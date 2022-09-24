#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File Manage the Services.
Mainly Two Services DHCP and DNS, which is mentioned in the .conf file
@token_required is a Wrapper Method to Validate the POST API. It contains arguments and keyword arguments Of The API
Service Class Have a Queue to Manage the Multiple Services.

"""

from common.constants import *
from common.validate_auth import *
from flask import current_app, Blueprint, request, json
from utils.log import *
from utils.service import *
import queue
import time

logger = Log.get_logger()
service_blueprint = Blueprint('service', __name__)
APIQueue = queue.Queue()


"""
Input - name of service and action need to be perform
Process - After Validating Token, Check Queue if the same request is enque in last two seconds. If Not Then only execute the action with the Help of Service Class.
Output - Success or Failure.
"""
@service_blueprint.route("/service/<string:name>/<string:action>", methods=['POST'])
@token_required
def service(name, action):
    currentTime = round(time.time())
    if {"name": name, "action": action, "time": currentTime} in APIQueue.queue or {"name": name, "action": action, "time": currentTime-1} in APIQueue.queue:
        APIQueue.get() ## Get the Last same Element from Queue
        APIQueue.empty() ## Deque the same element from the Queue
        logger.warning("Service {} is already {}.".format(name, action))
        response = "Service {} is already {}.".format(name, action)
        code = 204
    else:
        APIQueue.put({"name": name, "action": action, "time": currentTime}) ## Enque the fresh request to the Queue.
        response, code = Service().luna_service(name, action)
        time.sleep(COOLDOWN) ## Cool Down to Manage the Service itself.
        logger.info(response)
    return json.dumps(response), code