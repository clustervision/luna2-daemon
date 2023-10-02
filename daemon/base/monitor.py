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


from json import dumps
from utils.log import Log
from utils.service import Service
from utils.helper import Helper
from utils.database import Database
from utils.monitor import Monitor as monitor


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
        returned = service().luna_service(name, 'status')
        status=returned[0]
        response=returned[1]
        return status, response


    def get_status(self, node=None):
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


    def update_status(self, node=None, request_data=None):
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
