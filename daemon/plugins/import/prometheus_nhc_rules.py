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
                "hostname", "luna_group", "path", "class", "description", "product", "vendor", "serial", "size", "capacity", "clock"
            ]

    @staticmethod
    def _prometheus_check_response(query, response):
        if response.get("status") != "success":
            raise Exception(f"Failed to get prometheus data for query {query}")
        if response.get("data") is None:
            raise Exception(f"No data found for query {query}")
        if response.get("data").get("resultType") != "vector":
            raise Exception(f"Unexpected data type for query {query}")
        if len(response.get("data").get("result")) == 0:
            raise Exception(f"No data found for query {query}")
    
    @staticmethod
    def _example_json_data():
        return [
            { "hostname": "node001.cluster" },
            { "hostname": "node002.cluster" },
            { "hostname": "node003.cluster", "force": True },
            { "hostname": "node004.cluster", "nhc": False },
            { "hostname": "node005.cluster", "disabled": True },
            { "hostname": "node005.cluster", "force": False, "nhc": False, "disabled": False }
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
            verify=False,
            timeout=5
        ).json()
        self._prometheus_check_response(query, response)

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
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False, timeout=5)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to reload Prometheus server")
  
    def _generate_hostname_path(self, hostname):
        if hostname is None:
            raise KeyError(f"Hostname is missing in the host dict, expected format: {json.dumps(self._example_json_data(), indent=2)}")
        if not re.match(r'^([a-zA-Z0-9-_][.]?)+$', hostname):
            raise ValueError(f"Hostname ({hostname}) is invalid, should satidy ^([a-zA-Z0-9-_][.]?)+$")
        path = f"/trinity/local/etc/prometheus_server/rules/trix.hw.{hostname}.rules"
        if not os.path.exists(os.path.dirname(path)):
            raise FileNotFoundError (f"Path ({os.path.dirname(path)}) does not exist")
        return path
  
    def _generate_rules(self, nodename):
        # Use the updated method to get components with their counts in one call.
        data = self._prometheus_get_components_with_count(nodename)
        alerts = []

        for component in data:
            # Build label selector as before
            label_selector = ",".join([f'{key}="{value}"' for key, value in component.items() if key in self.prometheus_rules_component_fields])
            
            # Use the pre-fetched count for alert_expr_value
            # alert_expr_value = component.get("initial_count")
            alert_name = f"{component.get('class').capitalize()} changed"
            alert_expr = f"lshw_device{{{label_selector}}}"

            alert = {
                "alert": alert_name,
                "expr": f"absent({alert_expr})",
                "labels": {
                    "severity": "warning"
                },
                "annotations": {
                    "description": f"{component.get('class').capitalize()} device @ {component.get('hostname')}{component.get('path', '')} changed",
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
    
    def _write_rules_yaml(self, rules, path):
        with open(path, 'w') as file:
            yaml.dump(rules, file, default_flow_style=False)

    def _read_rules_yaml(self, path):
        with open(path, 'r') as file:
            return yaml.safe_load(file)


        
        
    def Import(self, json_data=None):
        """
        This method will generate and save the Prometheus Hardware Rules for a specific node.
        """
        self.logger.debug(f'json_data => {json_data}')
        if not isinstance(json_data, list):
            return False, f"Json data has type ({type(json_data)}) and should be a list, expected format: {json.dumps(self._example_json_data(), indent=2)}"
        if not json_data:
            return False, f"Json data is an empty list, expected format: {json.dumps(self._example_json_data(), indent=2)}"
        
        
        status, response = True, []
        
        for host in json_data:
            try:
                hostname = host.get("hostname")
                force = host.get("force", False)
                if not(isinstance(force, bool)):
                    raise ValueError(f"Force should be a boolean value, got {type(force)}")
                nhc = host.get("nhc", None)
                if (nhc is not None) and not(isinstance(nhc, bool)):
                    raise ValueError(f"NHC should be a boolean value, got {type(nhc)}")
                disabled = host.get("disabled", None)
                if (disabled is not None) and not(isinstance(disabled, bool)):
                    raise ValueError(f"Disabled should be a boolean value, got {type(disabled)}")
                
                hostname_rules_path = self._generate_hostname_path(hostname)
                
                if (not force) and os.path.exists(hostname_rules_path):
                    rules = self._read_rules_yaml(hostname_rules_path)
                else:
                    rules =self._generate_rules(hostname)

                if (nhc is not None):
                    for group in rules['groups']:
                        for rule in group['rules']:
                            rule["labels"]["nhc"] = str(nhc).lower()
                if (disabled is not None):
                    for group in rules['groups']:
                        for rule in group['rules']:
                            rule["labels"]["disabled"] = str(disabled).lower()


                
                response.append({"hostname": hostname, "status": True, "data": rules})

            except Exception as exception: 
                error = f"Error encountered while generating the  Prometheus Server Rules for {hostname}: {exception}."
                response.append({"hostname": hostname, "status": False, "message": error})
            finally:
                pass
        
        self._write_rules_yaml(rules, hostname_rules_path)
        self._prometheus_reload()
        
        return status, response
