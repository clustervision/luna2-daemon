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
import subprocess
import json
from configparser import RawConfigParser
from pathlib import Path
from utils.log import Log

LOGGER = Log.init_log('info', '/trinity/local/luna/log/luna2-daemon.log')
CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
configParser = RawConfigParser()
CONFIGFILE = '/trinity/local/luna/config/luna.ini'

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
                LOGGER.error(f'{pathtype} {path} is writable.')
        else:
            LOGGER.error(f'{pathtype} {path} is not readable.')
    else:
        LOGGER.error(f'{pathtype} {path} is not exists.')
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
    if os.path.exists(path):
        response = True
    else:
        response = None
    return response

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

def checksection(filename=None):
    """
    Compare the ini section with the predefined dictionary sections.
    """
    for item in list(CONSTANT.keys()):
        if item not in configParser.sections():
            LOGGER.error(f'Section {item} is missing, kindly check the file {filename}.')


def check_option(filename=None, section=None, option=None):
    """
    Compare the ini option with the predefined dictionary options.
    """
    for item in list(CONSTANT[section].keys()):
        if item.lower() not in list(dict(configParser.items(section)).keys()):
            LOGGER.error(f'{option} is not available in {section}, kindly check {filename}.')

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
    checksection(filename)
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            if section in getlist(CONSTANT):
                check_option(filename, section, option.upper())
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
    'FILES': {'KEYFILE': None, 'IMAGE_FILES': None, 'IMAGE_DIRECTORY': None, 'MAXPACKAGINGTIME': None},
    'SERVICES': {'DHCP': None, 'DNS': None, 'CONTROL': None, 'COOLDOWN': None, 'COMMAND': None},
    'DHCP': {'OMAPIKEY': None},
    'BMCCONTROL': {'BMC_BATCH_SIZE': None, 'BMC_BATCH_DELAY': None},
    'TEMPLATES': {'TEMPLATES_DIR': None, 'TEMPLATELIST': None,  'TEMP_DIR': None}
}


if check_path_state(CONFIGFILE):
    getconfig(CONFIGFILE)
else:
    LOGGER.error(f'Unable to get configurations from {CONFIGFILE} file')


## Sanity Checks On LOGFILE, IMAGE_FILES, TEMPLATES_DIR, TEMPLATELIST, KEYFILE

sanitize = [
                CONSTANT['LOGGER']['LOGFILE'],
                CONSTANT['FILES']['IMAGE_FILES'],
                CONSTANT['TEMPLATES']['TEMPLATES_DIR'],
                CONSTANT['TEMPLATES']['TEMPLATELIST'],
                CONSTANT['FILES']['KEYFILE']
            ]
for sanity in sanitize:
    check_path_state(sanity)

if CONSTANT['LOGGER']['LEVEL']:
    LOGGER = Log.set_logger(CONSTANT['LOGGER']['LEVEL'])

with open(CONSTANT['FILES']['KEYFILE'], 'r', encoding='utf-8') as key_file:
    LUNAKEY = key_file.read()
    LUNAKEY = LUNAKEY.replace('\n', '')

with open(CONSTANT['TEMPLATES']['TEMPLATELIST'], 'r', encoding='utf-8') as template_json:
    data = json.load(template_json)
if 'files' in data.keys():
    runcommand(f'rm -rf {CONSTANT["TEMPLATES"]["TEMP_DIR"]}')
    runcommand(f'mkdir {CONSTANT["TEMPLATES"]["TEMP_DIR"]}')
    for templatefiles in data['files']:
        if check_path_state(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles}'):
            copy_source = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles}'
            copy_destination = f'{CONSTANT["TEMPLATES"]["TEMP_DIR"]}'
            runcommand(f'cp {copy_source} {copy_destination}')
        else:
            error_msg = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} is not present.'
            LOGGER.error(error_msg)
else:
    LOGGER.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} have no files.')



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
