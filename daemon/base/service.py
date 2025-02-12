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
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

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
        status=False
        # we do not need the queue for e.g. status
        if action == "status":
            status, response = service().luna_service(name, action)
            return status, response
        response = f'Internal error: service {name} {action} failed. No sign of life of spawned thread'
        #Antoine
        request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
        queue_id, queue_response = Queue().add_task_to_queue(task=action, param=name, 
                                                             subsystem='service', request_id=request_id)
        if not queue_id:
            self.logger.info("service GET cannot get queue_id")
            status=False
            response = f'Service {name} {action} queuing failed'
            return status, response
        if queue_response != "added": # this means we already have an equal request in the queue
            status=True
            response = f"service for {name} {action} already queued"
            self.logger.info(f"my response [{response}] [{queue_response}]")
            return status, response, queue_response
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
            status=True
            response = f"service for {name} {action} queued"
            self.logger.info(f"my response [{response}] [{request_id}]")
            return status, response, request_id
        return status, response


    # below segment has been moved to Status()
    def get_status(self, request_id=None):
        """
        This method will get the exact status of the service, depends on the request ID.
        """
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
            status=True
            return status, response
        return status, 'No data for this request'
