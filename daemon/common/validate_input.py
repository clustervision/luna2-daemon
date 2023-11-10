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
    'name': r'^[a-z0-9\-]+$',
    'ipaddress': r'^[0-9a-f:\.]+$',
    'macaddress': r'^(([0-9A-Za-f]{2}((-|:)[0-9A-Za-f]{2}){5})|)$',
    'minimal': r'^\S.*$',
    'integer': r'^[0-9]+$',
    'anything': r''
}
RESERVED = {
    'name': ['default'],
    'anything': ['default']
}
MATCH = {
    'name': 'name',
    'newnodename': 'name',
    'hostname': 'name',
    'newhostname': 'name',
    'newswitchname': 'name',
    'newotherdevicename': 'name',
    'newotherdevname': 'name',
    'ipaddress':'ipaddress',
    'macaddress':'macaddress',
    'newosimage': 'name',
    'newgroupname': 'name',
    'newbmcname': 'name',
    'newotherdevicename': 'name',
    'newotherdevname': 'name',
    'newsecretname': 'name',
    'newswitchname': 'name',
    'newnetname': 'name',
    'osimagetag': 'anything',
    'tag': 'anything',
    'interface': 'minimal',
    'gateway_metric': 'integer',
    'host': 'name'
}
MAXLENGTH = {
    'request_id': '256',
    'newnodename': '63',
    'host': '63'
}
CONVERT = {'macaddress': {'-':':'}}

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
            data=None
            ERROR = None
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
        regex = re.compile(r"" + REG_EXP[MATCH[name]])
        if not regex.match(data):
            LOGGER.info(f"MATCH name = {name} with data = {data} mismatch with:")
            LOGGER.info(f"    REG_EXP['{MATCH[name]}'] = {REG_EXP[MATCH[name]]}")
            ERROR = f"field {name} with content {data} does match criteria {REG_EXP[MATCH[name]]}"
            return
    if name in CONVERT.keys():
        LOGGER.debug(f"CONVERT IN {name} = {data}")
        for rep in CONVERT[name].keys():
            data = data.replace(rep ,CONVERT[name][rep])
        LOGGER.debug(f"CONVERT OUT {name} = {data}")
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
