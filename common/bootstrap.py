#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is responsible to Check & Perform all bootstrap related activity.
"""

__author__ = 'Sumit Sharma'
__copyright__ = 'Copyright 2022, Luna2 Project'
__license__ = 'GPL'
__version__ = '2.0'
__maintainer__ = 'Sumit Sharma'
__email__ = 'sumit.sharma@clustervision.com'
__status__ = 'Development'

from common.dbcheck import checkdbstatus
from configparser import RawConfigParser
from pathlib import Path
import hostlist
import sys
import os
import ipaddress
import time
from utils.database import *


configParser = RawConfigParser()
Bootstrap = False
BootStrapFile = "/trinity/local/luna/config/bootstrap.ini"
BootStrapFilePath = Path(BootStrapFile)


bootstrap_file, database_ready, error = False, False, False
error_message = []

if BootStrapFilePath.is_file():
    print(f'INFO :: Bootstrap file is present {BootStrapFile}.')
    if os.access(BootStrapFile, os.R_OK):
        print(f'INFO :: Bootstrap file is readable {BootStrapFile}.')
        bootstrap_file = True
    else:
        print(f'ERROR :: Bootstrap file is not readable {BootStrapFile}.')

if bootstrap_file:
    checkdb, code = checkdbstatus()
    if checkdb["read"] == True and checkdb["write"] == True:
        print(f'INFO :: Database {checkdb["database"]} READ WRITE Check TRUE.')
        table = ["cluster", "bmcsetup", "group", "groupinterface", "groupsecrets",
                 "network", "osimage", "switch", "tracker", "node", "nodeinterface", "nodesecrets"]
        num = 0
        for tableX in table:
            result = Database().get_record(None, tableX, None)
            if result is None:
                error = True
                error_message.append(f'Database table {tableX} already have data.')
            if result:
                num = num+1
        if num == 0:
            print(f'INFO :: Database {checkdb["database"]} Is Empty and Daemon Ready for BootStrapping.')
            database_ready = True
        else:
            print(f'INFO :: Database {checkdb["database"]} Already Filled with Data.')
    else:
        print(f'ERROR :: Database {checkdb["database"]} READ {checkdb["read"]} WRITE {checkdb["write"]} Is not correct.')

BOOTSTRAP = {
    'HOSTS': {'HOSTNAME': None, 'CONTROLLER1': None, 'CONTROLLER2': None, 'NODELIST': None},
    'NETWORKS': {'INTERNAL': None, 'BMC': None, 'IB': None},
    'GROUPS': {'NAME': None},
    'OSIMAGE': {'NAME': None},
    'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}
}


def checksection():
    for item in list(BOOTSTRAP.keys()):
        if item not in configParser.sections():
            error = True
            error_message.append(f'ERROR :: Section {item} Is Missing, Kindly Check The File {filename}.')


def checkoption(each_section):
    for item in list(BOOTSTRAP[each_section].keys()):
        if item.lower() not in list(dict(configParser.items(each_section)).keys()):
            error = True
            error_message.append(f'ERROR :: Section {each_section} Do not Have Option {each_key.upper()}, Kindly Check The File {filename}.')


def getconfig(filename=None):
    configParser.read(filename)
    checksection()
    for each_section in configParser.sections():
        for (each_key, each_val) in configParser.items(each_section):
            globals()[each_key.upper()] = each_val
            if each_section in list(BOOTSTRAP.keys()):
                checkoption(each_section)
                if 'CONTROLLER1' in each_key.upper():
                    check_ip(each_val)
                    BOOTSTRAP[each_section][each_key.upper()] = each_val
                elif 'CONTROLLER' in each_key.upper() and 'CONTROLLER1' not in each_key.upper():
                    if "." in each_val:
                        check_ip(each_val)
                        BOOTSTRAP[each_section][each_key.upper()] = each_val
                    else:
                        # BOOTSTRAP[each_section].pop(each_key.upper())
                        del BOOTSTRAP[each_section][each_key.upper()]
                elif 'NODELIST' in each_key.upper():
                    try:
                        each_val = hostlist.expand_hostlist(each_val)
                        BOOTSTRAP[each_section][each_key.upper()] = each_val
                    except Exception as exp:
                        error = True
                        error_message.append(f'Invalid Node List range: {each_val}, Kindly use the Numbers in incremental order.')
                elif 'NETWORKS' in each_section:
                    check_ip_network(each_val)
                    BOOTSTRAP[each_section][each_key.upper()] = each_val
                else:
                    BOOTSTRAP[each_section][each_key.upper()] = each_val
            else:
                BOOTSTRAP[each_section] = {}
                BOOTSTRAP[each_section][each_key.upper()] = each_val

def check_ip(ipaddr):
    try:
        ip = ipaddress.ip_address(ipaddr)
    except Exception as exp:
        error = True
        error_message.append(f'Invalid IP Address: {ipaddr}.')


def check_ip_network(ipaddr):
    try:
        subnet = ipaddress.ip_network(ipaddr)
    except Exception as exp:
        error = True
        error_message.append(f'Invalid Subnet: {ipaddr} .')


def bootstrap():
    print('###################### Bootstrap Start ######################')
    """
    DELETE FROM "controller";
    DELETE FROM "cluster";
    DELETE FROM "bmcsetup";
    DELETE FROM "group";
    DELETE FROM "groupinterface";
    DELETE FROM "groupsecrets";
    DELETE FROM "network";
    DELETE FROM "osimage";
    DELETE FROM "switch";
    DELETE FROM "tracker";
    DELETE FROM "node";
    DELETE FROM "nodeinterface";
    DELETE FROM "nodesecrets";
    """
    num  = 1
    for hosts in BOOTSTRAP["HOSTS"]:
        if "CONTROLLER"+str(num) in BOOTSTRAP["HOSTS"].keys():
            default_controller = [{"column": "ipaddr", "value": BOOTSTRAP["HOSTS"]["CONTROLLER"+str(num)]}]
            result = Database().insert("controller", default_controller)
        num = num + 1
    for NodeX in BOOTSTRAP["HOSTS"]["NODELIST"]:
        default_node = [
                {"column": "name", "value": str(NodeX)},
                {"column": "localboot", "value": "0"},
                {"column": "service", "value": "0"},
                {"column": "setupbmc", "value": "1"},
                {"column": "localinstall", "value": "0"},
                {"column": "bootmenu", "value": "0"},
                {"column": "netboot", "value": "1"},
                {"column": "provisionmethod", "value": "torrent"},
                {"column": "provisionfallback", "value": "http"}
            ]
        result = Database().insert("node", default_node)
    for NetworkX in BOOTSTRAP["NETWORKS"].keys():
        default_network = [
                {"column": "name", "value": str(NetworkX)},
                {"column": "network", "value": str(BOOTSTRAP["NETWORKS"][NetworkX])},
                {"column": "dhcp", "value": "0"},
                {"column": "nshostname", "value": "controller_hostname"},
                {"column": "nsip", "value": "controller_ip"},
                {"column": "gateway", "value": "controller_ip"},
                {"column": "ntp_server", "value": "controller_ip"}
            ]
        result = Database().insert("network", default_network)
    default_group = [
            {"column": "name", "value": str(BOOTSTRAP["GROUPS"]["NAME"])},
            {"column": "bmcsetup", "value": "1"},
            {"column": "domain", "value": "cluster"},
            {"column": "netboot", "value": "1"},
            {"column": "localinstall", "value": "0"},
            {"column": "bootmenu", "value": "0"},
            {"column": "provisionmethod", "value": "torrent"},
            {"column": "provisionfallback", "value": "http"}
        ]

    default_group_interface = [
            {"column": "groupid", "value": "1"},
            {"column": "interfacename", "value": "BOOTIF"}
        ]

    default_osimage = [
            {"column": "name", "value": str(BOOTSTRAP["OSIMAGE"]["NAME"])},
            {"column": "dracutmodules", "value": "luna, -18n, -plymouth"},
            {"column": "grabfilesystems", "value": "/, /boot"},
            {"column": "initrdfile", "value": "osimagename-initramfs-`uname -r`"},
            {"column": "kernelfile", "value": "osimagename-vmlinuz-`uname -r`"},
            {"column": "kernelmodules", "value": "ipmi_devintf, ipmi_si, ipmi_msghandler"},
            {"column": "distribution", "value": "redhat"}
        ]
    
    default_bmcsetup = [
            {"column": "username", "value": str(BOOTSTRAP["BMCSETUP"]["USERNAME"])},
            {"column": "password", "value": str(BOOTSTRAP["BMCSETUP"]["PASSWORD"])}
        ]
    

    default_cluster = [
            {"column": "technicalcontacts", "value": "root@localhost"},
            {"column": "provisionmethod", "value": "torrent"},
            {"column": "provisionfallback", "value": "http"},
            {"column": "security", "value": "1"},
            {"column": "debug", "value": "0"}
        ]
    

    default_switch = [
            {"column": "oid", "value": ".1.3.6.1.2.1.17.7.1.2.2.1.2"},
            {"column": "read", "value": "public"},
            {"column": "rw", "value": "private"}
            ]
    result = Database().insert("group", default_group)
    result = Database().insert("groupinterface", default_group_interface)
    result = Database().insert("osimage", default_osimage)
    result = Database().insert("bmcsetup", default_bmcsetup)
    result = Database().insert("cluster", default_cluster)
    result = Database().insert("switch", default_switch)



    TIME = str(time.time()).replace(".", "")
    BootStrapNewFile = f"/trinity/local/luna/config/bootstrap-{TIME}.ini"
    os.rename(BootStrapFile, BootStrapNewFile)
    print('###################### Bootstrap Finish ######################')


def checkbootstrap():
    if error:
        print('###################### Bootstrap Error(s) ######################')
        for ERR in error_message:
            print(ERR)
        print('###################### Bootstrap Error(s) ######################')
        return None
    elif bootstrap_file:
        getconfig(BootStrapFile)
        bootstrap()
    else:
        return True