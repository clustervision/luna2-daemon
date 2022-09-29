#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point to Monitor the services.

"""

from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *
from utils.service import *

logger = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)


"""
Input - name of service
Process - With the help of Serive Class, we can get the exact status of the service. which is DHCP, DNS and luna2
Output - Status.
"""
@monitor_blueprint.route("/monitor/service/<string:name>", methods=['GET'])
def monitor_service(name=None):
    action = "status"
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Validate if the Node is Exists and UP
Output - Status.
"""
@monitor_blueprint.route("/monitor/status/<string:node>", methods=['GET'])
def monitor_status_get(node=None):
    status = True
    if status:
        logger.info("Node {} is UP And Running".format(node))
        response = {"message": "Node {} is UP And Running".format(node)}
        code = 200
    else:
        logger.info("Node {} is Down And Not Running".format(node))
        response = {"message": "Node {} is Down And Not Running".format(node)}
        code = 404
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Update the Node Status
Output - Status.
"""
@monitor_blueprint.route("/monitor/status/<string:node>", methods=['POST'])
def monitor_status_post(node=None):
    status = True
    if status:
        logger.info("Node {} is Updated.".format(node))
        response = {"message": "Node {} is Updated.".format(node)}
        code = 200
    else:
        logger.info("Node {} is Down And Not Running".format(node))
        response = {"message": "Node {} is Down And Not Running".format(node)}
        code = 404
    return json.dumps(response), code