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
This file is the entry point for provisioning Luna users: the identities that hold a
token. OS users, the cluster's accounts, live under /config/osuser.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from json import dumps
from flask import Blueprint, request, g
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.user import User
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
user_blueprint = Blueprint('config_user', __name__)


@user_blueprint.route("/config/user", methods=['GET'])
@token_required
def config_user():
    """
    This route will provide all users, without their passwords.
    """
    access_code = 404
    status, response = User().get_user()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@user_blueprint.route("/config/user/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_user_get(name=None):
    """
    This route will provide one user, without the password.
    """
    access_code = 404
    status, response = User().get_user(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@user_blueprint.route("/config/user/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:user'], skip=['password'])
def config_user_post(name=None):
    """
    This route will create or update a user. The caller is recorded as the creator and a
    password is digested here, so both values travel with the journaled request and the
    peer stores the same ones: a second salting on the peer would leave two digests for
    one account, and the password itself never travels.
    """
    body = request.data['config']['user'][name]
    body['createdby'] = g.userid
    if body.get('password'):
        body['password'] = User().digest(body['password'])
    status, response = Journal().add_request(function="User.update_user", object=name, payload=request.data)
    if status is True:
        status, response = User().update_user(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@user_blueprint.route("/config/user/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_user_delete(name=None):
    """
    This route will delete a user and its memberships.
    """
    status, response = Journal().add_request(function="User.delete_user", object=name)
    if status is True:
        status, response = User().delete_user(name)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code
