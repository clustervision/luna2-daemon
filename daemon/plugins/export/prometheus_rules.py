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
import time
import shutil
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
        self.prometheus_generic_rules_path = '/trinity/local/etc/prometheus_server/rules/trix.generic.rules'
        self.prometheus_service_rules_path = '/trinity/local/etc/prometheus_server/rules/trix.service.rules'

    def _prometheus_reload(self):
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False, timeout=5)
        if response.status_code != 200:
            raise RuntimeError("Failed to reload Prometheus server")

    def _read_rules(self) -> PrometheusRules:
        rules = []
        
        if os.path.exists(self.prometheus_generic_rules_path):
            with open(self.prometheus_generic_rules_path, 'r', encoding="utf-8") as file:
                generic_rules = PrometheusRules.model_validate(yaml.safe_load(file))
                for group in generic_rules.groups:
                    for rule in group.rules:
                        rules.append(rule)
        
        if os.path.exists(self.prometheus_service_rules_path):
            with open(self.prometheus_service_rules_path, 'r', encoding="utf-8") as file:
                service_rules = PrometheusRules.model_validate(yaml.safe_load(file))
                for group in service_rules.groups:
                    for rule in group.rules:
                        rules.append(rule)

        rules = PrometheusRules(groups=[Group(name='trinityx', rules=rules)])
        return rules
    
    def _write_rules(self, rules: PrometheusRules):
        _generic_rules = []
        _service_rules = []
        
        for group in rules.groups:
            for rule in group.rules:
                if rule.labels['category'] == 'generic':
                    _generic_rules.append(rule)
                elif rule.labels['category'] == 'service':
                    _service_rules.append(rule)
        
        if os.path.exists(self.prometheus_generic_rules_path):
            dirname, basename = os.path.split(self.prometheus_generic_rules_path)
            backup_path = os.path.join(dirname, "backup", f"{basename}.{int(time.time())}")
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy(self.prometheus_generic_rules_path, backup_path)
        
        if os.path.exists(self.prometheus_service_rules_path):
            dirname, basename = os.path.split(self.prometheus_service_rules_path)
            backup_path = os.path.join(dirname, "backup", f"{basename}.{int(time.time())}")
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy(self.prometheus_service_rules_path, backup_path)
        
        with open(self.prometheus_generic_rules_path, 'w', encoding="utf-8") as file:
            generic_rules = PrometheusRules(groups=[Group(name='trinityx', rules=_generic_rules)])
            yaml.safe_dump(generic_rules.model_dump(by_alias=True, exclude_none=True), file, explicit_start=True, explicit_end=True)
        
        with open(self.prometheus_service_rules_path, 'w', encoding="utf-8") as file:
            service_rules = PrometheusRules(groups=[Group(name='trinityx', rules=_service_rules)])
            yaml.safe_dump(service_rules.model_dump(by_alias=True, exclude_none=True), file, explicit_start=True, explicit_end=True)

    def Export(self, args=None):
        """
        This method will check the both files rules and detailed, and return the output from the
        detailed file with status.
        """
        self.logger.info(f"Exporting Prometheus Rules from {self.prometheus_generic_rules_path} and {self.prometheus_service_rules_path}, with args: {args}")
        try:
            rules = self._read_rules()
            response = rules.model_dump(by_alias=True)

        except Exception as exception:
            error_message = f"Error encountered while reading Prometheus Rules at  {self.prometheus_generic_rules_path} or {self.prometheus_service_rules_path}: {exception}."
            self.logger.error(error_message)
            return False, error_message

        return True, response
