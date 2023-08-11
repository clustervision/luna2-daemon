#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    'macaddress': r'^[a-fA-F0-9:\-]+$'
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
    'macaddress':'macaddress'
}
maxlength = {'request_id': '256'}
convert = {'macaddress': {'-':':'}}

#ERROR = None
SKIP_LIST = []
LOGGER = Log.get_logger()


def input_filter(checks=None, skip=None, json=True):
    """This decorator method will validate the input data."""
    def decorator(function):
        @wraps(function)
        def filter_input(*args, **kwargs):
            global SKIP_LIST
            #global ERROR
            data=None
            ERROR = None
            if json:
                if not Helper().check_json(request.data):
                    response = {'message': "data is not valid json"}
                    return response, 404
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
                ret, data, error = parse_item(data)
                SKIP_LIST = []
                LOGGER.debug(f"----- END ----- {data}")
                if ret is False:
                    response = {'message': f"{error}"}
                    return response, 404
                request.data = data
                return function(*args, **kwargs)
            response = {'message': "data structure incomplete or incorrect"}
            return response, 404
        return filter_input
    return decorator


def validate_name(function):
    """
    This decorator method will validate the input data.
    """
    @wraps(function)
    def decorator(*args, **kwargs):
        for name_key, name_value in kwargs.items():
            ret, data, error = filter_data(name_value, name_key)
            if ret is False:
                message = f"Incorrect Naming convention with {name_key} {name_value}: {error}"
                response = {'message': message}
                LOGGER.debug(f"{error}")
                return response, 400
        return function(*args, **kwargs)
    return decorator


def parse_dict(data=None):
    """
    This method will parse the dictionary.
    """
    for item in data.keys():
        ret, data[item], error = parse_item(data[item],item)
    return data


def parse_list(data=None):
    """
    This method will parse the list.
    """
    ret = True
    error = None
    new_data = []
    for item in data:
        if isinstance(item, list):
            ret, item, error = parse_list(item)
        else:
            ret, item, error = parse_item(item)
        new_data.append(item)
    return ret, new_data, error


def parse_item(data=None, name=None):
    """
    This method will parse the dictionary, list, and filter the strings.
    """
    ret = True
    error = None
    if isinstance(data, dict):
        ret, data, error = parse_list(data)
        data.update(data)
    elif isinstance(data, list):
        ret, data, error = parse_list(data)
        data = (data)
    elif isinstance(data, str):
        ret, data, error = filter_data(data,name)
    return ret, data, error


def filter_data(data=None, name=None):
    """
    This method will filter the provided data.
    """
    ret=True
    ERROR=None
    if name in SKIP_LIST:
        LOGGER.debug(f"Skipping filter on {name}")
        return data
    data = control_char_re.sub('', data)
    data = data.replace("'", "")
    data = data.replace('"', "")
    if name in maxlength.keys():
        if len(data) > int(maxlength[name]):
            LOGGER.info(f"length of {name} exceeds {maxlength[name]}")
            ERROR = f"length of {name} exceeds {maxlength[name]}"
            ret = False
            return ret, data, ERROR
    if name in MATCH.keys():
        regex = re.compile(r"" + REG_EXP[MATCH[name]])
        if not regex.match(data):
            LOGGER.info(f"MATCH name = {name} with data = {data} mismatch with:")
            LOGGER.info(f"    REG_EXP['{MATCH[name]}'] = {REG_EXP[MATCH[name]]}")
            ERROR = f"field {name} with content {data} does match criteria {REG_EXP[MATCH[name]]}"
            ret = False
            return ret, data, ERROR
    if name in convert.keys():
        LOGGER.debug(f"CONVERT IN {name} = {data}")
        for rep in convert[name].keys():
            data = data.replace(rep ,convert[name][rep])
        LOGGER.debug(f"CONVERT OUT {name} = {data}")
    return ret, data, ERROR


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
