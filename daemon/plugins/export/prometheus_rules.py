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
import yaml
from utils.log import Log


class Plugin():
    """
    Class for exporting prometheus server rules
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.trix_config = '/trinity/local/etc/prometheus_server/rules/trix.rules'
        self.trix_config_details = '/trinity/local/etc/prometheus_server/rules/trix.rules.details'
        self.response = None


    def generate_details(self, details=None):
        """
        This method will generate the fresh new detailed file depending on the main file.
        """
        trix_data = ""
        with open(self.trix_config, 'r') as trix_file:
            trix_data = yaml.safe_load(trix_file)
        
        if trix_data:
            if "groups" in trix_data:
                for groups in trix_data["groups"]:
                    group_rules = groups["rules"]
                    for rule in group_rules:
                        if details is True:
                            rule["labels"]["_trix_status"] = True
                        rule["labels"]["nhc"] = "no"
        file = self.trix_config_details if details is True else self.trix_config

        self.logger.info(f'Updating File => {file}')
        with open(file, "w") as detail_file:
            yaml.dump(trix_data, detail_file, default_flow_style=False)
        return True


    def check_files(self):
        """
        This method will check both files with read & write permissions, and returns a list of
        errors.
        """
        self.response = []
        for file in [self.trix_config, self.trix_config_details]:
            if os.path.exists(file):
                self.logger.warning(f"The file '{file}' exists.")
                if os.access(file, os.R_OK):
                    self.logger.warning(f"The file '{file}' is readable.")
                else:
                    self.logger.info(f"The file '{file}' is not readable.")
                    self.response.append(f"The file '{file}' is not readable.")
                if os.access(file, os.W_OK):
                    self.logger.warning(f"The file '{file}' is writable.")
                else:
                    self.logger.info(f"The file '{file}' is not writable.")
                    self.response.append(f"The file '{file}' is not writable.")
                if file == self.trix_config_details and os.stat(file).st_size == 0:
                    self.logger.warning(f"The file '{file}' is empty.")
                    self.generate_details(details=True)
                    self.generate_details(details=False)
                else:
                    self.logger.info(f"The file '{file}' is not empty.")
            else:
                self.logger.warning(f"The file '{file}' does not exist.")
                if file == self.trix_config_details:
                    self.logger.info(f"Creating file '{file}' is empty.")
                    self.generate_details(details=True)
                else:
                    self.response.append(f"The file '{file}' does not exist.")
        return self.response


    def Export(self):
        """
        This method will check the both files rules and detailed, and return the output from the
        detailed file with status.
        """
        self.response = self.check_files()
        if self.response:
            check = False
        else:
            self.logger.info(f'Loading Detailed File => {self.trix_config_details}')
            check = True
            with open(self.trix_config_details, 'r') as file:
                self.response = yaml.safe_load(file)
        return check, self.response


