#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This file manages the services.
Mainly two Ssrvices DHCP and DNS, which is mentioned in the .ini file
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

import queue
import time
from flask import Blueprint, json
from utils.log import Log
from utils.service import Service
from common.validate_auth import token_required
from common.constant import CONSTANT


LOGGER = Log.get_logger()
service_blueprint = Blueprint('service', __name__)
APIQueue = queue.Queue()

@service_blueprint.route("/service/<string:name>/<string:action>", methods=['POST'])
@token_required
def service(name, action):
    """
    Input - name of service and action need to be perform
    Process - After Validating Token, Check queue if the same request is enque in last two seconds.
              If not then only execute the action with the help of service Class.
    Output - Success or Failure.
    """
    current_time = round(time.time())
    current_minute = {"name": name, "action": action, "time": current_time}
    last_minute = {"name": name, "action": action, "time": current_time-1}
    if  current_minute in APIQueue.queue or last_minute in APIQueue.queue:
        APIQueue.get() ## Get the Last same Element from Queue
        APIQueue.empty() ## Deque the same element from the Queue
        LOGGER.warning(f'Service {name} is already {action}.')
        response = f'Service {name} is already {action}.'
        code = 204
    else:
        ## Enque the fresh request to the Queue.
        APIQueue.put({"name": name, "action": action, "time": current_time})
        response, code = Service().luna_service(name, action)
        ## Cool Down to Manage the Service itself.
        time.sleep(CONSTANT['SERVICES']['COOLDOWN'])
        LOGGER.info(response)
    return json.dumps(response), code
