#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This endpoint can be contacted to obtain service status.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


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
    status, response = Monitor().service_monitor(name)
    response={'monitor': {'Service': { name: response} } }
    return response, access_code


@monitor_blueprint.route("/monitor/status/<string:node>", methods=['GET'])
@validate_name
def monitor_status_get(node=None):
    """
    Input - NodeID or node name
    Process - Validate if the node exists and what the state is
    Output - Status.
    """
    access_code=404
    status, response = Monitor().get_status(node)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        access_code=404
        response={'message': f'{node} not found'}
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
    access_code=404
    status, response = Monitor().update_status(node, request)
    if status is True:
        access_code=204
    response={'message': response}
    return response, access_code

