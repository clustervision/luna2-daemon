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
from configparser import RawConfigParser
from pathlib import Path
from utils.log import Log
LOGGER = Log.init_log('debug', '/trinity/local/luna/log/luna2-daemon.log')
# from utils.helper import Helper

def checkfile(filename=None):
    """
    Input - Filename
    Output - Check File Existence And Readability
    """
    check = False
    if Path(filename).is_file():
        if os.access(filename, os.R_OK):
            check = True
        else:
            print(f'File {filename} is not readable.')
    else:
        print(f'File {filename} is absent.')
    return check


def checksection(filename=None):
    """
    Compare the ini section with the predefined dictionary sections.
    """
    for item in list(CONSTANT.keys()):
        if item not in configParser.sections():
            logger.error(f'Section {item} is missing, kindly check the file {filename}.')


def checkoption(filename=None, section=None, option=None):
    """
    Compare the ini option with the predefined dictionary options.
    """
    for item in list(CONSTANT[section].keys()):
        if item.lower() not in list(dict(configParser.items(section)).keys()):
            logger.error(f'Section {section} do not have option {option}, kindly check the file {filename}.')

def getconfig(filename=None):
    """
    From ini file Section Name is section here, Option Name is option here and Option Value is item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST], and vlaues of options are item(10.141.255.254, node[001-004])
    """
    configParser.read(filename)
    checksection(filename)
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            # globals()[option.upper()] = item
            if section in list(CONSTANT.keys()):
                checkoption(filename, section, option.upper())
                if option.upper() == 'EXPIRY':
                    if item:
                        CONSTANT[section][option.upper()] = int(item.replace('h', ''))*60*60
                        globals()[option.upper()] = int(item.replace('h', ''))*60*60
                    else:
                        CONSTANT[section][option.upper()] = 24*60*60
                        globals()[option.upper()] = 24*60*60
                elif option.upper() == 'COOLDOWN':
                    if item:
                        CONSTANT[section][option.upper()] = int(item.replace('s', ''))
                        globals()[option.upper()] = int(item.replace('s', ''))
                    else:
                        CONSTANT[section][option.upper()] = 2
                        globals()[option.upper()] = 2
                elif option.upper() == 'MAXPACKAGINGTIME':
                    if item:
                        CONSTANT[section][option.upper()] = int(item.replace('m', ''))*60
                        globals()[option.upper()] = int(item.replace('m', ''))*60
                    else:
                        CONSTANT[section][option.upper()] = 10*60
                        globals()[option.upper()] = 10*60
                else:
                    CONSTANT[section][option.upper()] = item
                    globals()[option.upper()] = item
            else:
                CONSTANT[section] = {}
                CONSTANT[section][option.upper()] = item


def checkdir(directory=None):
    """
    Input - Directory
    Output - Directory Existence, Readability and Writable
    """
    check = False
    if os.path.exists(directory):
        if os.access(directory, os.R_OK):
            if os.access(directory, os.W_OK):
                check = True
            else:
                print(f'Directory {directory} is writable.')
        else:
            print(f'Directory {directory} is not readable.')
    else:
        print(f'Directory {directory} is not exists.')
    return check


def checkwritable(filename=None):
    """
    Input - Filename and Default File True or False
    Output - Check If File Writable
    """
    write = False
    try:
        file = open(filename, 'a')
        if file.writable():
            write = True
    except Exception as e:
        print('File {} is Not Writable.'.format(filename))
    return write


def get_constants():
    pass

error = False
error_message = []

global CONSTANT
CONSTANT = {
    'LOGGER': { 'LEVEL': None, 'LOGFILE': None },
    'API': { 'USERNAME': None, 'PASSWORD': None, 'EXPIRY': None, 'SECRET_KEY': None },
    'DATABASE': { 'DRIVER': None, 'DATABASE': None, 'DBUSER': None, 'DBPASSWORD': None, 'HOST': None, 'PORT': None },
    'FILES': { 'TARBALL': None, 'IMAGE_DIRECTORY': None, 'MAXPACKAGINGTIME': None },
    'SERVICES': { 'DHCP': None, 'DNS': None, 'CONTROL': None, 'COOLDOWN': None, 'COMMAND': None },
    'TEMPLATES': { 'TEMPLATES_DIR': None, 'TEMPLATELIST': None,  'TEMP_DIR': None }
}

CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
configParser = RawConfigParser()

ConfigFile = '/trinity/local/luna/config/luna.ini'
KEYFILE = '/trinity/local/etc/ssl/luna.key'

file_check = checkfile(ConfigFile)
if file_check:
    getconfig(ConfigFile)
else:
    error = True
    error_message.append(f'ERROR :: Section {section} do not have option {option.upper()}, kindly check the file {filename}.')


if CONSTANT['LOGGER']['LEVEL']:
    # LOGGER = Log.init_log(LEVEL, LOGFILE)
    LOGGER = Log.set_logger(LEVEL)
    print(Log.check_loglevel())


global LUNAKEY
KEYFILECHECK = checkfile(KEYFILE)
if KEYFILECHECK:
    try:
        file = open(KEYFILE, 'r')
        LUNAKEY = file.read()
        LUNAKEY = LUNAKEY.replace('\n', '')
    except Exception as e:
        print('File {} is Not Readable.'.format(KEYFILE))
        LUNAKEY = None




"""
Sanity Checks On LOGFILE, TARBALL, TEMPLATES_DIR
"""

check_log_read = checkfile(LOGFILE)
if check_log_read is not True:
    error = True
    error_message.append(f'Log File: {LOGFILE} is not readable.')

check_log_write = checkwritable(LOGFILE)
if check_log_write is not True:
    error = True
    error_message.append(f'Log File: {LOGFILE} is not writable.')

check_dir_read = checkdir(TARBALL)
if check_dir_read is not True:
    error = True
    error_message.append(f'TARBALL directory: {TARBALL} is not readable.')

check_dir_write = checkdir(TARBALL)
if check_dir_write is not True:
    error = True
    error_message.append(f'TARBALL directory: {TARBALL} is not writable.')

check_dir_read = checkdir(TEMPLATES_DIR)
if check_dir_read is not True:
    error = True
    error_message.append(f'TEMPLATES_DIR directory: {TEMPLATES_DIR} is not readable.')

check_dir_write = checkdir(TEMPLATES_DIR)
if check_dir_write is not True:
    error = True
    error_message.append(f'TEMPLATES_DIR directory: {TEMPLATES_DIR} is not writable.')


# def validate():
#     """
#     Input - None
#     Process - Create TEMP_DIR with template files.
#     Output - Success OR Failure.
#     """
#     temp = False
#     if Helper().checkpathstate(TEMPLATES_DIR) and Helper().checkpathstate(TEMPLATELIST):
#         file = open(TEMPLATELIST, encoding='utf-8')
#         data = json.load(file)
#         file.close()
#         if 'files' in data.keys():
#             Helper().runcommand(f'rm -rf {TEMP_DIR}')
#             Helper().runcommand(f'mkdir {TEMP_DIR}')
#             for templatefiles in data['files']:
#                 if Helper().checkpathstate(f'{TEMPLATES_DIR}/{templatefiles}'):
#                     Helper().runcommand(f'cp {TEMPLATES_DIR}/{templatefiles} /var/tmp/luna2/')
#                     temp = True
#                 else:
#                     logger.error(f'{TEMPLATES_DIR}/{templatefiles} is Not Present.')
#         else:
#             logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} Do Not have file list.')
#     else:
#         logger.error('TEMPLATES_DIR and TEMPLATELIST Not Present in the INI File.')
#     return temp


######################## SET CRON JOB TO MONITOR ###########################
# cronfile = "/etc/cron.d/luna2-daemon.monitor"
# crondata = "0 * * * * root curl http://127.0.0.1:7050/monitor/service/luna2"
# with open(cronfile, "w") as file:
#     file.write(crondata)
######################## SET CRON JOB TO MONITOR ###########################
