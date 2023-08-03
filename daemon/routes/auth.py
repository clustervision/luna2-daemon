#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    status, response = Authentication().get_token(request)
    response = dumps(response)
    access_code = 200 if status is True else 401
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
    response, access_code = Authentication().node_token(request, nodename)
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
    response, access_code = Authentication().validate_token(request)
    return response, access_code
