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
This is a entry file for group configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
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
from base.group import Group
from base.interface import Interface
from base.osimage import OSImage
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
group_blueprint = Blueprint('config_group', __name__)


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@group_blueprint.route("/config/group", methods=['GET'])
@token_required
def config_group():
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    access_code = 404
    status, response = Group().get_all_group()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@group_blueprint.route("/config/group/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_group_get(name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    access_code = 404
    status, response = Group().get_group(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@group_blueprint.route("/config/group/<string:name>/_member", methods=['GET'])
@token_required
@validate_name
def config_group_member(name=None):
    """
    This method will fetch all the nodes, which is connected to
    the provided group.
    """
    access_code = 404
    status, response = Group().get_group_member(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@group_blueprint.route("/config/group/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_post(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    status, response = Journal().add_request(function="Group.update_group",object=name,payload=request.data)
    if status is True:
        status, response = Group().update_group(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# NEW API call.
@group_blueprint.route("/config/group/<string:name>/_ospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_ospush(name=None):
    """
    Input - OS Image name
    Process - Push the OS from an image to a all nodes in the group. node inside json
    Output - Success or Failure.
    """
    access_code = 404
    returned = OSImage().push(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code = 200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@group_blueprint.route("/config/group/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_clone(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    status, response = Journal().add_request(function="Group.clone_group",object=name,payload=request.data)
    if status is True:
        status, response = Group().clone_group(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@group_blueprint.route("/config/group/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_group_delete(name=None):
    """
    Input - Group Name
    Process - Delete the Group and it's interfaces.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Group.delete_group_by_name",object=name)
    if status is True:
        status, response = Group().delete_group_by_name(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@group_blueprint.route("/config/group/<string:name>/interfaces", methods=['GET'])
@token_required
@validate_name
def config_group_get_interfaces(name=None):
    """
    Input - Group Name
    Process - Fetch the Group Interface List.
    Output - Group Interface List.
    """
    access_code = 404
    status, response = Interface().get_all_group_interface(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@group_blueprint.route("/config/group/<string:name>/interfaces", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_post_interfaces(name=None):
    """
    Input - Group Name
    Process - Create Or Update The Group Interface.
    Output - Group Interface.
    """
    status, response = Journal().add_request(function="Interface.change_group_interface",object=name,payload=request.data)
    if status is True:
        status, response = Interface().change_group_interface(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@group_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
@validate_name
def config_group_interface_get(name=None, interface=None):
    """
    Input - Group Name & Interface Name
    Process - Get the Group Interface.
    Output - Success or Failure.
    """
    access_code = 404
    status, response = Interface().get_group_interface(name, interface)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@group_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
@validate_name
def config_group_delete_interface(name=None, interface=None):
    """
    Input - Group Name & Interface Name
    Process - Delete the Group Interface.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="Interface.delete_group_interface",object=name,param=interface)
    if status is True:
        status, response = Interface().delete_group_interface(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
