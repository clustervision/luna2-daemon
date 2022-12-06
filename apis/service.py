#!/usr/bin/env python3
"""
This file manages the services.
Mainly two Ssrvices DHCP and DNS, which is mentioned in the .ini file
@token_required is a wrapper Method to Validate the POST API. It contains arguments and keyword arguments Of The API
Service Class Have a queue to manage the multiple services.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from common.validate_auth import *
from flask import current_app, Blueprint, request, json
from utils.log import *
from utils.service import *
import queue
import time
import sys
from jinja2 import Environment

logger = Log.get_logger()
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


@service_blueprint.route("/service/reload", methods=['GET'])
def reload():
    """
    TODO: Add docs
    """
    check_dir_read = checkdir(TEMPLATES_DIR)
    if check_dir_read is not True:
        print("TEMPLATES_DIR Directory: {} Is Not Readable.".format(TEMPLATES_DIR))
        sys.exit(0)

    check_dir_write = checkdir(TEMPLATES_DIR)
    if check_dir_write is not True:
        print("TEMPLATES_DIR Directory: {} Is Not Writable.".format(TEMPLATES_DIR))
        sys.exit(0)

    check_boot_ipxe_read = checkfile(TEMPLATES_DIR+"/boot_ipxe.cfg")
    if check_boot_ipxe_read is not True:
        print("Boot PXE File: {} Is Not Readable.".format(TEMPLATES_DIR+"/boot_ipxe.cfg"))
        sys.exit(0)

    check_boot_ipxe_write = checkwritable(TEMPLATES_DIR+"/boot_ipxe.cfg")
    if check_boot_ipxe_write is not True:
        print("Boot PXE File: {} Is Not Writable.".format(TEMPLATES_DIR+"/boot_ipxe.cfg"))
        sys.exit(0)
    if check_boot_ipxe_read and check_boot_ipxe_write:
        with open(TEMPLATES_DIR+"/boot_ipxe.cfg", "r") as newbootfile:
            newbootfile = newbootfile.readlines()
    parse = None
    error = ""
    if newbootfile != bootfile:
        try:
            env = Environment()
            with open(TEMPLATES_DIR+"/boot_ipxe.cfg") as template:
                parse = env.parse(template.read())
                parse = False
        except Exception as e:
            parse = True
            error = e
    if parse:
        logger.error(str(error))
        abort(503, str(error))
    else:
        response, code = Service().luna_service("luna2-daemon", "reload")
        return json.dumps(response), code
