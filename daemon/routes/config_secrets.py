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
This is a entry file for secrets configurations.
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
from base.secret import Secret
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
secrets_blueprint = Blueprint('config_secrets', __name__)


@secrets_blueprint.route("/config/secrets", methods=['GET'])
@token_required
def config_secrets_get():
    """
    Input - None
    Output - Return the List Of All Secrets.
    """
    access_code=404
    status, response = Secret().get_all_secrets()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_node(name=None):
    """
    Input - Node Name
    Output - Return the Node Secrets And Group Secrets for the Node.
    """
    access_code=404
    status, response = Secret().get_node_secrets(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_post_secrets_node(name=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.update_node_secrets",object=name,payload=request.data)
    if status is True:
        status, response = Secret().update_node_secrets(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_node_secret(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Return the Node Secret
    """
    access_code=404
    status, response = Secret().get_node_secret(name, secret)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_post_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.update_node_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().update_node_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_clone_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.clone_node_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().clone_node_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
@token_required
@validate_name
def config_node_secret_delete(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Secret.delete_node_secret",object=name,param=secret)
    if status is True:
        status, response = Secret().delete_node_secret(name, secret)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/group/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_group(name=None):
    """
    Input - Group Name
    Output - Return the Group Secrets.
    """
    access_code=404
    status, response = Secret().get_group_secrets(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/group/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_post_secrets_group(name=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.update_group_secrets",object=name,payload=request.data)
    if status is True:
        status, response = Secret().update_group_secrets(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_group_secret(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Return the Group Secret
    """
    access_code=404
    status, response = Secret().get_group_secret(name, secret)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_post_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.update_group_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().update_group_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route("/config/secrets/group/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_clone_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Clone Group Secrets.
    Output - None.
    """
    status, response = Journal().add_request(function="Secret.clone_group_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().clone_group_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@secrets_blueprint.route('/config/secrets/group/<string:name>/<string:secret>/_delete', methods=['GET'])
@token_required
@validate_name
def config_group_secret_delete(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Secret.delete_group_secret",object=name,param=secret)
    if status is True:
        status, response = Secret().delete_group_secret(name, secret)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code
