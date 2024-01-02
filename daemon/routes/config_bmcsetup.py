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
This is a entry file for bmcsetup configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.bmcsetup import BMCSetup
from utils.journal import Journal
from utils.helper import Helper


LOGGER = Log.get_logger()
bmcsetup_blueprint = Blueprint('config_bmcsetup', __name__)


@bmcsetup_blueprint.route("/config/bmcsetup", methods=['GET'])
@token_required
def config_bmcsetup():
    """
    This route will provide all the BMC Setup's.
    """
    access_code = 404
    status, response = BMCSetup().get_all_bmcsetup()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@bmcsetup_blueprint.route("/config/bmcsetup/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_bmcsetup_get(name=None):
    """
    This route will provide a requested BMC Setup.
    """
    access_code = 404
    status, response = BMCSetup().get_bmcsetup(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@bmcsetup_blueprint.route("/config/bmcsetup/<string:name>/_member", methods=['GET'])
@token_required
@validate_name
def config_bmcsetup_member(name=None):
    """
    This route will provide the list of nodes which is connected to the requested BMC Setup.
    """
    access_code = 404
    status, response = BMCSetup().get_bmcsetup_member(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@bmcsetup_blueprint.route("/config/bmcsetup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:bmcsetup'], skip=None)
def config_bmcsetup_post(name=None):
    """
    This route will create or update requested BMC Setup.
    """
    status, response = Journal().add_request(function="BMCSetup.update_bmcsetup", object=name, payload=request.data)
    if status is True:
        status, response = BMCSetup().update_bmcsetup(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@bmcsetup_blueprint.route("/config/bmcsetup/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:bmcsetup'], skip=None)
def config_bmcsetup_clone(name=None):
    """
    This route will clone a requested BMC Setup.
    """
    status, response = Journal().add_request(function="BMCSetup.clone_bmcsetup", object=name, payload=request.data)
    if status is True:
        status, response = BMCSetup().clone_bmcsetup(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@bmcsetup_blueprint.route("/config/bmcsetup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_bmcsetup_delete(name=None):
    """
    This route will delete a requested BMC Setup.
    """
    status, response = Journal().add_request(function="BMCSetup.delete_bmcsetup", object=name)
    if status is True:
        status, response = BMCSetup().delete_bmcsetup(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
