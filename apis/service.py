#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File Manage the Services, such as DHCP as dhcpd and DNS as named.

"""

from common.constants import *
from common.validate_auth import *
from flask import current_app, Blueprint, request, json
from utils.log import *
from utils.service import *
import queue
import time
from time import sleep

logger = Log.get_logger()
service_blueprint = Blueprint('service', __name__)
APIQueue = queue.Queue()


"""
/service will receive the service name and action.
With the Help of Service Class perform the action
"""
@service_blueprint.route("/service/<string:name>/<string:action>", methods=['POST'])
# @token_required
def service(name, action):
    currentTime = round(time.time())
    if {"name": name, "action": action, "time": currentTime} in APIQueue.queue or {"name": name, "action": action, "time": currentTime-1} in APIQueue.queue:
        APIQueue.get()
        APIQueue.empty()
        response = "Service {} already {}.".format(name, action)
        code = 204
        logger.warning(response)
    else:
        APIQueue.put({"name": name, "action": action, "time": currentTime})
        response, code = Service().luna_service(name, action)
        sleep(COOLDOWN)
        logger.info(response)
    return json.dumps(response), code