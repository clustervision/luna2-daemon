#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file manages the services.
Mainly two Services DHCP and DNS, which is mentioned in the .ini file
@token_required is a wrapper Method to Validate the POST API.
It contains arguments and keyword arguments Of The API
Service Class Have a queue to manage the multiple services.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from flask import Blueprint
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import validate_name
from base.service import Service


LOGGER = Log.get_logger()
service_blueprint = Blueprint('service', __name__)


@service_blueprint.route("/service/<string:name>/<string:action>", methods=['GET'])
@token_required
@validate_name
def service(name, action):
    """
    Input - name of service and action need to be perform
    Process - After Validating Token, Check queue if the same request is enqueue in last two
        seconds. If not then only execute the action with the help of service Class.
    Output - Success or Failure.
    """
    response, access_code = Service().service_action(name, action)
    return response, access_code


@service_blueprint.route('/service/status/<string:request_id>', methods=['GET'])
@validate_name
def service_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """
    response, access_code = Service().get_status(request_id)
    return response, access_code
