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
This File is a A Entry Point of Every Configuration Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
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
from base.node import Node
from base.interface import Interface
from base.osimage import OSImage
from utils.journal import Journal
from utils.helper import Helper
from utils.status import Status
from utils.ha import HA

LOGGER = Log.get_logger()
node_blueprint = Blueprint('config_node', __name__)


@node_blueprint.route('/config/node', methods=['GET'])
@token_required
def config_node():
    """
    This api will send all the nodes in details.
    """
    access_code = 404
    status, response = Node().get_all_nodes()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_blueprint.route('/config/node/<string:name>', methods=['GET'])
@token_required
@validate_name
def config_node_get(name=None):
    """
    This api will send a requested node in details.
    """
    access_code = 404
    status, response = Node().get_node(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_blueprint.route('/config/node/<string:name>', methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_post(name=None):
    """
    This api will create or update a node depends on the availability of the node name.
    """
    status, response = Journal().add_request(function="Node.update_node",object=name,payload=request.data)
    if status is True:
        status, response = Node().update_node(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@node_blueprint.route('/config/node/<string:name>/_clone', methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_clone(name=None):
    """
    This api will clone a node depends on the availability of the node name.
    """
    status, response = Journal().add_request(function="Node.clone_node",object=name,payload=request.data)
    if status is True:
        status, response = Node().clone_node(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@node_blueprint.route('/config/node/<string:name>/_delete', methods=['GET'])
@token_required
@validate_name
def config_node_delete(name=None):
    """
    Input - Node Name
    Process - Delete the Node and it's interfaces.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Node.delete_node_by_name",object=name)
    if status is True:
        status, response = Node().delete_node_by_name(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# NEW API call.
@node_blueprint.route("/config/node/<string:name>/_osgrab", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_osgrab(name=None):
    """
    Input - OS Image name
    Process - Grab the OS from a node into an image. node inside json.
    Output - Success or Failure.
    """
    access_code=404
    osimage=None
    hastate=HA().get_hastate()
    if hastate is True:
        master=HA().get_role()
        if master is False:
            response={'message': 'something went wrong.....'}
            request_id = Status().gen_request_id()
            status, message = Journal().add_request(function="OSImage.grab",object=name,payload=request.data,masteronly=True,misc=request_id)
            if status is True:
                Status().add_message(request_id,"luna","request submitted to master...")
                Status().mark_messages_read(request_id)
                access_code=200
                response = {"message": "request submitted to master...", "request_id": request_id}
            else:
                response={'message': message}
            return response, access_code
    # below only when we are master
    returned = OSImage().grab(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            if hastate is True:
                Journal().queue_source_sync_by_node_name(name, request_id)
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


# NEW API call.
@node_blueprint.route("/config/node/<string:name>/_ospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_ospush(name=None):
    """
    Input - OS Image name
    Process - Push the OS from an image to a node. node inside json
    Output - Success or Failure.
    """
    access_code=404
    returned = OSImage().push(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


@node_blueprint.route('/config/node/<string:name>/interfaces', methods=['GET'])
@token_required
@validate_name
def config_node_get_interfaces(name=None):
    """
    Input - Node Name
    Process - Fetch the Node Interface List.
    Output - Node Interface List.
    """
    access_code=404
    status, response = Interface().get_all_node_interface(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_blueprint.route("/config/node/<string:name>/interfaces", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_post_interfaces(name=None):
    """
    Input - Node Name
    Process - Create Or Update The Node Interface.
    Output - Node Interface.
    """
    status, response = Journal().add_request(function="Interface.change_node_interface_by_name",object=name,payload=request.data)
    if status is True:
        status, response = Interface().change_node_interface_by_name(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@node_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
@validate_name
def config_node_interface_get(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Get the Node Interface.
    Output - Success or Failure.
    """
    access_code=404
    status, response = Interface().get_node_interface(name, interface)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@node_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
@validate_name
def config_node_delete_interface(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Delete the Node Interface.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Interface.delete_node_interface_by_name",object=name,param=interface)
    if status is True:
        status, response = Interface().delete_node_interface_by_name(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
