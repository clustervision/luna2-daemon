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
This is a entry file for osuser configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
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
osuser_blueprint = Blueprint('config_osuser', __name__)


@osuser_blueprint.route("/config/osuser", methods=['GET'])
@token_required
def config_get_os_user_list():
    """
    Input - None
    Output - List of OSUsers (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().list_users()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@osuser_blueprint.route("/config/osuser/<string:name>", methods=['GET'])
@token_required
def config_get_os_user(name):
    """
    Input - username
    Process - Show info of OSUser (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().get_user(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@osuser_blueprint.route("/config/osuser/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osuser'], skip=None)
def config_post_os_user(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update System (ldap/ssd/pam) users.
    Output - None.
    """
    access_code = 503
    response = "Invalid request: missing data"
    if name and name in request.json['config']['osuser']:
        userdata = request.json['config']['osuser'][name]
        status, response = OsUser().update_user(name, **userdata)
        access_code=Helper().get_access_code(status,response)
    return {'message': response}, access_code


@osuser_blueprint.route("/config/osuser/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_user_delete(name=None):
    """
    Input - User Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    access_code=404
    status, response = OsUser().delete_user(name)

    if status is True:
        access_code=204
    return {'message': response}, access_code
