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
Plugin Class ::  Prometheus Import class to import prometheus server rules.
"""

__author__      = "Diego Sonaglia"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Diego Sonaglia"
__email__       = "dieg.sonaglia@clustervision.com"
__status__      = "Development"

import os
import argparse
import requests
import json
import yaml
from utils.log import Log


def _check_response(response):
    if response.get("status") != "success":
        raise Exception(f"Failed to get data")
    if response.get("data") is None:
        raise Exception(f"No data found")
    if response.get("data").get("resultType") != "vector":
        raise Exception(f"Unexpected data type")
    if len(response.get("data").get("result")) == 0:
        raise Exception(f"No data found")

def _example_json_data():
    return {
        "hostname": {
            "option1": "value1",
            "option2": "value2"
        }
    }

class Plugin():
    """
    Class for importing prometheus server rules
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

    def _prometheus_get_components(self, nodename):
        """
        This method will source a list of components using data from the Prometheus server.
        """
        query = f'lshw_device{{class=~"processor|memory|disk|network|display", hostname="{nodename}"}}'
        response = requests.get(f"{self.prometheus_url}/api/v1/query", 
                                params={"query": query}, 
                                verify=False).json()
        
        _check_response(response)
        
        components = []
        for item in response.get("data").get("result"):
            fields = item.get("metric")
            component = {field: fields[field] for field in self.prometheus_rules_component_fields if field in fields}
            components.append(component)
        
        return components

    def _prometheus_get_query_value(self, query):
        response = requests.get(f"{self.prometheus_url}/api/v1/query", 
                                params={"query": query}, 
                                verify=False).json()
        _check_response(response)
        
        return response.get("data").get("result")[0].get("value")[1]
      
    def _prometheus_reload(self):
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False)
        if response.status_code != 200:
            raise Exception(f"Failed to reload Prometheus server")
  
    def _generate_rules_dict(self, nodename):
        data = self._prometheus_get_components(nodename)
        alerts = []
        for component in data:
            label_selector = ",".join([f'{key}="{value}"' for key, value in component.items()])
            alert_name = f"{component.get('class').capitalize()} changed"
            alert_expr = f"count (lshw_device{{{label_selector}}})"
            alert_expr_value = self._prometheus_get_query_value(alert_expr)
            
            alert = {
                "alert": alert_name,
                "expr": f"{alert_expr} != {alert_expr_value}",
                "for": "1m",
                "labels": {
                    "severity": "warning"
                },
                "annotations": {
                    "summary": f"{component.get('class').capitalize()} device @ {component['hostname']}{component.get('path')} changed",
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
        return yaml.dump(rules)        

    def _generate_rules_json(self, nodename):
        rules = self._generate_rules_dict(nodename)
        return json.dumps(rules, indent=2)
    
    def Import(self, json_data=None):
        """
        This method will generate and save the Prometheus Hardware Rules for a specific node.
        """
        self.logger.debug(f'json_data => {json_data}')
        if type(json_data) is not dict:
            return False,f"Json data has type ({type(json_data)}) and should be a dictionary."
        if len(json_data) == 0:
            return False, f"Json data is empty."
        for hostname, options in json_data.items():
            if type(hostname) is not str:
                return False, f"Hostname has type ({type(hostname)}) and should be a string."
            if type(options) is not dict:
                return False, f"Options have type ({type(options)}) and should be a dictionary."
        response = "Prometheus rules imported successfully."
        status = True
        errors = {}
        for hostname, options in json_data.items():
            try:
                rules = self._generate_rules_yaml(hostname)
                hostname_rules_name = f"trix.hw.{hostname}.rules"
                hostname_rules_path = os.path.join(self.prometheus_rules_folder, hostname_rules_name)
                with open(hostname_rules_path, 'w') as file:
                    file.write(rules)
                self._prometheus_reload()
            except Exception as exception:
                error = f"Error encountered while generating the  Prometheus Server Rules for {hostname}: {exception}."
                errors.update({hostname: error})
        if len(errors) > 0:
            status = False
            response = errors
            
        return status, response



