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

from json import dumps
from random import randint
from time import sleep, time
from os import getpid
from concurrent.futures import ThreadPoolExecutor
from utils.log import Log
from utils.service import Service as service
from utils.database import Database
from utils.status import Status
from utils.queue import Queue


class Service():
    """
    This class is responsible for all service operations.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def service_action(self, name=None, action=None):
        """
        This method will perform all the operations on all the services.
        such as dhcp or dns restart, reload, status, etc.
        """
        # we do not need the queue for e.g. status
        if action == "status":
            response, code = service().luna_service(name, action)
            return dumps(response), code
        code = 500
        response = {"message": f'service {name} {action} failed. No sign of life of spawned thread'}
        #Antoine
        request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
        queue_id, queue_response = Queue().add_task_to_queue(
            f'{name}:{action}',
            'service',
            request_id
        )
        if not queue_id:
            self.logger.info("service GET cannot get queue_id")
            response = {"message": f'Service {name} {action} queuing failed'}
            return dumps(response), code
        if queue_response != "added": # this means we already have an equal request in the queue
            code = 200
            response = {
                "message": f"service for {name} {action} already queued",
                "request_id": queue_response
            }
            self.logger.info(f"my response [{response}]")
            return dumps(response), code
        self.logger.info(f"service GET added task to queue: {queue_id}")
        Status().add_message(
            request_id,
            "luna",
            f"queued service {name} {action} with queue_id {queue_id}"
        )
        next_id = Queue().next_task_in_queue('service')
        if queue_id == next_id:
            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(service().service_mother, name, action, request_id)
            executor.shutdown(wait=False)
            # Service().service_mother(name,action,request_id)
        # we should check after a few seconds if there is a status update for us.
        # if so, that means mother is taking care of things
        sleep(1)
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            code = 200
            response = {"message": f"service for {name} {action} queued", "request_id": request_id}
        self.logger.info(f"my response [{response}]")
        return dumps(response), code


    def get_status(self, request_id=None):
        """
        This method will get the exact status of the service, depends on the request ID.
        """
        access_code = 404
        response = {'message': 'No data for this request'}
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            message = []
            for record in status:
                if 'read' in record:
                    if record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                # Database().delete_row(
                                # 'status', [{"column": "request_id", "value": request_id}]
                                # )
                                Status().del_messages(request_id)
                            else:
                                message.append(record['message'])
            response = {'message': (';;').join(message) }
            Status().mark_messages_read(request_id)
            access_code = 200
        return dumps(response), access_code
