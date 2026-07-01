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
This is a entry file for static route configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.route import Route
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
route_blueprint = Blueprint('config_route', __name__)


@route_blueprint.route('/config/route', methods=['GET'])
@token_required
def get_routes():
    """
    This api sends the whole static-route catalog.
    """
    access_code = 404
    status, response = Route().get_routes()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@route_blueprint.route('/config/route/<string:name>', methods=['GET'])
@token_required
def get_route(name=None):
    """
    This api sends a single route from the catalog.
    """
    access_code = 404
    status, response = Route().get_routes(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@route_blueprint.route("/config/route/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:route'], skip=None)
def config_route(name=None):
    """
    Input - Route Name & Payload
    Process - Create Or Update a static route in the catalog.
    Output - None.
    """
    status, response = Journal().add_request(function="Route.update_route", object=name, payload=request.data)
    if status is True:
        status, response = Route().update_route(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@route_blueprint.route('/config/route/<string:name>/_delete', methods=['GET'])
@token_required
def delete_route(name=None):
    """
    This api deletes a route from the catalog (refused while still coupled).
    """
    access_code = 404
    status, response = Journal().add_request(function="Route.delete_route", object=name)
    if status is True:
        status, response = Route().delete_route(name)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@route_blueprint.route('/config/route/<string:name>/<string:tableref>/<string:target>/_couple', methods=['GET'])
@token_required
def couple_route(name=None, tableref=None, target=None):
    """
    This api couples (stacks) a route onto a network, group or node.
    """
    status, response = Journal().add_request(function="Route.couple_route", object=name, param=f"{tableref}/{target}")
    if status is True:
        status, response = Route().couple_route(name, f"{tableref}/{target}")
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@route_blueprint.route('/config/route/<string:name>/<string:tableref>/<string:target>/_decouple', methods=['GET'])
@token_required
def decouple_route(name=None, tableref=None, target=None):
    """
    This api removes a route coupling from a network, group or node.
    """
    status, response = Journal().add_request(function="Route.decouple_route", object=name, param=f"{tableref}/{target}")
    if status is True:
        status, response = Route().decouple_route(name, f"{tableref}/{target}")
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code
