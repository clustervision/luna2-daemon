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
        num = 0  # >>>>>>>>>>>>>>>>>>>..... REMOVE THIS LINE AFTER DEVELOPMENT
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
                BOOTSTRAP[each_section][each_key.upper()] = each_val
            else:
                BOOTSTRAP[each_section] = {}
                BOOTSTRAP[each_section][each_key.upper()] = each_val


def checkbootstrap():
    if bootstrap_file:
        getconfig(BootStrapFile)
        print(BOOTSTRAP)
    else:
        return True


# >>>>>>>>>>............ Database Insert Activity; Still not Finalize
# table = ["cluster", "bmcsetup", "group", "groupinterface", "groupsecrets", "network", "osimage", "switch", "tracker", "node", "nodeinterface", "nodesecrets"]
# for x in table:
# 	row = [{"column": "name", "value": "node004"}, {"column": "ip", "value": "10.141.0.1"}]
# 	result = Database().insert(x, row)
# 	if result is None:
# 		sys.exit(0)

# Rename bootstrap.ini file to bootstrap-time().ini

# >>>>>>>>>>............ Database Insert Activity; Still not Finalize


# if __name__ == '__main__':
#     checkbootstrap()
