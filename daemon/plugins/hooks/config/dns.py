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
Plugin Class ::  DNS config calls
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
from utils.helper import Helper

class Plugin():
    """
    This is the default class for dns config plugin.
    """

    def __init__(self):
        """
        method nsupdate and notify are mandatory
        - nsupdate: updates the record for the given host. typically used
                    when a network has been configured as nodes_in_pool
                    while mixing non-dhcp configured hosts
        - notify:   informs the slaves that a new zone definition is ready
        """

    def nsupdate(self, host, ipaddress, zone=None, ttl=3600, key_name=None, key_secret=None, key_hmac='hmac-md5'):
        """
        host and ipaddress are required.
        this method is being called for each non-dhcp configured host
        in a network where dhcp_nodes_in_pool is set.
        """
        status = False
        update_file = "/root/nsupdate_data"
        if host and ipaddress:
            if os.path.exists(update_file):
                os.remove(update_file)
            with open(update_file, "a") as nsfile:
                if key_name and key_secret:
                    nsfile.write(f"key {key_hmac}:{key_name} {key_secret}\n")
                if zone:
                    nsfile.write(f"zone {zone}\n")
                nsfile.write(f"update delete {host}\n")
                nsfile.write(f"update add {host} {ttl} A {ipaddress}\n")
                nsfile.write("send\n")
        output, exit_code = Helper().runcommand(f"nsupdate {update_file}",True,10)
        if output and exit_code == 0:
            response = str(output[0].decode())
            status = True
        else:
            if len(output)>1:
                response = str(output[1].decode())
            response = f"Command execution failed with exit code {exit_code}: {response}"
        return status, response

    def notify(self,master,slaves,key):
        """
        this method is only called once, after regenerating zones
        """
        return True, "success"
