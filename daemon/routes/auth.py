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
This File is use for authentication purpose.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_input import validate_name, input_filter
from base.authentication import Authentication

LOGGER = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)


@auth_blueprint.route('/token', methods=['POST'])
@input_filter()
def jwt_token():
    """
    This route will generate and return the token on behalf of provided username and password.
    """
    access_code = 401
    status, response = Authentication().get_token(request.data)
    response = dumps(response)
    if status is True:
        access_code = 201
    return response, access_code


@auth_blueprint.route('/tpm/<string:nodename>', methods=['POST'])
@validate_name
@input_filter()
def tpm(nodename=None):
    """
    Input - TPM string
    Process - Validate the TPM string to match a node.
    On the success, create a token, which is valid for expiry time mentioned in configuration.
    Output - Token.
    """
    access_code = 401
    status, response = Authentication().node_token(request.data, nodename)
    if status is True:
        access_code=200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@auth_blueprint.route('/filesauth', methods=['GET'])
def auth_get():
    """
    Needed for e.g. --> nginx subrequest auth <--
    Input - just headers -> token + original uri
    Process - Validate the token if needed
    On the success, return a go, else no go
    Output - go/no go
    """
    access_code = 401
    status, response = Authentication().validate_token(request.data,request.headers)
    if status is True:
        access_code = 200
    response = {'message': response}
    return response, access_code
