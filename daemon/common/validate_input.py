#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
Security class which provides functions and method to verify,
check and secure input and other related things
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import re
from sys import maxunicode
from itertools import chain
from functools import wraps
from flask import request
from utils.log import Log
from utils.helper import Helper

all_chars = (chr(i) for i in range(maxunicode))
categories = {'Cc'}
# CONTROL_CHAR = ''.join(c for c in all_chars if unicodedata.category(c) in categories)
# or equivalently and much more efficiently
CONTROL_CHAR = ''.join(map(chr, chain(range(0x00, 0x20), range(0x7f, 0xa0))))
control_char_re = re.compile(f'[{re.escape(CONTROL_CHAR)}]')

REG_EXP = {
    'name': { 'regexp': r'^[a-zA-Z0-9\-\.\_\ ]+$', 'error': 'combination of characters a-z A-Z, numbers 0-9, whitespace, \'-\', \'_\' and \'.\'' },
    'strictname': { 'regexp': r'^[a-z0-9\-\.]+$', 'error': 'combination of small characters a-z, numbers 0-9, \'-\' and \'.\'' },
    'ipaddress': { 'regexp': r'^[0-9a-f:\.]+$', 'error': 'combination of characters small a-f, numbers 0-9, \':\' and \'.\'' },
    'macaddress': { 'regexp': r'^(([0-9A-Za-f]{2}((-|:)[0-9A-Za-f]{2}){5})|)$', 'error': '6 blocks of 2 characters a-f or numbers 0-9, separated by \':\' or \'-\'' },
    'minimal': { 'regexp': r'^\S.*$', 'error': 'minimal character requirement. at least one' },
    'integer': { 'regexp': r'^[0-9]+$', 'error': 'integers only' },
    'anything': { 'regexp': r'', 'error': 'anything' },
}
RESERVED = {
    'name': ['default','inventory'],
    'strictname': ['default','inventory'],
    'anything': ['default']
}
CONVERT = {
    'macaddress': {'-':':'},
    'name': {r'\.+':'.'},
    'strictname': {r'\.+':'.'},
}
MATCH = {
    'name': 'name',
    'newnodename': 'strictname',
    'hostname': 'strictname',
    'host': 'strictname',
    'newhostname': 'strictname',
    'newswitchname': 'strictname',
    'newotherdevicename': 'strictname',
    'newotherdevname': 'strictname',
    'newnetname': 'strictname',
    'ipaddress':'ipaddress',
    'macaddress':'macaddress',
    'newosimage': 'name',
    'newgroupname': 'name',
    'newbmcname': 'name',
    'newsecretname': 'name',
    'osimagetag': 'anything',
    'tag': 'anything',
    'interface': 'minimal',
    'gateway_metric': 'integer'
}
MAXLENGTH = {
    'request_id': '256',
    'newnodename': '63',
    'host': '63'
}

# Strict names is a bit of a hack where i use the name of the function to determine whether we have
# a node name, switch name or any sort like names on our hand, or just a group name, image name, etc - Antoine
STRICT_NAMES = ['config_node_get','config_node_post','config_node_clone','config_node_delete',
                'config_node_osgrab','config_node_ospush','config_node_get_interfaces',
                'config_node_post_interfaces','config_node_interface_get','config_node_delete_interface',
                'config_switch_get','config_switch_post','config_switch_clone','config_switch_delete',
                'config_otherdev','config_otherdev_get','config_otherdev_post','config_otherdev_clone','config_otherdev_delete',
                'config_network_get','config_network_post','config_network_delete','config_network_ip',
                'config_network_taken','config_network_nextip']

ERROR = None
SKIP_LIST = []
LOGGER = Log.get_logger()


def input_filter(checks=None, skip=None, json=True):
    """This decorator method will validate the input data."""
    def decorator(function):
        @wraps(function)
        def filter_input(*args, **kwargs):
            global SKIP_LIST
            global ERROR
            global STRICT_NAME
            data=None
            ERROR = None
            STRICT_NAME = True
            if function.__name__ not in STRICT_NAMES:
                STRICT_NAME = False
            if json:
                if not Helper().check_json(request.data):
                    response = {'message': "data is not valid json"}
                    return response, 400
                data = request.get_json(force=True)
            else:
                data = request.args.to_dict()
            if skip:
                if isinstance(skip, str):
                    # data = request.args.getlist('info_hash') ## For Tracker - Sumit
                    SKIP_LIST.append(str(skip))
                else:
                    # data = request.args.to_dict() ## For Tracker - Sumit
                    SKIP_LIST = skip
            LOGGER.debug(f"---- START ---- {data}")
            # Checking for Name in kwargs and appending the name in checks - Sumit
            if 'name' in kwargs:
                check_with_name = f"{checks[0]}:{kwargs['name']}"
                check_list = [check_with_name]
            else:
                check_list = checks
            # Checking for Name in kwargs and appending the name in checks - Sumit
            if check_structure(data, check_list):
                data = parse_item(data)
                SKIP_LIST = []
                LOGGER.debug(f"----- END ----- {data}")
                if ERROR:
                    response = {'message': f"{ERROR}"}
                    ERROR = None
                    return response, 400
                request.data = data
                return function(*args, **kwargs)
            response = {'message': "data structure incomplete or incorrect"}
            return response, 400
        return filter_input
    return decorator


def validate_name(function):
    """
    This decorator method will validate the input data.
    """
    @wraps(function)
    def decorator(*args, **kwargs):
        global STRICT_NAME
        STRICT_NAME = True
        if function.__name__ not in STRICT_NAMES:
            STRICT_NAME = False
        for name_key, name_value in kwargs.items():
            global ERROR
            filter_data(name_value, name_key)
            if ERROR:
                message = f"Incorrect Naming convention with {name_key} {name_value}: {ERROR}"
                response = {'message': message}
                LOGGER.debug(f"{ERROR}")
                ERROR = None
                return response, 400
        return function(*args, **kwargs)
    return decorator


def parse_dict(data=None):
    """
    This method will parse the dictionary.
    """
    for item in data.keys():
        data[item] = parse_item(data[item],item)
    return data


def parse_list(data=None):
    """
    This method will parse the list.
    """
    new_data = []
    for item in data:
        if isinstance(item, list):
            item = parse_list(item)
        else:
            item = parse_item(item)
        new_data.append(item)
    return new_data


def parse_item(data=None, name=None):
    """
    This method will parse the dictionary, list, and filter the strings.
    """
    if isinstance(data, dict):
        data.update(parse_dict(data))
    elif isinstance(data, list):
        data = parse_list(data)
    elif isinstance(data, str):
        data = filter_data(data,name)
    return data


def filter_data(data=None, name=None):
    """
    This method will filter the provided data.
    """
    global ERROR
    if STRICT_NAME and name == 'name':
        name='strictname'
        LOGGER.debug("Applying strict name rules")
    if name in SKIP_LIST:
        LOGGER.debug(f"Skipping filter on {name}")
        return data
    data = control_char_re.sub('', data)
    data = data.replace("'", "")
    data = data.replace('"', "")
    if name in MAXLENGTH.keys():
        if len(data) > int(MAXLENGTH[name]):
            LOGGER.info(f"length of {name} exceeds {MAXLENGTH[name]}")
            ERROR = f"length of {name} exceeds {MAXLENGTH[name]}"
            return
    if name in MATCH.keys():
        if MATCH[name] in RESERVED.keys():
            for reserved in RESERVED[MATCH['name']]:
                if str(data) == reserved:
                    LOGGER.info(f"RESERVED name = {name} with data = {data} is a reserved keyword")
                    ERROR = f"field {name} with content {data} is a reserved keyword: {reserved}"
                    return
        regex = re.compile(r"" + REG_EXP[MATCH[name]]['regexp'])
        if not regex.match(data):
            LOGGER.info(f"MATCH name = {name} with data = {data} mismatch with:")
            LOGGER.info(f"    REG_EXP['{MATCH[name]}']['regexp'] = {REG_EXP[MATCH[name]]['regexp']}")
            ERROR = f"field {name} with content {data} does match criteria {REG_EXP[MATCH[name]]['error']}"
            return
        if MATCH[name] in CONVERT.keys():
            LOGGER.debug(f"CONVERT IN {MATCH[name]} = {data}")
            for rep in CONVERT[MATCH[name]].keys():
                #data = data.replace(rep ,CONVERT[MATCH[name]][rep])
                data = re.sub(r"" + rep, CONVERT[MATCH[name]][rep], data)
            LOGGER.debug(f"CONVERT OUT {MATCH[name]} = {data}")
    return data


def check_structure(data=None, checks=None):
    """
    This method will validate the structure of the data.
    """
    if not checks:
        return True
    check_list = []
    if isinstance(checks, str):
        check_list.append(str(checks))
    else:
        check_list = checks
    try:
        for check in check_list:
            arr = check.split(':')
            slice_data = data
            for element in arr:
                if not element in slice_data:
                    LOGGER.debug(f"{element} not found in data {slice_data}")
                    return False
                LOGGER.debug(f"OK: {element} found in data {slice_data}")
                slice_data = slice_data[element]
        return True
    except Exception as exp:
        LOGGER.debug(f"filter encountered issue due to incorrect data/json/dict?: {exp}")
        return False
