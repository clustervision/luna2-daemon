#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This file is the entry point for provisioning
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
from common.validate_auth import token_required
from common.validate_input import validate_name, input_filter
from base.control import Control

LOGGER = Log.get_logger()
control_blueprint = Blueprint('control', __name__)


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@control_blueprint.route('/control/power/<string:hostname>/<string:action>', methods=['GET'])
@token_required
@validate_name
def control_get(hostname=None, action=None):
    """
    Input - hostname & action
    Process - Use to perform on, off, reset operations on one node.
    Output - Success or failure
    """
    access_code=404
    status, response = Control().power_action(hostname, action)
    if status is True:
        access_code=204
        if 'status' in action:
            access_code=200
        response=dumps(response)
    else:
        response={'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@control_blueprint.route('/control/power', methods=['POST'])
@token_required
@input_filter(checks=['control:power'], skip=None)
def control_post():
    """
    Input - hostname & action
    Process - Use to perform on, off, reset operations on one node.
    Output - Success or failure
    """
    access_code=404
    status, response = Control().bulk_action(request)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response={'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@control_blueprint.route('/control/status/<string:request_id>', methods=['GET'])
@validate_name
def control_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """
    access_code=404
    # we cannot use Status().get_status as there is too much customization
    status, response = Control().get_status(request_id)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response={'message': response}
    return response, access_code
