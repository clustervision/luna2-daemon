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
        print(f'INFO :: Database {checkdb["database"]} READ WRITE check TRUE.')
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
            print(f'INFO :: Database {checkdb["database"]} is empty and daemon ready for bootstrap.')
            database_ready = True
        else:
            print(f'INFO :: Database {checkdb["database"]} already filled with data.')
    else:
        print(f'ERROR :: Database {checkdb["database"]} READ {checkdb["read"]} WRITE {checkdb["write"]} is not correct.')

BOOTSTRAP = {
    'HOSTS': {'HOSTNAME': None, 'CONTROLLER1': None, 'CONTROLLER2': None, 'NODELIST': None},
    'NETWORKS': {'INTERNAL': None, 'BMC': None, 'IB': None},
    'GROUPS': {'NAME': None},
    'OSIMAGE': {'NAME': None},
    'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}
}


def checksection():
    """
    Compare bootstrap section with the predefined dictionary sections.
    """
    for item in list(BOOTSTRAP.keys()):
        if item not in configParser.sections():
            error = True
            error_message.append(f'ERROR :: Section {item} is missing, kindly check the file {filename}.')


def checkoption(section):
    """
    Compare bootstrap option with the predefined dictionary optionss.
    """
    for item in list(BOOTSTRAP[section].keys()):
        if item.lower() not in list(dict(configParser.items(section)).keys()):
            error = True
            error_message.append(f'ERROR :: Section {section} do not have option {option.upper()}, kindly check the file {filename}.')


def getconfig(filename=None):
    """
    From ini file Section Name is section here, Option Name is option here and Option Value is item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST], and vlaues of options are item(10.141.255.254, node[001-004])
    """
    configParser.read(filename)
    checksection()
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            globals()[option.upper()] = item
            if section in list(BOOTSTRAP.keys()):
                checkoption(section)
                if 'CONTROLLER1' in option.upper():
                    check_ip(item)
                    BOOTSTRAP[section][option.upper()] = item
                elif 'CONTROLLER' in option.upper() and 'CONTROLLER1' not in option.upper():
                    if "." in item:
                        check_ip(item)
                        BOOTSTRAP[section][option.upper()] = item
                    else:
                        del BOOTSTRAP[section][option.upper()]
                elif 'NODELIST' in option.upper():
                    try:
                        item = hostlist.expand_hostlist(item)
                        BOOTSTRAP[section][option.upper()] = item
                    except Exception as exp:
                        error = True
                        error_message.append(f'Invalid node list range: {item}, kindly use the numbers in incremental order.')
                elif 'NETWORKS' in section:
                    check_ip_network(item)
                    BOOTSTRAP[section][option.upper()] = item
                else:
                    BOOTSTRAP[section][option.upper()] = item
            else:
                BOOTSTRAP[section] = {}
                BOOTSTRAP[section][option.upper()] = item

def check_ip(ipaddr):
    """
    Check if IP address is a valid IP or not.
    """
    check = False
    try:
        ip = ipaddress.ip_address(ipaddr)
        check = True
    except Exception as exp:
        error = True
        error_message.append(f'Invalid IP address: {ipaddr}.')
    return check


def check_ip_network(ipaddr):
    """
    Check if the subnets are correct.
    """
    check = False
    try:
        subnet = ipaddress.ip_network(ipaddr)
        check = True
    except Exception as exp:
        error = True
        error_message.append(f'Invalid subnet: {ipaddr}.')
    return check


def bootstrap():
    """
    Insert default data into the database.
    """
    print('###################### Bootstrap Start ######################')
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
    return True


def checkbootstrap():
    """
    Main method, should be called from outside.
    To perform and check the bootstrap.
    """
    bootstarping = None
    if error:
        print('###################### Bootstrap Error(s) ######################')
        for ERR in error_message:
            print(ERR)
        print('###################### Bootstrap Error(s) ######################')
    elif bootstrap_file:
        getconfig(BootStrapFile)
        bootstrap()
        bootstarping = True
    return bootstarping