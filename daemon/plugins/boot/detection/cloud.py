#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""
Plugin to allow for cloud node detection

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
from utils.log import Log
from utils.helper import Helper

azure = [
       '0003FF', '000D3A', '00125A', '00155D', '0017FA', '001DD8', '002248', '0025AE',
       '0C413E', '0CE725', '102F6B', '149A10', '206274', '20A99B', '281878', '2C2997',
       '300D43', '3059B7', '38256B', '38F23E', '3C8375', '444553', '485073', '4886E8',
       '4C0BBE', '501AC5', '5882A8', '5CBA37', '5CCA1A', '6045BD', '607EDD', '6C2483',
       '6C2779', '6C8FB5', '74E28C', '7C1E52', '7CED8D', '80C5E6', '8463D6', '949AA9',
       '985FD3', '9C6C15', 'A4516F', 'B4AE2B', 'B4E1C4', 'B84FD5', 'BC8385', 'C0335E',
       'C49DED', 'C83F26', 'D0929E', 'D48F33', 'DCB4C4', 'E498D1', 'EC59E7', 'F01DBC'
]
aws = [
       '0C47C9', '34D270', '40B4CD', '44650D', '50B363', '50F5DA', '6837E9', '6854FD',
       'F0272D', '747548', '74C246', '84D6D0', '8871E5', 'A002DC', 'AC63BE', 'B47C9C', 
       'F0D2F1', '02'
]
gcp = [
       '001A11', '089E08', '3C5AB4', '546009', '703ACB', '9495A0', '94EB2C', '98D293',
       'A47733', 'F40304', 'F4F5D8', 'F4F5E8', 'F88FCA'
]
vsphere = [
       '005056'
]

class Plugin():
    """
    This plugin class requires 1 mandatory method:
    -- find    : receives a MAC and returns the cloud name
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.working_path = "/trinity/local/var/lib/luna/detection"
        if not os.path.exists(self.working_path):
            os.makedirs(self.working_path)

    # ----------------------------------------------------------------------------------

    def find(self, macaddress=None):
        """
        This method will be used to find cloud names
        """
        status = False
        response = None
        if macaddress:
            octets = macaddress.split(':')
            for tel in range(3,0,-1):
                vendor = ''
                for oc in range(0,tel,1):
                    vendor += octets[oc]
                    if vendor.upper() in azure:
                        status = True
                        response = 'azure'
                        break
                    elif vendor.upper() in aws:
                        status = True
                        response = 'aws'
                        break
                    elif vendor.upper() in gcp:
                        status = True
                        response = 'gcp'
                        break
                    elif vendor.upper() in vsphere:
                        status = True
                        response = 'vsphere'
                        break
                else:
                    continue
                break
        self.logger.info(f"Cloud detection for {macaddress}: {response}")
        return status, response


