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
from random import randint
from time import sleep,time
from os import getpid
from utils.helper import Helper
import concurrent.futures
from utils.database import Database
from utils.status import Status
from utils.queue import Queue
from utils.filter import Filter


LOGGER = Log.get_logger()
service_blueprint = Blueprint('service', __name__)
#APIQueue = queue.Queue()

@service_blueprint.route("/service/<string:name>/<string:action>", methods=['GET'])
@token_required
def service(name, action):
    """
    Input - name of service and action need to be perform
    Process - After Validating Token, Check queue if the same request is enque in last two seconds.
              If not then only execute the action with the help of service Class.
    Output - Success or Failure.
    """

    # we do not need the queue for e.g. status
    if action == "status":
        response,code = Service().luna_service(name, action)
        return json.dumps(response), code
        
    code=500
    response= {"message": f'service {name} {action} failed. No sign of life of spawned thread'}
    name = Filter().filter(name,'service')
    action = Filter().filter(action,'action')

    #Antoine
    request_id=str(time())+str(randint(1001,9999))+str(getpid())

    queue_id, queue_response = Queue().add_task_to_queue(f'{name}:{action}','service',request_id)
    if not queue_id:
        LOGGER.info(f"service GET cannot get queue_id")
        response= {"message": f'Service {name} {action} queuing failed'}
        return json.dumps(response), code

    if queue_response != "added": # this means we already have an equal request in the queue
        code=200
        response = {"message": f"service for {name} {action} already queued", "request_id": queue_response}
        LOGGER.info(f"my repsonse [{response}]")
        return json.dumps(response), code

    LOGGER.info(f"service GET added task to queue: {queue_id}")
    Status().add_message(request_id,"luna",f"queued service {name} {action} with queue_id {queue_id}")

    next_id = Queue().next_task_in_queue('service')
    if queue_id == next_id:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(Service().service_mother,name,action,request_id)
        executor.shutdown(wait=False)
#        Service().service_mother(name,action,request_id)

    # we should check after a few seconds if there is a status update for us.
    # if so, that means mother is taking care of things

    sleep(1)
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        code=200
        response = {"message": f"service for {name} {action} queued", "request_id": request_id}
    LOGGER.info(f"my repsonse [{response}]")
    return json.dumps(response), code


@service_blueprint.route('/service/status/<string:request_id>', methods=['GET'])
def service_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """

    access_code = 404
    response = {'message': 'No data for this request'}
    request_id = Filter().filter(request_id,'request_id')
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        message=[]
        for record in status:
            if 'read' in record:
                if record['read']==0:
                    if 'message' in record:
                        if record['message'] == "EOF":
                            #Database().delete_row('status', [{"column": "request_id", "value": request_id}])
                            Status().del_messages(request_id)
                        else:
                            message.append(record['message'])
        response={'message': (';;').join(message) }
        Status().mark_messages_read(request_id)
        access_code = 200
    return json.dumps(response), access_code

