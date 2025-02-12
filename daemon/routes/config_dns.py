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
This is a entry file for DNS configurations.
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
from base.dns import DNS
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
dns_blueprint = Blueprint('config_dns', __name__)


@dns_blueprint.route('/config/dns/<string:name>', methods=['GET'])
@token_required
def get_dns(name=None):
    """
    This api will send all records for additional dns for the network.
    """
    access_code = 404
    status, response = DNS().get_dns(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@dns_blueprint.route("/config/dns/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:dns'], skip=None)
def config_dns(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update additional DNS entries.
    Output - None.
    """
    status, response = Journal().add_request(function="DNS.update_dns", object=name, payload=request.data)
    if status is True:
        status, response = DNS().update_dns(name, request.data)
    access_code = Helper().get_access_code(status,response)
    return {'message': response}, access_code


@dns_blueprint.route('/config/dns/<string:network>/<string:name>/_delete', methods=['GET'])
@token_required
def delete_dns(name=None,network=None):
    """
    This api deletes an additional dns entry.
    """
    access_code = 404
    status, response = Journal().add_request(function="DNS.delete_dns", object=name, param=network)
    if status is True:
        status, response = DNS().delete_dns(name,network)
        access_code = 204
    return {'message': response}, access_code
