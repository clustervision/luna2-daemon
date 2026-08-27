#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
This endpoint can be contacted to manage stored BIOS configurations.

The grab route hangs off the node rather than off the configuration, because the
node is what is being read - the same way _osgrab does, so an administrator who
knows one can guess the other.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2026, Luna2 Project"
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
from base.bios import Bios
from utils.journal import Journal
from utils.helper import Helper


LOGGER = Log.get_logger()
bios_blueprint = Blueprint('config_bios', __name__)


@bios_blueprint.route("/config/biosconfig", methods=['GET'])
@token_required
def config_bios():
    """
    This route will provide all the stored BIOS configurations.
    """
    access_code = 404
    status, response = Bios().get_all_bios()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@bios_blueprint.route("/config/biosconfig/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_bios_get(name=None):
    """
    This route will provide a requested BIOS configuration and its settings.
    """
    access_code = 404
    status, response = Bios().get_bios(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@bios_blueprint.route("/config/biosconfig/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:biosconfig'], skip=None)
def config_bios_post(name=None):
    """
    This route will update what an administrator owns on a BIOS configuration.
    """
    status, response = Journal().add_request(function="Bios.update_bios",
                                             object=name, payload=request.data)
    if status is True:
        status, response = Bios().update_bios(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@bios_blueprint.route("/config/biosconfig/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_bios_delete(name=None):
    """
    This route will delete a BIOS configuration.
    """
    status, response = Journal().add_request(function="Bios.delete_bios", object=name)
    if status is True:
        status, response = Bios().delete_bios(name)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@bios_blueprint.route("/config/node/<string:name>/_biosgrab", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_biosgrab(name=None):
    """
    This route will read a node's BIOS over Redfish and store it as a named
    configuration.

    The read happens here and the store goes through the journal, which is the
    split every collector in this daemon uses: reading a BMC is local to whichever
    controller can reach it, and writing the result is a replicated change.
    """
    try:
        config = request.data['config']['node'][name]['biosconfig']
    except (KeyError, TypeError):
        return {'message': 'Invalid request: no biosconfig name supplied'}, 400
    status, response = Bios().collect_bios(node=name, name=config)
    if status is True:
        payload = response
        status, response = Journal().add_request(function="Bios.store_grabbed",
                                                 object=config, payload=payload)
        if status is True:
            status, response = Bios().store_grabbed(config, payload)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@bios_blueprint.route("/config/node/<string:name>/_biospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_biospush(name=None):
    """
    This route will apply a stored BIOS configuration to a node.
    """
    return _biospush('node', name)


@bios_blueprint.route("/config/group/<string:name>/_biospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_biospush(name=None):
    """
    This route will apply a stored BIOS configuration to every node of a group.
    """
    return _biospush('group', name)


def _biospush(object_type=None, name=None):
    """
    Both push routes, which differ only in what they are aimed at.

    The work is queued and the request id comes back at once: a stage is a write,
    a reset and a wait for POST, so holding the HTTP request open would mean
    holding it for the better part of an hour.
    """
    returned = Bios().push_bios(object_type=object_type, name=name,
                                request_data=request.data)
    status, response = returned[0], returned[1]
    if status is True and len(returned) == 3:
        return {'message': response, 'request_id': returned[2]}, 200
    return {'message': response}, Helper().get_access_code(status, response)
