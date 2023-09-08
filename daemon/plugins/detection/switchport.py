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
import netsnmp


class Plugin():
    """
    This plugin class requires 2 mandatory methods:
    -- find    : receives a MAC and returns switch,port
    -- scan    : is being called on regular basis to collect switch port/mac info from switches
    """

    def __init__(self):
        self.logger = Log.get_logger()


    def find(self, macaddress=None):
        """
        This method will be used to find switch ports.
        """
        status = False
        response = None
        if macaddress:
            try:
                with open('/tmp/switchports.dat', 'r', encoding='utf-8') as switchport_file:
                    switchport_data = switchport_file.readlines()
                    for line in switchport_data:
                        line = line.strip()
                        switch, port,mac = line.split('=')
                        self.logger.debug(f"{switch} {port} {mac}")
                        if mac == macaddress:
                            self.logger.info(f"Found positive match for {mac} on {switch}:{port}")
                            status = True
                            response = f"{switch}", f"{port}"
                            return True, f"{switch}", f"{port}"
            except Exception as exp:
                self.logger.error(f"plugin threw one.... : {exp}")
        return status, response

    
    def scan(self, switches={}):
        """
        switches is a dict that contains: switches { id: { name: , oid:, read:, rw:, ipaddress: } }
        """
        doc = {}
        # empty what we have
        open('/tmp/switchports.dat', 'w', encoding='utf-8').close()
        for switch in switches.keys():
            name = switches[switch]['name']
            ipaddress = switches[switch]['name']
            oid = switches[switch]['oid']
            # port_oid = switches[switch]['port_oid'] or '.1.3.6.1.2.1.31.1.1.1.1'
            # ifname_oid = switches[switch]['ifname_oid'] or '.1.3.6.1.2.1.17.1.4.1.2'
            read = switches[switch]['read']
            rw = switches[switch]['rw']
            self.logger.debug(f"Walking for {name} ...")

            if ipaddress and read and oid:
                vl = netsnmp.VarList(netsnmp.Varbind(oid))
                res = netsnmp.snmpwalk(vl, Version=2, DestHost=ipaddress, Community=read, UseNumeric=True)

                # vl_ifnames = netsnmp.VarList(netsnmp.Varbind(ifname_oid))
                # ifnames = netsnmp.snmpwalk(vl_ifnames, Version=2, DestHost=ipaddress, Community=read, UseNumeric=True)

                # vl_portmap = netsnmp.VarList(netsnmp.Varbind(port_oid))
                # portmap = netsnmp.snmpwalk(vl_portmap, Version=2, DestHost=ipaddress, Community=read, UseNumeric=True)

                # portmaps = {}
                # for i in range(len(vl_portmap)):
                #     if vl_portmap[i].iid:
                #         pornnum = vl_portmap[i].iid
                #     else:
                #         pornnum = vl_portmap[i].tag.split('.')[-1:][0]

                #     try:
                #         portmaps[int(pornnum)] = int(vl_portmap[i].val)
                #     except:
                #         pass

                # portnums = {}
                # for i in range(len(vl_ifnames)):
                #     if vl_ifnames[i].iid:
                #         pornnum = vl_ifnames[i].iid
                #     else:
                #         pornnum = vl_ifnames[i].tag.split('.')[-1:][0]

                #     tmpvar = vl_ifnames[i]
                #     try:
                #         portnums[int(pornnum)] = str(vl_ifnames[i].val)
                #     except:
                #         pass

                doc[name]={}
                for i in enumerate(vl):
                    mac = ''
                    port = str(vl[i].val)

                    # try:
                    #     portname = portnums[portmaps[int(vl[i].val)]]
                    # except KeyError:
                    #     portname = port

                    for elem in vl[i].tag.split('.')[-5:]:
                        mac += hex(int(elem)).split('x')[1].zfill(2) + ':'

                    mac += hex(int(vl[i].iid)).split('x')[1].zfill(2)
                    doc[name][port] = mac
                    # doc[name]['portname'] = portname

        with open('/tmp/switchports.dat','a', encoding='utf-8') as switchport_file:
            for switch in doc.keys():
                for port in switch.keys():
                    switchport_file.write(f"{switch}={port}={switch[port]}")
 
