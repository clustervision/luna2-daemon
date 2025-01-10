# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Prometheus Import class to import Prometheus nhc rules.
"""

__author__      = "Diego Sonaglia"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Diego Sonaglia"
__email__       = "dieg.sonaglia@clustervision.com"
__status__      = "Development"

import os
import re
import requests
import json
import yaml
from utils.log import Log


def _prometheus_check_response(query, response):
    if response.get("status") != "success":
        raise Exception(f"Failed to get data")
    if response.get("data") is None:
        raise Exception(f"No data found")
    if response.get("data").get("resultType") != "vector":
        raise Exception(f"Unexpected data type")
    if len(response.get("data").get("result")) == 0:
        raise Exception(f"No data found")

def _check_hostname(hostname, force):
    if hostname is None:
        raise Exception (f"Hostname is missing in the host dict, expected format: {json.dumps(_example_json_data(), indent=2)}")
    if not re.match(r'^([a-zA-Z0-9-_][.]?)+$', hostname):
        raise Exception (f"Hostname ({hostname}) is invalid")
    if type(force) is not bool:
        raise Exception (f"Force option ({force}) is invalid, expected boolean")
    
def _check_path(path, force):
    if os.path.exists(path) and not force:
        raise Exception (f"Path ({path}) already exists, use force option to overwrite")
    if not os.path.exists(os.path.dirname(path)):
        raise Exception (f"Path ({os.path.dirname(path)}) does not exist")

def _example_json_data():
    return [
        { "hostname": "node001" },
        { "hostname": "node002" },
        { "hostname": "node003", "force": True },
    ]
        

class Plugin():
    """
    Class for importing Prometheus rules
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.prometheus_url = "https://localhost:9090"
        self.prometheus_rules_folder = '/trinity/local/etc/prometheus_server/rules/'
        self.prometheus_rules_component_fields =  [
                "hostname", "path", "class", "description", "product", "vendor", "serial", "size", "capacity", "clock"
            ]

    def _prometheus_get_components_with_count(self, nodename):
        """
        Fetch components and their count in one query.
        """
        # Aggregate count by all relevant fields
        label_fields = ",".join(self.prometheus_rules_component_fields)
        query = (
            f'count(lshw_device{{class=~"processor|memory|disk|network|display", hostname="{nodename}"}})'
            f' by ({label_fields})'
        )
        response = requests.get(
            f"{self.prometheus_url}/api/v1/query", 
            params={"query": query}, 
            verify=False
        ).json()
        _prometheus_check_response(query, response)

        components = []
        for item in response.get("data").get("result"):
            # The aggregated count is returned as "value" and labels in "metric"
            metric = item.get("metric")
            # Extract count value from the result vector
            count_value = float(item.get("value")[1])
            component = {
                field: metric[field] 
                for field in self.prometheus_rules_component_fields 
                if field in metric
            }
            # Store the initial count with the component data
            component["initial_count"] = count_value
            components.append(component)

        return components
      
    def _prometheus_reload(self):
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False)
        if response.status_code != 200:
            raise Exception(f"Failed to reload Prometheus server")
  
    def _generate_rules_dict(self, nodename):
        # Use the updated method to get components with their counts in one call.
        data = self._prometheus_get_components_with_count(nodename)
        alerts = []

        for component in data:
            # Build label selector as before
            label_selector = ",".join([f'{key}="{value}"' for key, value in component.items() if key in self.prometheus_rules_component_fields])
            
            # Use the pre-fetched count for alert_expr_value
            alert_expr_value = component.get("initial_count")
            alert_name = f"{component.get('class').capitalize()} changed"
            alert_expr = f"count(lshw_device{{{label_selector}}})"

            alert = {
                "alert": alert_name,
                "expr": f"{alert_expr} != {alert_expr_value}",
                "for": "1m",
                "labels": {
                    "severity": "warning"
                },
                "annotations": {
                    "summary": f"{component.get('class').capitalize()} device @ {component.get('hostname')}{component.get('path', '')} changed",
                }
            }
            alerts.append(alert)

        rules = {
            "groups": [
                {
                    "name": "trinityx_hw",
                    "rules": alerts
                }
            ]
        }
        return rules

    def _generate_rules_yaml(self, nodename):
        rules = self._generate_rules_dict(nodename)
        return yaml.dump(rules, default_flow_style=False)

    def _generate_rules_json(self, nodename):
        rules = self._generate_rules_dict(nodename)
        return json.dumps(rules, indent=2)
    
    def Import(self, json_data=None):
        """
        This method will generate and save the Prometheus Hardware Rules for a specific node.
        """
        self.logger.debug(f'json_data => {json_data}')
        if type(json_data) is not list:
            return False, f"Json data has type ({type(json_data)}) and should be a list, expected format: {json.dumps(_example_json_data(), indent=2)}"
        if not json_data:
            return False, f"Json data is an empty list, expected format: {json.dumps(_example_json_data(), indent=2)}"

                
        status, response = True, []
        
        for host in json_data:
            try:
                hostname = host.get("hostname")
                force = host.get("force", False)
                
                _check_hostname(hostname, force)
                
                rules = self._generate_rules_yaml(hostname)
                hostname_rules_name = f"trix.hw.{hostname}.rules"
                hostname_rules_path = os.path.join(self.prometheus_rules_folder, hostname_rules_name)
                
                _check_path(hostname_rules_path, force)

                with open(hostname_rules_path, 'w') as file:
                    file.write(rules)

                self._prometheus_reload()
            
                response.append({"hostname": hostname, "status": True})

            except Exception as exception:
                error = f"Error encountered while generating the  Prometheus Server Rules for {hostname}: {exception}."
                response.append({"hostname": hostname, "status": False, "message": error})
            
        return status, response



