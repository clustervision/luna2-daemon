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


import re
from utils.log import Log
from utils.service import Service
from utils.helper import Helper
from utils.database import Database
from utils.monitor import Monitor as monitor
from utils.status import Status


class Monitor():
    """
    This class is responsible to monitor all the services.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def service_monitor(self, name=None):
        """
        This method will check the status of a service
        """
        status=False
        if name == "luna2":
            # response, code = Helper().checkdbstatus()
            response, status = 'Helper Method checkdbstatus is missing', True
            self.logger.info(f'Database status is: {response}.')
        returned = Service().luna_service(name, 'status')
        status=returned[0]
        response=returned[1]
        return status, response


    def get_nodestatus(self, node=None):
        """
        This method will check the status of a node
        """
        status=False
        response = {"monitor": {"status": { node: { } } } }
        nodes = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
        if nodes:
            status,servicestatus=monitor().installer_state(nodes[0]['status'])
            response['monitor']['status'][node]['status'] = servicestatus
            response['monitor']['status'][node]['state'] = nodes[0]['status']
        else:
            response = None
            status=False
        return status, response


    def update_nodestatus(self, node=None, request_data=None):
        """
        This method will update the status of a node
        """
        status=False
        response = 'Bad Request'
        if request_data:
            try:
                state = request_data['monitor']['status'][node]['state']
                where = f' WHERE id = "{node}" OR name = "{node}";'
                node_db = Database().get_record(None, 'node', where)
                if node_db:
                    self.logger.info(f"node {node}: {state}")
                    row = [{"column": "status", "value": state}]
                    where = [{"column": "name", "value": node}]
                    Database().update('node', row, where)
                    status=True
                    response = f'Node {node} updated'
                else:
                    response = 'Node is not present'
                    status=False
            except KeyError:
                response = 'Invalid request: URL Node is not matching with requested node'
                status=False
        return status, response


    def get_queue(self):
        """
        This method generates a list of tasks in the queue
        """
        status=True
        response = []
        queue = Database().get_record(None, 'queue', "ORDER BY created ASC")
        if queue:
            status=True
            regex=re.compile(r"^.*:noeof$")
            for task in queue:
                details={}
                for item in ['request_id','username_initiator','created','subsystem','task','status']:
                    if item == 'task':
                        if regex.match(task['task']):
                            details['level']='subtask'
                        else:
                            details['level']='maintask'
                    details[item]=task[item]
                response.append(details)
        return status, response


    def get_status(self):
        """
        This method generates a list of messages in the status table
        """
        status=True
        response = []
        statuslist = Database().get_record(None, 'status', "ORDER BY created ASC")
        if statuslist:
            status=True
            for line in statuslist:
                details={}
                for item in ['request_id','username_initiator','created','read','message']:
                    details[item]=line[item]
                response.append(details)
        return status, response


    def insert_status_messages(self, request_data=None):
        status=False
        response = 'Bad Request'
        remote_request_id, remote_host = None, None
        if request_data:
            data=request_data['monitor']['status']
            if 'request_id' in data and 'messages' in data:
                status=True
                response="success"
                if 'remote_request_id' in data and 'remote_host' in data:
                    remote_request_id = data['remote_request_id']
                    remote_host = data['remote_host']
                for record in data['messages']:
                    if 'message' in record:
                        Status().add_message(data['request_id'], '__remote__', record['message'], remote_request_id, remote_host)
        return status, response



