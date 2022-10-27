#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is responsible to Check & Perform all bootstrap related activity.
"""

from common.dbcheck import checkdbstatus
from configparser import RawConfigParser
from pathlib import Path
import hostlist
import sys
import os
import ipaddress
import time
from utils.database import *
__author__ = 'Sumit Sharma'
__copyright__ = 'Copyright 2022, Luna2 Project'
__license__ = 'GPL'
__version__ = '2.0'
__maintainer__ = 'Sumit Sharma'
__email__ = 'sumit.sharma@clustervision.com'
__status__ = 'Development'


configParser = RawConfigParser()
# from utils.log import Log
# logger = Log.get_logger()
Bootstrap = False
# >>>>>>............. DEVELOPMENT PURPOSE ------>> Remove Line 20 and 21 When Feature is Developed, And Uncomment Next Line --> BootStrapFile
# BootStrapFile = '/trinity/local/luna/config/bootstrapDEV.ini'
# >>>>>>............. DEVELOPMENT PURPOSE
BootStrapFile = "/trinity/local/luna/config/bootstrap.ini"
BootStrapFilePath = Path(BootStrapFile)


bootstrap_file, database_ready = False, False

if BootStrapFilePath.is_file():
    print(f'INFO :: Bootstrp file is present {BootStrapFile}.')
    if os.access(BootStrapFile, os.R_OK):
        print(f'INFO :: Bootstrp file is readable {BootStrapFile}.')
        bootstrap_file = True
    else:
        print(f'ERROR :: Bootstrp file is not readable {BootStrapFile}.')

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
                sys.exit(0)
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
    'HOSTS': {'CONTROLLER1': None, 'CONTROLLER2': None, 'NODELIST': None},
    'NETWORKS': {'INTERNAL': None, 'BMC': None, 'IB': None},
    'GROUPS': {'NAME': None},
    'OSIMAGE': {'NAME': None},
    'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}
}


def checksection():
    for item in list(BOOTSTRAP.keys()):
        if item not in configParser.sections():
            print(
                f'ERROR :: Section {item} Is Missing, Kindly Check The File {filename}.')
            sys.exit(0)


def checkoption(each_section):
    for item in list(BOOTSTRAP[each_section].keys()):
        if item.lower() not in list(dict(configParser.items(each_section)).keys()):
            print(
                f'ERROR :: Section {each_section} Do not Have Option {each_key.upper()}, Kindly Check The File {filename}.')
            sys.exit(0)


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
                    except Exception as e:
                        print("Invalid Node List range: {}, Kindly use the Numbers in incremental order.".format(each_val))
                        sys.exit(0)
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
    except Exception as e:
        print("Invalid IP Address: {} ".format(ipaddr))
        sys.exit(0)


def check_ip_network(ipaddr):
    try:
        subnet = ipaddress.ip_network(ipaddr)
    except Exception as e:
        print("Invalid Subnet: {} ".format(ipaddr))
        sys.exit(0)




def bootstrap():
    print("Ruuning Bootstrap")
    print(BOOTSTRAP)
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
    for x in BOOTSTRAP["HOSTS"]:
        if "CONTROLLER"+str(num) in BOOTSTRAP["HOSTS"].keys():
            row = [{"column": "ipaddr", "value": BOOTSTRAP["HOSTS"]["CONTROLLER"+str(num)]}]
            result = Database().insert("controller", row)
        num = num + 1
    for NodeX in BOOTSTRAP["HOSTS"]["NODELIST"]:
        row = [{"column": "name", "value": str(NodeX)}]
        result = Database().insert("node", row)
    for NetworkX in BOOTSTRAP["NETWORKS"].keys():
        row = [{"column": "name", "value": str(NetworkX)},{"column": "network", "value": str(BOOTSTRAP["NETWORKS"][NetworkX])}]
        result = Database().insert("network", row)
    row = [{"column": "name", "value": str(BOOTSTRAP["GROUPS"]["NAME"])}]
    result = Database().insert("group", row)
    row = [{"column": "name", "value": str(BOOTSTRAP["OSIMAGE"]["NAME"])}]
    result = Database().insert("osimage", row)
    row = [{"column": "username", "value": str(BOOTSTRAP["BMCSETUP"]["USERNAME"])}, {"column": "password", "value": str(BOOTSTRAP["BMCSETUP"]["PASSWORD"])}]
    result = Database().insert("bmcsetup", row)
    TIME = str(time.time()).replace(".", "")
    BootStrapNewFile = f"/trinity/local/luna/config/bootstrap-{TIME}.ini"
    os.rename(BootStrapFile, BootStrapNewFile)
    print("Finish Bootstrap")


# def checkbootstrap():
if bootstrap_file:
    getconfig(BootStrapFile)
    bootstrap()
# else:
#     return True

# >>>>>>>>>>............ Database Insert Activity; Still not Finalize


# if __name__ == '__main__':
#     checkbootstrap()
