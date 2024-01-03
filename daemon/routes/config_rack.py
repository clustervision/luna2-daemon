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
This is a entry file for Rack configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Antoine Schonewille"
__email__       = "support@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.rack import Rack
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
rack_blueprint = Blueprint('config_rack', __name__)


@rack_blueprint.route("/config/rack", methods=['GET'])
@token_required
def config_rack():
    """
    This route will provide all the racks and layout.
    """
    access_code = 404
    status, response = Rack().get_rack()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_rack_get(name=None):
    """
    This route will provide a requested rack with layout.
    """
    access_code = 404
    status, response = Rack().get_rack(name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:rack'], skip=None)
def config_rack_post(name=None):
    """
    This route will create or update a requested rack.
    """
    status, response = Journal().add_request(function="Rack.update_rack", object=name, payload=request.data)
    if status is True:
        status, response = Rack().update_rack(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/inventory", methods=['GET'])
@token_required
def config_inventory_get():
    """
    This route will provide a requested rack with layout.
    """
    access_code = 404
    status, response = Rack().get_inventory()
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/inventory", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:rack:inventory'], skip=None)
def config_inventory_post(name=None):
    """
    This route will create or update a requested rack.
    """
    status, response = Journal().add_request(function="Rack.update_inventory", object=name, payload=request.data)
    if status is True:
        status, response = Rack().update_inventory(name, request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_rack_delete(name=None):
    """
    This route will delete a requested rack with layout.
    """
    status, response = Journal().add_request(function="Rack.delete_rack", object=name)
    if status is True:
        status, response = Rack().delete_rack(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@rack_blueprint.route("/config/rack/inventory/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_inventory_delete(name=None):
    """
    This route will delete a requested rack with layout.
    """
    status, response = Journal().add_request(function="Rack.delete_inventory", object=name)
    if status is True:
        status, response = Rack().delete_inventory(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

