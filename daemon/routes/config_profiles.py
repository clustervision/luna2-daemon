#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
This is the entry file for profile configuration requests.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required, provision_token_required
from common.validate_input import input_filter, validate_name
from base.profile import Profile
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
profiles_blueprint = Blueprint('config_profiles', __name__)


@profiles_blueprint.route("/config/profiles", methods=['GET'])
@token_required
def config_profiles_get():
    """
    Input - None
    Output - Return the List Of All Profiles.
    """
    access_code=404
    status, response = Profile().get_all_profiles()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@profiles_blueprint.route("/config/profiles/node/<string:name>", methods=['GET'])
@provision_token_required
@validate_name
def config_get_profiles_node(name=None):
    """
    Input - Node Name
    Output - Every profile the node applies (group's plus its own, stacked), in
             apply-ready shape. The call a node makes to apply its profiles
             without knowing their names.
    """
    access_code=404
    status, response = Profile().get_node_profiles(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@profiles_blueprint.route("/config/profiles/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_profile_get(name=None):
    """
    Input - Profile Name
    Output - Return the Profile including its files.
    """
    access_code=404
    status, response = Profile().get_profile(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@profiles_blueprint.route("/config/profiles/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:profiles'], skip=None)
def config_profile_post(name=None):
    """
    Input - Profile Name & Payload
    Process - Create Or Update a Profile and its files.
    Output - None.
    """
    status, response = Journal().add_request(function="Profile.update_profile",object=name,payload=request.data)
    if status is True:
        status, response = Profile().update_profile(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@profiles_blueprint.route("/config/profiles/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:profiles'], skip=None)
def config_profile_clone(name=None):
    """
    Input - Profile Name & Payload
    Process - Clone a Profile including its files.
    Output - None.
    """
    status, response = Journal().add_request(function="Profile.clone_profile",object=name,payload=request.data)
    if status is True:
        status, response = Profile().clone_profile(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@profiles_blueprint.route('/config/profiles/<string:name>/_delete', methods=['GET'])
@token_required
@validate_name
def config_profile_delete(name=None):
    """
    Input - Profile Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Profile.delete_profile",object=name)
    if status is True:
        status, response = Profile().delete_profile(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@profiles_blueprint.route('/config/profiles/<string:name>/<string:filename>/_delete', methods=['GET'])
@token_required
@validate_name
def config_profile_file_delete(name=None, filename=None):
    """
    Input - Profile Name & File Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Profile.delete_profile_file",object=name,param=filename)
    if status is True:
        status, response = Profile().delete_profile_file(name, filename)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
