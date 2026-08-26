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
This is a entry file for Node hardware inventory.
@token_required wrapper Method is used to Validate the token.
@provision_token_required wrapper Method allows a booting node to report itself.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "support@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required, provision_token_required
from common.validate_input import input_filter, validate_name
from base.nodeinventory import NodeInventory
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
node_inventory_blueprint = Blueprint('config_node_inventory', __name__)


@node_inventory_blueprint.route("/config/node/inventory", methods=['GET'])
@token_required
def config_node_inventory_list():
    """
    This route will provide a summary of inventory for all nodes.
    """
    access_code = 404
    status, response = NodeInventory().list_inventory()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_inventory_blueprint.route("/config/node/<string:name>/inventory", methods=['GET'])
@token_required
@validate_name
def config_node_inventory_get(name=None):
    """
    This route will provide the inventory of a requested node.
    """
    access_code = 404
    status, response = NodeInventory().get_inventory(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_inventory_blueprint.route("/config/node/<string:name>/inventory", methods=['POST'])
@provision_token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_inventory_post(name=None):
    """
    This route will store an inventory snapshot for a node.
    """
    status, response = Journal().add_request(function="NodeInventory.update_inventory", object=name, payload=request.data)
    if status is True:
        status, response = NodeInventory().update_inventory(name, request.data)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code


@node_inventory_blueprint.route("/config/node/<string:name>/inventory/_redfish", methods=['GET'])
@token_required
@validate_name
def config_node_inventory_redfish(name=None):
    """
    This route will collect one node's inventory over Redfish and store it.
    """
    status, response = NodeInventory().collect_redfish(name)
    if status is True:
        payload = response
        status, response = Journal().add_request(function="NodeInventory.update_inventory",
                                                 object=name, payload=payload)
        if status is True:
            status, response = NodeInventory().update_inventory(name, payload)
    access_code = Helper().get_access_code(status, response)
    response = {'message': response}
    return response, access_code


@node_inventory_blueprint.route("/config/node/inventory/_redfish", methods=['POST'])
@token_required
@input_filter(checks=['config:node'], skip=None)
def config_node_inventory_redfish_bulk():
    """
    This route will collect inventory over Redfish for a hostlist.
    """
    access_code = 404
    status, response = NodeInventory().bulk_collect_redfish(request.data)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code
