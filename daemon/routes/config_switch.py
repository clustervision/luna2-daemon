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
This is a entry file for switch configurations.
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
from base.switch import Switch
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
switch_blueprint = Blueprint('config_switch', __name__)


@switch_blueprint.route("/config/switch", methods=['GET'])
@token_required
def config_switch():
    """
    This route will provide all the Switches.
    """
    access_code = 404
    status, response = Switch().get_all_switches()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@switch_blueprint.route("/config/switch/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_switch_get(name=None):
    """
    This route will provide a requested Switch.
    """
    access_code = 404
    status, response = Switch().get_switch(name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@switch_blueprint.route("/config/switch/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:switch'], skip=None)
def config_switch_post(name=None):
    """
    This route will create or update a requested Switch.
    """
    status, response = Journal().add_request(function="Switch.update_switch", object=name, payload=request.data)
    if status is True:
        status, response = Switch().update_switch(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@switch_blueprint.route("/config/switch/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:switch'], skip=None)
def config_switch_clone(name=None):
    """
    This route will clone a requested Switch.
    """
    status, response = Journal().add_request(function="Switch.clone_switch", object=name, payload=request.data)
    if status is True:
        status, response = Switch().clone_switch(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@switch_blueprint.route("/config/switch/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_switch_delete(name=None):
    """
    This route will delete a requested Switch.
    """
    status, response = Journal().add_request(function="Switch.delete_switch", object=name)
    if status is True:
        status, response = Switch().delete_switch(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
