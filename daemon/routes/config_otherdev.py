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
This is a entry file for otherdev configurations.
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
from base.otherdev import OtherDev
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
otherdev_blueprint = Blueprint('config_otherdev', __name__)


@otherdev_blueprint.route("/config/otherdev", methods=['GET'])
@token_required
def config_otherdev():
    """
    This route will provide all the Other Devices.
    """
    access_code=404
    status, response = OtherDev().get_all_otherdev()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@otherdev_blueprint.route("/config/otherdev/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_otherdev_get(name=None):
    """
    This route will provide a requested Other Device.
    """
    access_code=404
    status, response = OtherDev().get_otherdev(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@otherdev_blueprint.route("/config/otherdev/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:otherdev'], skip=None)
def config_otherdev_post(name=None):
    """
    This route will create or update a requested Other Device.
    """
    status, response = Journal().add_request(function="OtherDev.update_otherdev",object=name,payload=request.data)
    if status is True:
        status, response = OtherDev().update_otherdev(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@otherdev_blueprint.route("/config/otherdev/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:otherdev'], skip=None)
def config_otherdev_clone(name=None):
    """
    This route will clone a requested Other Device.
    """
    status, response = Journal().add_request(function="OtherDev.clone_otherdev",object=name,payload=request.data)
    if status is True:
        status, response = OtherDev().clone_otherdev(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@otherdev_blueprint.route("/config/otherdev/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_otherdev_delete(name=None):
    """
    This route will delete a requested Other Device.
    """
    status, response = Journal().add_request(function="OtherDev.delete_otherdev",object=name)
    if status is True:
        status, response = OtherDev().delete_otherdev(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
