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
Plugin Class ::  Prometheus export class to export prometheus server rules.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


import os
import re
import yaml
from typing import List, Dict, Optional
from utils.log import Log
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
    

class HWSettings(BaseModel):
    nhc: Optional[bool] = True
    disabled: Optional[bool] = False

class Settings(BaseModel):
    hw: HWSettings

class ImportData(RootModel):
    root: Settings

class Plugin():
    """
    Class for exporting prometheus server rules
    """

    def __init__(self):
        """
        Initialize the logger and the rules folder
        """
        self.logger = Log.get_logger()
        self.prometheus_rules_folder = '/trinity/local/etc/prometheus_server/rules/'
        self.rules_settings_file = '/trinity/local/etc/prometheus_server/rules_settings.yaml'
    
    def _generate_hostname_path(self, hostname):
        hostname_regex = r'^([a-zA-Z0-9-_.])+$'
        if not re.match(hostname_regex, hostname):
            raise ValueError(f"Hostname ({hostname}) is invalid, should satisfy {hostname_regex}")
        path = f"/trinity/local/etc/prometheus_server/rules/trix.hw.{hostname}.rules"
        if not os.path.exists(os.path.dirname(path)):
            raise FileNotFoundError (f"Path ({os.path.dirname(path)}) does not exist")
        return path
    
    def _list_rules_hostnames(self):
        files = os.listdir(self.prometheus_rules_folder)
        hostnames_matches = [re.search(r'^trix[.]hw[.](.*)[.]rules$', f) for f in files]
        hostnames_matches = [m for m in hostnames_matches if ( m is not None) ]
        return [m.group(1) for m in hostnames_matches]
        
    def _write_rules_settings(self, rules_settings: Settings):
        """
        Write the rules settings to the rules settings file
        """
        with open(self.rules_settings_file, 'w', encoding="utf-8") as file:
            yaml.safe_dump(rules_settings.model_dump(), file)
    
    def _read_rules_settings(self) -> Settings:
        """
        Read the rules settings from the rules settings file
        """
        if not os.path.exists(self.rules_settings_file):
            return Settings(hw=HWSettings())
        with open(self.rules_settings_file, 'r', encoding="utf-8") as file:
            return Settings.model_validate(yaml.safe_load(file))

    def _write_rules(self, rules: PrometheusRules, path):
        with open(path, 'w', encoding='utf-8') as file:
            yaml.safe_dump(rules.model_dump(by_alias=True, exclude_none=True), file)

    def _read_rules(self, path) -> PrometheusRules:
        with open(path, 'r', encoding='utf-8') as file:
            return PrometheusRules.model_validate(yaml.safe_load(file))
    
    
    def Import(self, json_data=None):
        """
        This method will save the both files rules and detailed, depending on the users validation.
        """
        self.logger.info(f"Importing Prometheus Rules from {self.rules_settings_file}, with json_data: {json_data}")
        try:
            data = ImportData.model_validate(json_data)
            rules_settings = data.root
            self._write_rules_settings(rules_settings)
        except Exception as e:
            error_message = f'Error while importing rules settings: {e}'
            self.logger.error(error_message)
            return False, error_message

        response = []
        hostnames = self._list_rules_hostnames()
        for hostname in hostnames:
            try:
                hostname_path = self._generate_hostname_path(hostname)
                
                rules = self._read_rules(hostname_path)

                for group in rules.groups:
                    for rule in group.rules:
                        if (rules_settings.hw.nhc is not None):
                            rule.labels["nhc"] = str(rules_settings.hw.nhc).lower()
                        if (rules_settings.hw.disabled is not None):
                            rule.labels["disabled"] = str(rules_settings.hw.disabled).lower()
                
                self._write_rules(rules, hostname_path)
                response.append({"hostname": hostname, "status": True })
                
            except Exception as e:
                error_message = f'Error while importing rules for {hostname}: {e}'
                self.logger.error(error_message)
                response.append({"hostname": hostname, "status": False, "message": error_message })


        return True, response
    