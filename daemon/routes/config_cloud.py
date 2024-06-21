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
This is a entry file for cloud configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.cloud import Cloud
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
cloud_blueprint = Blueprint('config_cloud', __name__)


@cloud_blueprint.route("/config/cloud", methods=['GET'])
@token_required
def config_cloud():
    """
    This route will provide all the Cloudes.
    """
    access_code = 404
    status, response = Cloud().get_all_clouds()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@cloud_blueprint.route("/config/cloud/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_cloud_get(name=None):
    """
    This route will provide a requested Cloud.
    """
    access_code = 404
    status, response = Cloud().get_cloud(name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@cloud_blueprint.route("/config/cloud/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:cloud'], skip=None)
def config_cloud_post(name=None):
    """
    This route will create or update a requested Cloud.
    """
    status, response = Journal().add_request(function="Cloud.update_cloud", object=name, payload=request.data)
    if status is True:
        status, response = Cloud().update_cloud(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@cloud_blueprint.route("/config/cloud/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_cloud_delete(name=None):
    """
    This route will delete a requested Cloud.
    """
    status, response = Journal().add_request(function="Cloud.delete_cloud", object=name)
    if status is True:
        status, response = Cloud().delete_cloud(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
