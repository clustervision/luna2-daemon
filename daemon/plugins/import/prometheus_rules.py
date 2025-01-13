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
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


import requests
import yaml
import copy
from utils.log import Log


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
        self.prometheus_rules_details_path = '/trinity/local/etc/prometheus_server/rules/trix.rules.details'


    def _prometheus_reload(self):
        response = requests.post(f"{self.prometheus_url}/-/reload", verify=False)
        if response.status_code != 200:
            raise Exception(f"Failed to reload Prometheus server")

    def Import(self, json_data=None):
        """
        This method will save the both files rules and detailed, depending on the users validation.
        """
        try:
            self.logger.debug(f'json_data => {json_data}')
            trix_rules = copy.deepcopy(json_data)
            if trix_rules:
                if "groups" in trix_rules:
                    for groups in trix_rules["groups"]:
                        group_rules = groups["rules"]
                        for rule in group_rules:
                            if rule["labels"]["_trix_status"] is False:
                                group_rules.remove(rule)
                            else:
                                del rule["labels"]["_trix_status"]

            self.logger.info(f'Saving Detailed File => {self.prometheus_rules_details_path}')
            with open(self.prometheus_rules_details_path, 'w') as file:
                yaml.dump(json_data, file, default_flow_style=False)
            
            self.logger.info(f'Saving Rules File => {self.prometheus_rules_path}')
            with open(self.prometheus_rules_path, 'w') as file:
                yaml.dump(trix_rules, file, default_flow_style=False)

            self._prometheus_reload()

            status = True
            response = f"TrinityX Prometheus Server Rules is updated under {self.prometheus_rules_path}."

        except Exception as exception:
            status = False
            response = f"Encounter a error While saving the TrinityX Prometheus Server Rules {exception}."

        return status, response



