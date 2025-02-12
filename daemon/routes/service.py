#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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

This file manages the services.
Mainly two Services DHCP and DNS, which is mentioned in the .ini file
@token_required is a wrapper Method to Validate the POST API.
It contains arguments and keyword arguments Of The API
Service Class Have a queue to manage the multiple services.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import validate_name
from base.service import Service
from utils.status import Status


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
    access_code = 404
    returned = Service().service_action(name, action)
    status = returned[0]
    message = returned[1]
    if status is True:
        access_code = 200
        if len(returned) == 3:
            request_id = returned[2]
            response = {"message": message, "request_id": request_id}
        else:
            response = {'info': message}
    else:
        if 'config has error' in message or action == 'status':
            # we have no issues with reporting the failed service. is this 500 or 200 ??
            access_code = 503
        response = {'error': message}
    # Antoine - aug 5 2023 - bit ugly workaround for status as API expects monitor as response
    if action == 'status':
        response = {'monitor': {'Service': { name: message} } }
    return response, access_code


@service_blueprint.route('/service/status/<string:request_id>', methods=['GET'])
@validate_name
def service_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """
    access_code = 404
    status, response = Status().get_status(request_id)
    if status is True:
        access_code=200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code
