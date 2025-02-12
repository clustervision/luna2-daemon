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
__version__     = "2.1"
__maintainer__  = "Diego Sonaglia"
__email__       = "dieg.sonaglia@clustervision.com"
__status__      = "Development"


import os
import re
import requests
import json
import yaml
from utils.log import Log

from typing import Dict, List, Optional
from pydantic import BaseModel, RootModel, Field, field_validator

class Annotations(BaseModel):
    description: str

class Rule(BaseModel):
    alert: str
    expr: str
    for_: Optional[str] = Field(alias="for", default=None)
    labels: Dict[str, str]
    annotations: Optional[Annotations] = None
    
    @field_validator("for_")
    @classmethod
    def validate_for_(cls, value):
        if value is not None:
            if not re.match(r'^[0-9]+[s|m|h]$', value):
                raise ValueError(f'for value must be a string with a number followed by "s", "m" or "h", but got {value}')
        return value
    
    @field_validator("labels")
    @classmethod
    def validate_labels(cls, value):
        # check that nhc, hw, disabled labels are in ['true', 'false'] and that severity is in ['critical', 'danger', 'warning', 'info']
        for key, val in value.items():
            if key in ['nhc', 'hw', 'disabled']:
                if val not in ['true', 'false']:
                    raise ValueError(f'{key} label must be either "true" or "false", but got {val}')
            if key == 'severity':
                if val not in ['critical', 'danger', 'warning', 'info']:
                    raise ValueError(f'{key} label must be either "critical", "danger", "warning" or "info", but got {val}')
        
        return value

class Group(BaseModel):
    name: str
    rules: List[Rule]

class PrometheusRules(BaseModel):
    groups: List[Group]
   
class ImportDataEntry(BaseModel):
    hostname: str
    force: Optional[bool] = False
    nhc: Optional[bool] = None
    disabled: Optional[bool] = None

class HWSettings(BaseModel):
    nhc: Optional[bool] = True
    disabled: Optional[bool] = False

class Settings(BaseModel):
    hw: HWSettings

class ImportData(RootModel):
    root: List[ImportDataEntry]


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
        self.rules_settings_file = '/trinity/local/etc/prometheus_server/rules_settings.yaml'
        self.prometheus_rules_component_fields =  [
                "hostname", "luna_group", "path", "class", "description", "product", "vendor", "serial"
            ]

    @staticmethod
    def _prometheus_check_response(query, response):
        if response.get("status") != "success":
            raise RuntimeError(f"Failed to get prometheus data for query {query}")
        if response.get("data") is None:
            raise RuntimeError(f"No data found for query {query}")
        if response.get("data").get("resultType") != "vector":
            raise RuntimeError(f"Unexpected data type for query {query}")
        if len(response.get("data").get("result")) == 0:
            raise RuntimeError(f"No data found for query {query}")
    
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
        hostname_regex = r'^([a-zA-Z0-9-_.])+$'
        if not re.match(hostname_regex, hostname):
            raise ValueError(f"Hostname ({hostname}) is invalid, should satisfy {hostname_regex}")
        path = f"/trinity/local/etc/prometheus_server/rules/trix.hw.{hostname}.rules"
        if not os.path.exists(os.path.dirname(path)):
            raise FileNotFoundError (f"Path ({os.path.dirname(path)}) does not exist")
        return path
  
    def _generate_rules(self, nodename, settings: Settings) -> PrometheusRules:
        # Use the updated method to get components with their counts in one call.
        data = self._prometheus_get_components_with_count(nodename)
        alerts = []

        for component in data:
            # Build label selector as before
            label_selector = ",".join([f'{key}="{value}"' for key, value in component.items() if key in self.prometheus_rules_component_fields])
            
            # Use the pre-fetched count for alert_expr_value
            # alert_expr_value = component.get("initial_count")
            # alert_name = f"{component.get('class').capitalize()} changed"
            alert_expr = f"lshw_device{{{label_selector}}}"

            alert = {
                "alert": "MissingHardwareComponent",
                "expr": f"absent({alert_expr})",
                "labels": {
                    "severity": "warning",
                    "hw": "true",
                    "nhc": str(settings.hw.nhc).lower(),
                    "disabled":str(settings.hw.disabled).lower(),
                },
                "annotations": {
                    "description": "Hardware component {{ $labels.class }} with {{ $labels.product }} {{ $labels.vendor }} {{ $labels.serial }} is missing."
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
        
        return PrometheusRules(groups=[Group(**group) for group in rules["groups"]])
    
    def _write_rules(self, rules: PrometheusRules, path):
        with open(path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(rules.model_dump(by_alias=True, exclude_none=True), file, explicit_start=True, explicit_end=True)

    def _read_rules(self, path) -> PrometheusRules:
        with open(path, 'r', encoding='utf-8') as file:
            return PrometheusRules.model_validate(yaml.safe_load(file))

    def _read_rules_settings(self) -> Settings:
        """
        Read the rules settings from the rules settings file
        """
        if not os.path.exists(self.rules_settings_file):
            return Settings(hw=HWSettings())
        with open(self.rules_settings_file, 'r', encoding="utf-8") as file:
            return Settings.model_validate(yaml.safe_load(file))
        
        
    def Import(self, json_data=None):
        """
        This method will generate and save the Prometheus Hardware Rules for a specific node.
        """
        
        try:
            data = ImportData.model_validate(json_data)
        except Exception as exception:
            error_message = f"Error encountered while validating the input data: {exception}."
            self.logger.error(error_message)
            return False, error_message
        
        try:
            rules_settings = self._read_rules_settings()
        except Exception as exception:
            error_message = f"Error encountered while reading the rules settings: {exception}."
            self.logger.error(error_message)
            return False, error_message

        response = []
        
        for host in data.root:
            try:        
                hostname_rules_path = self._generate_hostname_path(host.hostname)
                
                if (not host.force) and os.path.exists(hostname_rules_path):
                    rules = self._read_rules(hostname_rules_path)
                else:
                    rules =self._generate_rules(host.hostname, rules_settings)

                if (host.nhc is not None):
                    for group in rules.groups:
                        for rule in group.rules:
                            rule.labels["nhc"] = str(host.nhc).lower()
                if (host.disabled is not None):
                    for group in rules.groups:
                        for rule in group.rules:
                            rule.labels["disabled"] = str(host.disabled).lower()


                self._write_rules(rules, hostname_rules_path)
                response.append({"hostname": host.hostname, "status": True})
            except Exception as exception: 
                error_message = f"Error encountered while generating the  Prometheus Server Rules for {host.hostname}: {exception}."
                self.logger.error(error_message)
                response.append({"hostname": host.hostname, "status": False, "message": error_message})
            finally:
                pass
        
        try:
            self._prometheus_reload()
        except Exception as exception:
            error_message = f"Error encountered while reloading the Prometheus Server: {exception}."
            self.logger.error(error_message)
            return False, error_message
                    
        return True, response
