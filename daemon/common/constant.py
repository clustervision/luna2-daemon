#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

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
This File is responsible to fetch each variable configured in config/luna.ini.
Import this file will provide all variables which is fetched here.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import shutil
import sys
import subprocess
import json
from configparser import RawConfigParser
from pathlib import Path
from utils.log import Log

# not here..... further down as we load the path for the log file - Antoine Aug 11 2023
#LOGGER = Log.init_log('info', '/trinity/local/luna/log/luna2-daemon.log')
CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
configParser = RawConfigParser()
CONFIGFILE = '/trinity/local/luna/daemon/config/luna.ini'

def check_path_state(path=None):
    """
    Input - Directory
    Output - Directory if exists, readable or writable
    """
    path_check = False
    pathtype = check_path_type(path)
    if pathtype in ('File', 'Directory'):
        if os.access(path, os.R_OK):
            if os.access(path, os.W_OK):
                path_check = True
            else:
                LOGGER = Log.init_log('info')
                LOGGER.error(f'{pathtype} {path} is writable')
        else:
            LOGGER = Log.init_log('info')
            LOGGER.error(f'{pathtype} {path} is not readable')
    else:
        LOGGER = Log.init_log('info')
        LOGGER.error(f'{pathtype} {path} does not exist')
    return path_check


def check_path_type(path=None):
    """
    Input - Path of File or Directory
    Output - File or directory or Not Exists
    """
    pathstatus = check_path(path)
    if pathstatus:
        if os.path.isdir(path):
            response = 'File'
        elif os.path.isfile(path):
            response = 'Directory'
        else:
            response = 'socket or FIFO or device'
    else:
        response = 'Not exists'
    return response


def check_path(path=None):
    """
    Input - Path of File or Directory
    Output - True or False Is exists or not
    """
    if not path:
        return False
    if os.path.exists(path):
        return True
    return False

def runcommand(command):
    """
    Input - command, which need to be executed
    Process - Via subprocess, execute the command and wait to receive the complete output.
    Output - Detailed result.
    """
    with subprocess.Popen(command, stdout=subprocess.PIPE, shell=True) as process:
        LOGGER.debug(f'Command Executed {command}')
        output = process.communicate()
        process.wait()
        LOGGER.debug(f'Output Of Command {output}')
    return output

def getlist(dictionary):
    """
    Get Section List
    """
    key_list = []
    for key in dictionary.keys():
        key_list.append(key)
    return key_list

def check_section(filename=None):
    """
    Compare the ini section with the predefined dictionary sections.
    """
    for item in list(CONSTANT.keys()):
        if item not in configParser.sections():
            LOGGER.error(f'Section {item} is missing, kindly check the file {filename}.')


def check_option(filename, section, option=None):
    """
    Compare the ini option with the predefined dictionary options.
    """

    if option:
        if option.lower() not in list(dict(configParser.items(section)).keys()):
            try:
                LOGGER.error(f'{option} is not available in {section}, please check {filename}.')
            except:
                # getconfig + check_option are needed to read config file to know where to store logs
                # this then inits logger. it's a chicken egg problem. unsolvable - Antoine sep 20 2023
                sys.stderr.write(f"{option} is not available in {section}, please check {filename}\n")
    else:
        if section in CONSTANT.keys():
            for item in list(CONSTANT[section].keys()):
                if item.lower() not in list(dict(configParser.items(section)).keys()):
                    try:
                        LOGGER.error(f'{item} is not available in {section}, please check {filename}.')
                    except:
                        # getconfig + check_option are needed to read config file to know where to store logs
                        # this then inits logger. it's a chicken egg problem. unsolvable - Antoine sep 20 2023
                        sys.stderr.write(f"{item} is not available in {section}, please check {filename}\n")


def set_constants(section=None, option=None, item=None):
    """
    This method set the value in the Constant.
    """
    if option == 'EXPIRY':
        if item:
            CONSTANT[section][option] = int(item.replace('h', ''))*60*60
        else:
            CONSTANT[section][option] = 24*60*60
    elif option.upper() == 'COOLDOWN':
        if item:
            CONSTANT[section][option] = int(item.replace('s', ''))
        else:
            CONSTANT[section][option] = 2
    elif option.upper() == 'MAXPACKAGINGTIME':
        if item:
            CONSTANT[section][option] = int(item.replace('m', ''))*60
        else:
            CONSTANT[section][option] = 10*60
    elif option.upper() == 'BMC_BATCH_DELAY':
        if item:
            CONSTANT[section][option] = int(item.replace('s', ''))
        else:
            CONSTANT[section][option] = 1
    else:
        CONSTANT[section][option] = item
    return CONSTANT


def getconfig(filename=None):
    """
    From ini file Section Name is section here, Option Name is option here
    and Option Value is item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST], and vlaues
    of options are item(10.141.255.254, node[001-004])
    """
    configParser.read(filename)
    check_section(filename)
    for section in configParser.sections():
        check_option(filename, section)
        for (option, item) in configParser.items(section):
            if section in getlist(CONSTANT):
                set_constants(section, option.upper(), item)
            else:
                CONSTANT[section] = {}
                CONSTANT[section][option.upper()] = item


global CONSTANT
global LUNAKEY

CONSTANT = {
    'LOGGER': {'LEVEL': None, 'LOGFILE': None},
    'API': {'USERNAME': None, 'PASSWORD': None, 'EXPIRY': None, 'SECRET_KEY': None, 'ENDPOINT': None, 'PROTOCOL': None},
    'DATABASE': {'DRIVER': None, 'DATABASE': None, 'DBUSER': None,
                'DBPASSWORD': None, 'HOST': None, 'PORT': None},
    'FILES': {'KEYFILE': None, 'IMAGE_FILES': None, 'IMAGE_DIRECTORY': None, 'MAXPACKAGINGTIME': None, 'TMP_DIRECTORY': None},
    'PLUGINS':  {'PLUGINS_DIRECTORY': None, 'IMAGE_FILESYSTEM': None},
    'SERVICES': {'DHCP': None, 'DNS': None, 'CONTROL': None, 'COOLDOWN': None, 'COMMAND': None},
    'DHCP': {'OMAPIKEY': None},
    'BMCCONTROL': {'BMC_BATCH_SIZE': None, 'BMC_BATCH_DELAY': None},
    'TEMPLATES': {'TEMPLATE_FILES': None, 'TEMPLATE_LIST': None,  'TMP_DIRECTORY': None}
}

if check_path_state(CONFIGFILE):
    getconfig(CONFIGFILE)
else:
    LOGGER = Log.init_log('info')
    LOGGER.error(f'Unable to get configurations from {CONFIGFILE} file')


## Sanity Checks On LOGFILE, IMAGE_FILES, TEMPLATE_FILES, TEMPLATE_LIST, KEYFILE

# the log path, not the file. we can create the file very well by ourselves... - Antoine aug 11 2023
logpath = os.path.dirname(CONSTANT['LOGGER']['LOGFILE'])

sanitize = [
#                CONSTANT['LOGGER']['LOGFILE'],
                logpath,
                CONSTANT['FILES']['IMAGE_FILES'],
                CONSTANT['TEMPLATES']['TEMPLATE_FILES'],
                CONSTANT['TEMPLATES']['TEMPLATE_LIST'],
                CONSTANT['PLUGINS']['PLUGINS_DIRECTORY'],
                CONSTANT['FILES']['KEYFILE']
            ]
for sanity in sanitize:
    check_path_state(sanity)

if CONSTANT['LOGGER']['LOGFILE']:
    #os.makedirs(logpath, exist_ok=True)  # <-- debatable - Antoine
    LOGGER = Log.init_log('info', CONSTANT['LOGGER']['LOGFILE'])
if CONSTANT['LOGGER']['LEVEL']:
    LOGGER = Log.set_logger(CONSTANT['LOGGER']['LEVEL'])


with open(CONSTANT['FILES']['KEYFILE'], 'r', encoding='utf-8') as key_file:
    LUNAKEY = key_file.read()
    LUNAKEY = LUNAKEY.replace('\n', '')

with open(CONSTANT['TEMPLATES']['TEMPLATE_LIST'], 'r', encoding='utf-8') as template_json:
    data = json.load(template_json)
if 'files' in data.keys():
    if len(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"]) > 1 and os.path.exists(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"]):
        shutil.rmtree(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"])
    if not os.path.exists(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"]):
        os.makedirs(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"])
    if not os.path.exists(CONSTANT["TEMPLATES"]["TMP_DIRECTORY"]):
        LOGGER.error(f"Cannot create directory {CONSTANT['TEMPLATES']['TMP_DIRECTORY']}")
    else:
        for templatefiles in data['files']:
            if check_path_state(f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{templatefiles}'):
                copy_source = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{templatefiles}'
                copy_destination = f'{CONSTANT["TEMPLATES"]["TMP_DIRECTORY"]}/{templatefiles}'
                shutil.copyfile(copy_source, copy_destination)
            else:
                error_msg = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{templatefiles} is not writable'
                LOGGER.error(error_msg)
else:
    LOGGER.error(f'{CONSTANT["TEMPLATES"]["TEMPLATE_LIST"]} have no files')



##### TODO
##
## Add Template Variables in CONSTANT["TEMPLATES"]["VARS"] = {LUNA_CONTROLLER: cluster.nameserver_ip , LUNA_API_PORT: cluster.port}
## When Read Templates get the variable name from there and match with CONSTANTS Variables and get db table and field name
## Fetch the exact column value base on the above logic
## Render the template with that value(s)
## Can also create a API or Method to change and add the variable name or value to the CONSTANTS (Problem But it requires a luna2-daemon service restart)

CONSTANT["TEMPLATES"]["VARS"] = {
    'LUNA_CONTROLLER': 'controller.ipaddr',
    'LUNA_API_PORT': 'controller.srverport',
    'asda': 'we.cv'
    }
