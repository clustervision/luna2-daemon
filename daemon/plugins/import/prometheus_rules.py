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

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


import re
import os
import yaml
import requests
from utils.log import Log
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, field_validator

class Annotations(BaseModel):
    description: str

class Rule(BaseModel):
    alert: str
    expr: str
    for_: Optional[str] = Field(alias="for", default=None)
    labels: Dict[str, str|bool]
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
            if key in ['nhc', 'disabled']:
                if not isinstance(val, bool):
                    raise ValueError(f'{key} label must be a boolean, but got {val}')
            if key == 'severity':
                if val not in ['critical', 'danger', 'warning', 'info']:
                    raise ValueError(f'{key} label must be either "critical", "danger", "warning" or "info", but got {val}')
            if key == 'category':
                if val not in ['hardware', 'service', 'generic']:
                    raise ValueError(f'{key} label must be either "hardware", "software" or "generic", but got {val}')
        if 'category' not in value:
            value['category'] = 'generic'
        return value

class Group(BaseModel):
    name: str
    rules: List[Rule]

class PrometheusRules(BaseModel):
    groups: List[Group]
    

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
        self.prometheus_rules_path = '/trinity/local/etc/prometheus_server/rules/trix.rules'

    def _prometheus_reload(self):
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False, timeout=5)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to reload Prometheus server")

    def _read_rules(self) -> PrometheusRules:
        if not os.path.exists(self.prometheus_rules_path):
            return PrometheusRules(groups=[])
        with open(self.prometheus_rules_path, 'r', encoding="utf-8") as file:
            return PrometheusRules.model_validate(yaml.safe_load(file))
    
    def _write_rules(self, rules: PrometheusRules):
        with open(self.prometheus_rules_path, 'w', encoding="utf-8") as file:
            yaml.safe_dump(rules.model_dump(by_alias=True, exclude_none=True), file)

    def Import(self, json_data=None):
        """
        This method will save the both files rules and detailed, depending on the users validation.
        """
        self.logger.info(f"Importing Prometheus Rules to {self.prometheus_rules_path}, with json_data: {json_data}")
        try:
            rules = PrometheusRules.model_validate(json_data)
            
            self._write_rules(rules)
            self._prometheus_reload()

            response = f"TrinityX Prometheus Server Rules is updated under {self.prometheus_rules_path}."
            return True, response
        except Exception as exception:
            error_message = f"Error encountered while saving the Prometheus Rules at {self.prometheus_rules_path}: {exception}."
            self.logger.error(error_message)
            return False, error_message

