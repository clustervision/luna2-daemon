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
This is a entry file for network configurations.
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
from base.network import Network
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
network_blueprint = Blueprint('config_network', __name__)


@network_blueprint.route("/config/network", methods=['GET'])
@token_required
def config_network():
    """
    Input - None
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    access_code=404
    status,response = Network().get_all_networks()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@network_blueprint.route("/config/network/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_network_get(name=None):
    """
    Input - Network Name
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    access_code=404
    status, response = Network().get_network(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@network_blueprint.route("/config/network/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:network'], skip=None)
def config_network_post(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Network.update_network",object=name,payload=request.data)
    if status is True:
        status, response = Network().update_network(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@network_blueprint.route("/config/network/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_network_delete(name=None):
    """
    Input - Network Name
    Process - Delete The Network.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Network.delete_network",object=name)
    if status is True:
        status, response = Network().delete_network(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# Antoine - Aug 5 2023 - next API call will probably never be used, or not in context with a network?
@network_blueprint.route("/config/network/<string:name>/<string:ipaddress>", methods=['GET'])
@token_required
@validate_name
def config_network_ip(name=None, ipaddress=None):
    """
    Input - Network Name And IP Address
    Process - checks if a given ip address is free or taken for the network
    Output - Success or Failure.
    """
    access_code=404
    status, response = Network().network_ip(name, ipaddress)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@network_blueprint.route("/config/network/<string:name>/_member", methods=['GET'])
@token_required
@validate_name
def config_network_taken(name=None):
    """
    Input - Network Name
    Process - Find out all the ipaddress which is taken by the provided network.
    Output - List all taken ipaddress by the network.
    """
    access_code=404
    status, response = Network().taken_ip(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@network_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
@token_required
@validate_name
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Network.
    Output - Next Available IP on the Network.
    """
    access_code=404
    status, response = Network().next_free_ip(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code
