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
Plugin to allow for switch port detection

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    This plugin class requires 2 mandatory methods:
    -- find    : receives a MAC and returns switch,port
    -- scan    : is being called on regular basis to collect switch port/mac info from switches
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.working_path = "/trinity/local/var/lib/luna/detection"
        if not os.path.exists(self.working_path):
            os.makedirs(self.working_path)
        self.create_script()

    # ----------------------------------------------------------------------------------

    def clear(self):
        # empty what we have
        open(self.working_path+'/switchports.dat', 'w', encoding='utf-8').close()

    # ----------------------------------------------------------------------------------

    def find(self, macaddress=None):
        """
        This method will be used to find switch ports.
        """
        status = False
        response = None
        if macaddress:
            try:
                with open(self.working_path+'/switchports.dat', 'r', encoding='utf-8') as switchport_file:
                    switchport_data = switchport_file.readlines()
                    for line in switchport_data:
                        line = line.strip()
                        switch, port,mac = line.split('=')
                        self.logger.debug(f"{switch} {port} {mac}")
                        if mac.lower() == macaddress.lower():
                            self.logger.info(f"Found positive match for {mac} on {switch}:{port}")
                            return True, f"{switch}", f"{port}"
            except Exception as exp:
                self.logger.error(f"plugin threw one.... : {exp}")
        return status, response

    # ----------------------------------------------------------------------------------

    def scan(self, name=None, ipaddress=None, oid=None, read=None, rw=None, uplinkports=[]):
        # port_oid = switches[switch]['port_oid'] or '.1.3.6.1.2.1.31.1.1.1.1'
        # ifname_oid = switches[switch]['ifname_oid'] or '.1.3.6.1.2.1.17.1.4.1.2'
        doc = {}
        doc[name] = {}
        self.logger.debug(f"Walking for {name} ...")

        if (not ipaddress) or (not oid):
            return False, "no ipaddress or oid"

        bash_command = f"/bin/bash {self.working_path}/switchprobe.sh '{ipaddress}' '{oid}'"
        output, exit_code = Helper().runcommand(bash_command,True,60)
        if output and exit_code == 0:
            all_data = output[0].decode().split('\n')
            for port_data in all_data:
                if not port_data:
                    continue
                _port, _mac = port_data.split('=')
                if _port in uplinkports:
                    continue
                doc[name][_port] = _mac

        self.logger.debug(f"DOC: {doc}")

        with open(self.working_path+'/switchports.dat','a', encoding='utf-8') as switchport_file:
            for switch in doc.keys():
                for port in doc[switch].keys():
                    switchport_file.write(f"{switch}={port}={doc[switch][port]}\n")

    # ----------------------------------------------------------------------------------

    def create_script(self):
        script = """
#!/bin/bash

# Basic switch -> .1.3.6.1.2.1.17.7.1.2.2.1.2
# HP switch    -> .1.3.6.1.2.1.17.4.3.1.2

HOST=$1
OID=$2

for string in `snmpwalk -v 2c -c public $HOST $OID -O qn|sed -e "s/ /./g"`; do
    pstring=$(echo $string | sed -e 's/^'$OID'\.//')
    if [ "$OID" == ".1.3.6.1.2.1.17.4.3.1.2" ]; then
        decmac=$(echo $pstring|awk -F "." '{print $1";"$2";"$3";"$4";"$5";"$6}')
    else
        decmac=$(echo $pstring|awk -F "." '{print $2";"$3";"$4";"$5";"$6";"$7}')
        vlan=$(echo $pstring|awk -F "." '{print $1}')
    fi
    mac=""
    hex=""
    for hex in `echo "obase=16; $decmac"|bc`; do
        if [ ${#hex} == "1" ]; then
            hex="0"$hex
        fi
        if [ -z $mac ]; then
            mac=$hex
        else
            mac=$mac":"$hex
        fi
    done
    if [ "$OID" == ".1.3.6.1.2.1.17.4.3.1.2" ]; then
        port=$(echo $pstring|awk -F "." '{print $7}')
    else
        port=$(echo $pstring|awk -F "." '{print $8}')
    fi
    echo "${port}=${mac}"
done
"""
        with open(self.working_path+'/switchprobe.sh','w', encoding='utf-8') as probe_script:
            probe_script.write(f"{script}")
