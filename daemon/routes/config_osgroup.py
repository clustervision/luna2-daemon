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
This is a entry file for osgroup configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.osuser import OsUser
from utils.helper import Helper

LOGGER = Log.get_logger()
osgroup_blueprint = Blueprint('config_osgroup', __name__)


@osgroup_blueprint.route("/config/osgroup", methods=['GET'])
@token_required
def config_get_os_group_list():
    """
    Input - None
    Output - List of OSUsers (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().list_groups()

    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@osgroup_blueprint.route("/config/osgroup/<string:name>", methods=['GET'])
@token_required
def config_get_os_group(name):
    """
    Input - groupname
    Process - Show info of OSUser (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().get_group(name)

    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@osgroup_blueprint.route("/config/osgroup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osgroup'], skip=None)
def config_post_os_group(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update System (ldap/ssd/pam) groups.
    Output - None.
    """
    access_code = 503
    response = "Invalid request: data missing"
    if name and name in request.json['config']['osgroup']:
        groupdata = request.json['config']['osgroup'][name]
        status, response = OsUser().update_group(name, **groupdata)
        access_code=Helper().get_access_code(status,response)
    return {'message': response}, access_code


@osgroup_blueprint.route("/config/osgroup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_group_delete(name=None):
    """
    Input - User Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    access_code=404
    status, response = OsUser().delete_group(name)

    if status is True:
        access_code=204
    return {'message': response}, access_code
