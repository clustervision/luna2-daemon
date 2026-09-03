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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import re
import threading
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
    'artefactfile': { 'regexp': r'^[a-zA-Z0-9\-\.\_\+]+$', 'error': 'combination of characters a-z A-Z, numbers 0-9, \'-\', \'_\', \'.\' and \'+\'' },
    'filename': { 'regexp': r'^[a-zA-Z0-9\-\.\_\+\ ]+$', 'error': 'combination of characters a-z A-Z, numbers 0-9, whitespace, \'-\', \'_\', \'.\' and \'+\'' },
    # anchored as a whole: the earlier '^[...]+|$' was an alternation whose first
    # branch had no end anchor, so any value starting with a valid character passed
    # whatever followed it - a quote included - on every field using this rule
    'nameandclear': { 'regexp': r'^([a-zA-Z0-9\-\.\_\ ]+)?$', 'error': 'combination of characters a-z A-Z, numbers 0-9, whitespace, \'-\', \'_\' and \'.\'' },
    'tagandclear': { 'regexp': r'^([a-zA-Z0-9\-\.\_\ \:\+]+)?$', 'error': 'combination of characters a-z A-Z, numbers 0-9, whitespace, \'-\', \'_\', \'.\', \':\' and \'+\'' },
    # a plugin file name: the strict character set, but 'default' is a real plugin
    'plugin': { 'regexp': r'^[a-z0-9\-\.]+$', 'error': 'combination of small characters a-z, numbers 0-9, \'-\' and \'.\'' },
    'strictname': { 'regexp': r'^[a-z0-9\-\.]+$', 'error': 'combination of small characters a-z, numbers 0-9, \'-\' and \'.\'' },
    'strictcsv': { 'regexp': r'^[a-z0-9\-\,\ ]+$', 'error': 'combination of small characters a-z, numbers 0-9, whitespace, \'-\' and \',\'' },
    'loosecsv': { 'regexp': r'^[a-z0-9\-\.\,\ ]*$', 'error': 'combination of small characters a-z, numbers 0-9, whitespace, \'-\', \'.\' and \',\'' },
    'interfacecsv': { 'regexp': r'^[a-zA-Z0-9\.\-\,\ \:]{3,}$', 'error': 'combination of minimal 3 small characters a-z A-Z, numbers 0-9, whitespace, \'.\', \':\', \'-\' and \',\'' },
    'interface': { 'regexp': r'^[a-zA-Z0-9\.\-\:]{3,}$', 'error': 'combination of minimal 3 small characters a-z A-Z, numbers 0-9, \'.\', \':\', \'-\' and \',\'' },
    'intfandclear': { 'regexp': r'^[a-zA-Z0-9\.\-\:]{3,}|$', 'error': 'combination of minimal 3 small characters a-z A-Z, numbers 0-9, \'.\', \':\', \'-\' and \',\'' },
    'ipaddress': { 'regexp': r'^[0-9a-f:\.]*$', 'error': 'combination of characters small a-f, numbers 0-9, \':\' and \'.\'' },
    'macaddress': { 'regexp': r'^(([0-9A-Fa-f]{2}((-|:)[0-9A-Fa-f]{2}){5})|)$', 'error': '6 blocks of 2 characters a-f or numbers 0-9, separated by \':\' or \'-\'' },
    'domainname': { 'regexp': r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$', 'error': "lowercase a-z, numbers 0-9, '-', labels 1-63 chars, labels not starting/ending with '-'" },
    # a network's name in most payloads, its address (optionally /prefix) in the network table's own
    'network': { 'regexp': r'^(?:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?|[0-9a-f:\.]+(?:/[0-9]{1,3})?)$', 'error': "a network name (lowercase a-z, numbers 0-9, '-', '.') or an address with an optional /prefix" },
    'minimal': { 'regexp': r'^\S.*$', 'error': 'minimal character requirement. at least one' },
    'integer': { 'regexp': r'^[0-9]+$', 'error': 'integers only' },
    'intandnone': { 'regexp': r'^[0-9]*$', 'error': 'integers or empty only' },
    'fileowner': { 'regexp': r'^(([A-Za-z_][A-Za-z0-9_.-]*|[0-9]+)(:([A-Za-z_][A-Za-z0-9_.-]*|[0-9]+))?|)$', 'error': 'user or user:group, names or numeric ids, or empty' },
    'filemode': { 'regexp': r'^([0-7]{3,4}|)$', 'error': '3 or 4 octal digits, or empty' },
    'serviceaction': { 'regexp': r'^(restart|stop|reload|start|none|)$', 'error': 'restart, stop, reload, start or none' },
    'profilescope': { 'regexp': r'^(static|dynamic|)$', 'error': 'static or dynamic' },
    'redfishscheme': { 'regexp': r'^(https|http|)$', 'error': 'https or http' },
    'redfishrole': { 'regexp': r'^[a-zA-Z0-9\-\_\.]*$', 'error': 'combination of characters a-z A-Z, numbers 0-9, \'-\', \'_\' and \'.\'' },
    'anything': { 'regexp': r'', 'error': 'anything' }
}
RESERVED = {
    'name': ['default','inventory'],
    'strictname': ['default','inventory'],
    'anything': ['default']
}
CONVERT = {
    'macaddress': {'-':':'},
    'bond_slaves': {'-':':'},
    'vlan_parent': {'-':':'},
    'name': {r'\.+':'.'},
    'strictname': {r'\.+':'.'},
    'domainname': {r'\.+':'.'}
}
MATCH = {
    'name': 'name',
    'strictname': 'strictname',
    'newnodename': 'strictname',
    'hostname': 'strictname',
    'host': 'strictname',
    'newhostname': 'strictname',
    'newswitchname': 'strictname',
    'newotherdevicename': 'strictname',
    'newotherdevname': 'strictname',
    'newnetname': 'domainname',
    'domainname': 'domainname',
    'ipaddress': 'ipaddress',
    'macaddress': 'macaddress',
    'newosimage': 'name',
    'newgroupname': 'name',
    'newbmcname': 'name',
    'newsecretname': 'name',
    'newname': 'name',
    'newrackname': 'name',
    'newcloudname': 'name',
    'tableref': 'strictname',
    'target': 'name',
    'network': 'network',
    'owner': 'fileowner',
    'mode': 'filemode',
    'profiles': 'loosecsv',
    'newprofilename': 'strictname',
    'profile': 'strictname',
    # URL segments: each reaches a query, so each carries the rule of what it names
    'secret': 'name',
    'nodename': 'strictname',
    'node': 'strictname',
    'groupname': 'name',
    'script': 'plugin',
    'tagname': 'tagandclear',
    'subset': 'strictname',
    'filename': 'filename',
    'subsystem': 'strictname',
    'request_id': 'strictname',
    'device_type': 'strictname',
    'scope': 'profilescope',
    'object_type': 'strictname',
    'file': 'artefactfile',
    'osimagetag': 'tagandclear',
    'roles': 'loosecsv',
    'scripts': 'loosecsv',
    'tag': 'tagandclear',
    'interface': 'minimal',
    'newinterfacename': 'interface',
    'gateway_metric': 'integer',
    'vlanid': 'intandnone',
    'vlan_parent': 'intfandclear',
    'bond_mode': 'nameandclear',
    'bond_slaves': 'interfacecsv',
    'newredfishsetupname': 'name',
    # nameandclear, not name: on a node or a group it is an assignment, and an
    # assignment is cleared by sending it empty. The grab and push routes that
    # also carry it refuse an empty one themselves
    'biosconfig': 'nameandclear',
    'firmwarecatalog': 'name',
    'newbiosname': 'name',
    'account': 'name',
    'scheme': 'redfishscheme',
    'role': 'redfishrole'
}
MAXLENGTH = {
    'request_id': 256,
    'newnodename': 63,
    'host': 63,
    'newosimage': 127,
    'osimagetag': 127,
    'tag': 127,
    'name': 253,
    'newnetname': 253,
    'domainname': 253
}

# Strict names is a bit of a hack where i use the name of the function to determine whether we have
# a node name, switch name or any sort like names on our hand, or just a group name, image name, etc - Antoine
STRICT_NAMES = ['config_profile_post','config_profile_clone',
                'config_node_get','config_node_post','config_node_clone','config_node_delete',
                'config_node_osgrab','config_node_ospush','config_node_biosgrab',
                'config_node_get_interfaces',
                'config_node_post_interfaces','config_node_interface_get','config_node_delete_interface',
                'config_switch_get','config_switch_post','config_switch_clone','config_switch_delete',
                'config_switch_interfaces_get','config_switch_interface_get',
                'config_switch_interfaces_post','config_switch_interface_delete',
                'config_otherdev','config_otherdev_get','config_otherdev_post','config_otherdev_clone','config_otherdev_delete',
                'config_network_get','config_network_post','config_network_delete','config_network_ip',
                'config_network_taken','config_network_nextip']

STRICT_MATCHES = {'config_network_get': 'domainname', 'config_network_post': 'domainname'}

# Per-request validation state. The daemon serves several requests per
# process (gthread), so this must be thread-local: a module global here let one
# request's strict rule or error land in another request's decision.
_state = threading.local()


def _st():
    if not hasattr(_state, 'error'):
        _state.error = None
        _state.strict_name = False
        _state.strict_match = None
        _state.skip_list = []
    return _state
LOGGER = Log.get_logger()


def input_filter(checks=None, skip=None, json=True):
    """This decorator method will validate the input data."""
    def decorator(function):
        @wraps(function)
        def filter_input(*args, **kwargs):
            data=None
            _st().error = None
            _st().strict_name = True
            _st().strict_match = None
            _st().skip_list = []
            if function.__name__ not in STRICT_NAMES:
                _st().strict_name = False
            elif function.__name__ in STRICT_MATCHES.keys():
                _st().strict_match = STRICT_MATCHES[function.__name__]
            LOGGER.debug(f"STRICT CHECKING: strict_name: {_st().strict_name}, strict_match: {_st().strict_match}")
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
                    _st().skip_list.append(str(skip))
                else:
                    # data = request.args.to_dict() ## For Tracker - Sumit
                    _st().skip_list = list(skip)
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
                _st().skip_list = []
                LOGGER.debug(f"----- END ----- {data}")
                if _st().error:
                    response = {'message': f"{_st().error}"}
                    _st().error = None
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
        _st().strict_name = True
        _st().strict_match = None
        if function.__name__ not in STRICT_NAMES:
            _st().strict_name = False
        elif function.__name__ in STRICT_MATCHES.keys():
            _st().strict_match = STRICT_MATCHES[function.__name__]
        LOGGER.debug(f"STRICT CHECKING: strict_name: {_st().strict_name}, strict_match: {_st().strict_match}")
        for name_key, name_value in kwargs.items():
            filter_data(name_value, name_key)
            if _st().error:
                message = f"Incorrect Naming convention with {name_key} {name_value}: {_st().error}"
                response = {'message': message}
                LOGGER.debug(f"{_st().error}")
                _st().error = None
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
    if _st().strict_name and name == 'name':
        name=_st().strict_match or 'strictname'
        LOGGER.debug(f"Applying strict {name} rules")
    if name in _st().skip_list:
        LOGGER.debug(f"Skipping filter on {name}")
        return data
    data = control_char_re.sub('', data)
    # Match on what the caller actually sent, not on a cleaned copy of it. The two
    # differ, and only one of them reaches the code: validate_name discards this
    # return value and calls the route with the original kwargs, so a value is
    # approved in a form nothing downstream ever sees. "osimage'--" passes as
    # "osimage--" and arrives at the query with its quote intact, where it closes
    # the first condition and comments out the rest.
    # Rejecting is right rather than cleaning: a quote in a name is a client
    # mistake, and quietly answering about a different object is worse than a 400.
    unfiltered = data
    data = data.replace("'", "")
    data = data.replace('"', "")
    if name in MAXLENGTH.keys():
        if len(data) > MAXLENGTH[name]:
            LOGGER.info(f"length of {name} exceeds {MAXLENGTH[name]}")
            _st().error = f"length of {name} exceeds {MAXLENGTH[name]}"
            return
    if name in MATCH.keys():
        if MATCH[name] in RESERVED.keys():
            for reserved in RESERVED[MATCH[name]]:
                if str(data) == reserved:
                    LOGGER.info(f"RESERVED name = {name} with data = {data} is a reserved keyword")
                    _st().error = f"field {name} with content {data} is a reserved keyword: {reserved}"
                    return
        regex = re.compile(r"" + REG_EXP[MATCH[name]]['regexp'])
        if not regex.match(unfiltered):
            LOGGER.info(f"MATCH name = {name} with data = {unfiltered} mismatch with:")
            LOGGER.info(f"    REG_EXP['{MATCH[name]}']['regexp'] = {REG_EXP[MATCH[name]]['regexp']}")
            _st().error = f"field {name} with content {data} does not match criteria {REG_EXP[MATCH[name]]['error']}"
            return
        if MATCH[name] in CONVERT.keys():
            LOGGER.debug(f"CONVERT IN {MATCH[name]} = {data}")
            for rep in CONVERT[MATCH[name]].keys():
                #data = data.replace(rep ,CONVERT[MATCH[name]][rep])
                data = re.sub(r"" + rep, CONVERT[MATCH[name]][rep], data)
            LOGGER.debug(f"CONVERT OUT {MATCH[name]} = {data}")
    else:
        LOGGER.debug(f"Filter match problem. {name} does not exist in MATCH")
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
