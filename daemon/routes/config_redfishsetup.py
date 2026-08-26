#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
This file is the entry point for the redfishsetup configuration
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2026, Luna2 Project [CLI]"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.redfishsetup import RedfishSetup
from utils.journal import Journal
from utils.helper import Helper


LOGGER = Log.get_logger()
redfishsetup_blueprint = Blueprint('config_redfishsetup', __name__)


@redfishsetup_blueprint.route("/config/redfishsetup", methods=['GET'])
@token_required
def config_redfishsetup():
    """
    This route will provide all the Redfish Setup's.
    """
    access_code = 404
    status, response = RedfishSetup().get_all_redfishsetup()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_redfishsetup_get(name=None):
    """
    This route will provide a requested Redfish Setup.
    """
    access_code = 404
    status, response = RedfishSetup().get_redfishsetup(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>/_member", methods=['GET'])
@token_required
@validate_name
def config_redfishsetup_member(name=None):
    """
    This route will provide the nodes and groups pointing at a Redfish Setup.
    """
    access_code = 404
    status, response = RedfishSetup().get_redfishsetup_member(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:redfishsetup'], skip=None)
def config_redfishsetup_post(name=None):
    """
    This route will create or update a requested Redfish Setup.
    """
    status, response = Journal().add_request(function="RedfishSetup.update_redfishsetup",
                                             object=name, payload=request.data)
    if status is True:
        status, response = RedfishSetup().update_redfishsetup(name, request.data)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:redfishsetup'], skip=None)
def config_redfishsetup_clone(name=None):
    """
    This route will clone a requested Redfish Setup.
    """
    status, response = Journal().add_request(function="RedfishSetup.clone_redfishsetup",
                                             object=name, payload=request.data)
    if status is True:
        status, response = RedfishSetup().clone_redfishsetup(name, request.data)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_redfishsetup_delete(name=None):
    """
    This route will delete a requested Redfish Setup.
    """
    status, response = Journal().add_request(function="RedfishSetup.delete_redfishsetup",
                                             object=name)
    if status is True:
        status, response = RedfishSetup().delete_redfishsetup(name)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code


@redfishsetup_blueprint.route("/config/redfishsetup/<string:name>/<string:account>/_delete",
                              methods=['GET'])
@token_required
@validate_name
def config_redfishsetup_account_delete(name=None, account=None):
    """
    This route will delete one account of a requested Redfish Setup.
    """
    status, response = Journal().add_request(function="RedfishSetup.delete_redfishsetup_account",
                                             object=name, param=account)
    if status is True:
        status, response = RedfishSetup().delete_redfishsetup_account(name, account)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code
