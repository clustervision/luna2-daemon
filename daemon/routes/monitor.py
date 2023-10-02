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

This endpoint can be contacted to obtain service status.
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
from common.validate_input import validate_name, input_filter
from base.monitor import Monitor

LOGGER = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)

@monitor_blueprint.route('/monitor/service/<string:name>', methods=['GET'])
@validate_name
def monitor_service(name=None):
    """
    Input - name of service
    Process - With the help of service class, the status of the service can be obtained.
    Currently supported services are DHCP, DNS and luna2 itself.
    Output - Status
    """
    access_code = 503
    status, response = Monitor().service_monitor(name)
    if status is True:
        access_code = 200
    response = {'monitor': {'Service': { name: response} } }
    return response, access_code


@monitor_blueprint.route("/monitor/status/<string:node>", methods=['GET'])
@validate_name
def monitor_status_get(node=None):
    """
    Input - NodeID or node name
    Process - Validate if the node exists and what the state is
    Output - Status.
    """
    access_code = 404
    status, response = Monitor().get_status(node)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        access_code = 404
        response = {'message': f'{node} not found'}
    return response, access_code


@monitor_blueprint.route("/monitor/status/<string:node>", methods=['POST'])
@validate_name
@token_required
@input_filter(checks=['monitor:status'], skip=None)
def monitor_status_post(node=None):
    """
    Input - NodeID or Node Name
    Process - Update the Node Status
    Output - Status.
    """
    access_code = 404
    status, response = Monitor().update_status(node, request.data)
    if status is True:
        access_code = 204
    response = {'message': response}
    return response, access_code
