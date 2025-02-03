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
from pydantic import BaseModel, RootModel, Field

class Annotations(BaseModel):
    description: str

class Rule(BaseModel):
    alert: str
    expr: str
    for_: Optional[str] = Field(alias="for", default=None)
    labels: Dict[str, str]
    annotations: Optional[Annotations] = None

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
            yaml.dump(rules_settings.model_dump(), file)
    
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
            yaml.dump(rules.model_dump(by_alias=True, exclude_defaults=True), file)

    def _read_rules(self, path) -> PrometheusRules:
        with open(path, 'r', encoding='utf-8') as file:
            return PrometheusRules.model_validate(yaml.safe_load(file))
    
    def Export(self, args=None):
        """
        This method will check the both files rules and detailed, and return the output from the
        detailed file with status.
        """
        self.logger.info(f"Exporting Prometheus Rules from {self.rules_settings_file}, with args: {args}")
        try:
            rules_settings = self._read_rules_settings()
            response = rules_settings.model_dump()
        except Exception as e:
            error_message = f'Error while exporting rules settings: {e}'
            self.logger.error(error_message)
            return False, error_message

        return True, response