#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
This File is responsible to fetch each variable configured in config/luna.ini.
Import this file will provide all variables which is fetched here.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'



import os
import sys
from configparser import RawConfigParser
from pathlib import Path

global CONSTANT
CONSTANT = {
	'LOGGER': { 'LEVEL': None, 'LOGFILE': None },
	'API': { 'USERNAME': None, 'PASSWORD': None, 'EXPIRY': None },
	'DATABASE': { 'DRIVER': None, 'DATABASE': None, 'DBUSER': None, 'DBPASSWORD': None, 'HOST': None, 'PORT': None },
	'FILES': { 'TARBALL': None },
	'SERVICES': { 'DHCP': None, 'DNS': None, 'CONTROL': None, 'COOLDOWN': None, 'COMMAND': None },
	'TEMPLATES': { 'TEMPLATES_DIR': None }
}

CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
SECRET_KEY = '004f2af45d3a4e161a7dd2d17fdae47f'
configParser = RawConfigParser()

ConfigFile = '/trinity/local/luna/config/luna.ini'

"""
Input - Filename
Output - Check File Existence And Readability
"""
def checkfile(filename=None):
    ConfigFilePath = Path(filename)
    if ConfigFilePath.is_file():
        if os.access(filename, os.R_OK):
            return True
        else:
            print('File {} Is Not readable.'.format(filename))
    else:
        print('File {} Is Abesnt.'.format(filename))
    return False

def checksection():
    for item in list(CONSTANT.keys()):
        if item not in configParser.sections():
            print('ERROR :: Section {} Is Missing, Kindly Check The File {}.'.format(item, filename))
            sys.exit(0)


def checkoption(each_section):
    for item in list(CONSTANT[each_section].keys()):
        if item.lower() not in list(dict(configParser.items(each_section)).keys()):
            print('ERROR :: Section {} Do not Have Option {}, Kindly Check The File {}.'.format(each_section, each_key.upper(), filename))
            sys.exit(0)

def getconfig(filename=None):
    configParser.read(filename)
    checksection()
    for each_section in configParser.sections():
        for (each_key, each_val) in configParser.items(each_section):
            globals()[each_key.upper()] = each_val
            if each_section in list(CONSTANT.keys()):
                checkoption(each_section)
                if each_key.upper() == 'EXPIRY':
                    if each_val:
                        CONSTANT[each_section][each_key.upper()] = int(each_val.replace('h', ''))*60*60
                    else:
                        CONSTANT[each_section][each_key.upper()] = 24*60*60
                elif each_key.upper() == 'COOLDOWN':
                    if each_val:
                        CONSTANT[each_section][each_key.upper()] = int(each_val.replace('s', ''))
                    else:
                        CONSTANT[each_section][each_key.upper()] = 2
                else:
                    CONSTANT[each_section][each_key.upper()] = each_val
            else:
                CONSTANT[each_section] = {}
                CONSTANT[each_section][each_key.upper()] = each_val

file_check = checkfile(ConfigFile)
if file_check:
	getconfig(ConfigFile)
	# LOGGER = Log.init_log(CONSTANT['LOGGER']['LEVEL'])
else:
	sys.exit(0)


"""
Input - Directory
Output - Directory Existence, Readability and Writable
"""
def checkdir(directory=None):
    if os.path.exists(directory):
        if os.access(directory, os.R_OK):
            if os.access(directory, os.W_OK):
                return True
            else:
                print('Directory {} Is Writable.'.format(directory))
        else:
            print('Directory {} Is Not readable.'.format(directory))
    else:
        print('Directory {} Is Not exists.'.format(directory))
    return False


"""
Input - Filename and Default File True or False
Output - Check If File Writable
"""
def checkwritable(filename=None):
	write = False
	try:
		file = open(filename, 'a')
		if file.writable():
			write = True
	except Exception as e:
		print('File {} is Not Writable.'.format(filename))
	return write


"""
Sanity Checks On LOGFILE, TARBALL, TEMPLATES_DIR
"""
### TODO -> Create Universal method for exit, before exit, send message, exit code should be "-1"

check_log_read = checkfile(LOGFILE)
if check_log_read is not True:
    print('Log File: {} Is Not Readable.'.format(LOGFILE))
    sys.exit(-1)

check_log_write = checkwritable(LOGFILE)
if check_log_write is not True:
    print('Log File: {} Is Not Writable.'.format(LOGFILE))
    sys.exit(0)

check_dir_read = checkdir(TARBALL)
if check_dir_read is not True:
    print('TARBALL Directory: {} Is Not Readable.'.format(TARBALL))
    sys.exit(0)

check_dir_write = checkdir(TARBALL)
if check_dir_write is not True:
    print('TARBALL Directory: {} Is Not Writable.'.format(TARBALL))
    sys.exit(0)

check_dir_read = checkdir(TEMPLATES_DIR)
if check_dir_read is not True:
    print('TEMPLATES_DIR Directory: {} Is Not Readable.'.format(TEMPLATES_DIR))
    sys.exit(0)

check_dir_write = checkdir(TEMPLATES_DIR)
if check_dir_write is not True:
    print('TEMPLATES_DIR Directory: {} Is Not Writable.'.format(TEMPLATES_DIR))
    sys.exit(0)

# check_boot_ipxe_read = checkfile(TEMPLATES_DIR+'/boot_ipxe.cfg')
# if check_boot_ipxe_read is not True:
#     print('Boot PXE File: {} Is Not Readable.'.format(TEMPLATES_DIR+'/boot_ipxe.cfg'))
#     sys.exit(0)

# check_boot_ipxe_write = checkwritable(TEMPLATES_DIR+'/boot_ipxe.cfg')
# if check_boot_ipxe_write is not True:
#     print('Boot PXE File: {} Is Not Writable.'.format(TEMPLATES_DIR+'/boot_ipxe.cfg'))
#     sys.exit(0)

# if check_boot_ipxe_read and check_boot_ipxe_write:
#     with open(TEMPLATES_DIR+'/boot_ipxe.cfg', 'r') as bootfile:
#         bootfile = bootfile.readlines()

######################## SET CRON JOB TO MONITOR ###########################
# cronfile = "/etc/cron.d/luna2-daemon.monitor"
# crondata = "0 * * * * root curl http://127.0.0.1:7050/monitor/service/luna2"
# with open(cronfile, "w") as file:
#     file.write(crondata)
######################## SET CRON JOB TO MONITOR ###########################


