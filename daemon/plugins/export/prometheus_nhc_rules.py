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
Plugin Class ::  Prometheus Export class to import Prometheus nhc rules.
"""

__author__      = "Diego Sonaglia"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Diego Sonaglia"
__email__       = "dieg.sonaglia@clustervision.com"
__status__      = "Development"


import re
import os
import json
import yaml
from utils.log import Log




class Plugin():
    """
    Class for exporting Prometheus rules
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.prometheus_rules_folder = '/trinity/local/etc/prometheus_server/rules/'

    def _generate_hostname_path(self, hostname):
        if not re.match(r'^([a-zA-Z0-9-_][.]?)+$', hostname):
            raise ValueError(f"Hostname ({hostname}) is invalid, should satidy ^([a-zA-Z0-9-_][.]?)+$")
        path = f"/trinity/local/etc/prometheus_server/rules/trix.hw.{hostname}.rules"
        if not os.path.exists(os.path.dirname(path)):
            raise FileNotFoundError (f"Path ({os.path.dirname(path)}) does not exist")
        return path

    def _read_rules_yaml(self, path):
        with open(path, 'r') as file:
            return yaml.safe_load(file)    

    def Export(self,args=None):
        """
        This method will check the both files rules and detailed, and return the output from the
        detailed file with status.
        This method will generate and save the Prometheus Hardware Rules for a specific node.
        """
        
        self.logger.debug(f'args => {args}')
        if not isinstance(args, dict):
            return False, f"args have type ({type(args)}) and should be a dict"
        if ("hostnames" in args) and (not isinstance(args["hostnames"], str)):
            return False, f"hostnames should be a str, got {type(args['hostnames'])}"
        
        if "hostnames" in args:
            hostnames = args["hostnames"].split(",")
        else:
            files = os.listdir(self.prometheus_rules_folder)
            hw_files = [f for f in files if re.match(r'^trix[.]hw[.].+[.]rules$', f)]
            hostnames = [re.search(r'^trix[.]hw[.]([^.]+)[.]rules$', f).group(1) for f in hw_files]
            
        status, response = True, []
        
        for hostname in hostnames:
            
            try:
                hostname_rules_path = self._generate_hostname_path(hostname)

                rules = self._read_rules_yaml(hostname_rules_path)
                    
                response.append({"hostname": hostname, "status": True, "data": rules})

            except Exception as exception:
                error = f"Error encountered while reading the Prometheus Rules for {hostname}: {exception}."
                response.append({"hostname": hostname, "status": False, "message": error})
            
        return status, response
       

