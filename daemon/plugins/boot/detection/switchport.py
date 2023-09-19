#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin to allow for switch port detection

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.helper import Helper
import os


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

    
    def scan(self, switches={}):
        #def scan(self, name=None, ipaddress=None, oid=None, read=None, rw=None, uplinkports=[]):
        """
        switches is a dict that contains: switches { id: { name: , oid:, read:, rw:, ipaddress, uplinkports: } }
        """
        doc = {}
        # empty what we have
        open(self.working_path+'/switchports.dat', 'w', encoding='utf-8').close()
        for switch in switches.keys():
            name = switches[switch]['name']
            ipaddress = switches[switch]['ipaddress']
            oid = switches[switch]['oid']
            # port_oid = switches[switch]['port_oid'] or '.1.3.6.1.2.1.31.1.1.1.1'
            # ifname_oid = switches[switch]['ifname_oid'] or '.1.3.6.1.2.1.17.1.4.1.2'
            read = switches[switch]['read']
            rw = switches[switch]['rw']
            doc[name] = {}
            uplinks = [] 
            if 'uplinkports' in switches[switch] and switches[switch]['uplinkports']:
                uplinks_str = switches[switch]['uplinkports']
                uplinks_str = uplinks_str.replace(' ','')
                uplinks = uplinks_str.split(',')
            self.logger.debug(f"Walking for {name} ...")

            bash_command = f"/bin/bash {self.working_path}/switchprobe.sh '{ipaddress}' '{oid}'"
            output, exit_code = Helper().runcommand(bash_command,True,60)
            if output and exit_code == 0:
                all_data = output[0].decode().split('\n')
                for port_data in all_data:
                    if not port_data:
                        continue
                    _port, _mac = port_data.split('=')
                    if _port in uplinks:
                        continue
                    doc[name][_port] = _mac

        self.logger.debug(f"DOC: {doc}")

        with open(self.working_path+'/switchports.dat','a', encoding='utf-8') as switchport_file:
            for switch in doc.keys():
                for port in doc[switch].keys():
                    switchport_file.write(f"{switch}={port}={doc[switch][port]}\n")


    def create_script(self):
        SCRIPT = """
#!/bin/bash

HOST=$1
OID=$2

for string in `snmpwalk -v 2c -c public $HOST $OID -O qn|sed -e "s/^\.//g" -e "s/ /./g"`; do
    decmac=$(echo $string|awk -F "." '{print $15";"$16";"$17";"$18";"$19";"$20}')
    vlan=$(echo $string|awk -F "." '{print $14 }')
    mac=""
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
    port=$(echo $string|awk -F "." '{print $21}')
    echo "${port}=${mac}"
done
"""
        with open(self.working_path+'/switchprobe.sh','w', encoding='utf-8') as probe_script:
            probe_script.write(f"{SCRIPT}")


