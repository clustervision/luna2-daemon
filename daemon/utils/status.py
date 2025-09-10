
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


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is a class to assist in Status related items. e.g. the cleanup thread lives here.

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from os import getpid
from time import sleep, time
from random import randint
from utils.log import Log
from utils.database import Database
from utils.request import Request
#from utils.helper import Helper


class Status(object):

    def __init__(self):
        self.logger = Log.get_logger()


    def gen_request_id(self):
        return str(time()) + str(randint(1001, 9999)) + str(getpid())


    def add_message(self,request_id,username_initiator,message,remote_request_id=None,remote_host=None):
        mymessage=f"{message}"
        mymessage=mymessage.replace("b'", '')
        mymessage=mymessage.replace("'",'')
        mymessage=mymessage.replace('"','')
        #current_datetime=datetime.now().replace(microsecond=0)
        current_datetime="NOW"
        row=[{"column": "request_id", "value": f"{request_id}"},
             {"column": "created", "value": str(current_datetime)},
             {"column": "username_initiator", "value": f"{username_initiator}"},
             {"column": "read", "value": "0"},
             {"column": "message", "value": f"{mymessage}"}]
        if remote_request_id and remote_host:
            row.append({"column": "remote_request_id", "value": remote_request_id})
            row.append({"column": "remote_host", "value": remote_host})
        Database().insert('status', row)


    def add_remote_message(self,request_id,username_initiator,message,remote_):
        mymessage=f"{message}"
        mymessage=mymessage.replace("b'", '')
        mymessage=mymessage.replace("'", '"')
        mymessage=mymessage.replace('"','')
        #current_datetime=datetime.now().replace(microsecond=0)
        current_datetime="NOW"
        row=[{"column": "request_id", "value": f"{request_id}"},
             {"column": "created", "value": str(current_datetime)},
             {"column": "username_initiator", "value": f"{username_initiator}"},
             {"column": "read", "value": "0"},
             {"column": "message", "value": f"{mymessage}"}]
        Database().insert('status', row)


    def mark_messages_read(self,request_id,id=None):
        where = [{"column": "request_id", "value": request_id}]
        row = [{"column": "read", "value": "1"}]
        Database().update('status', row, where)


    def del_message(self,id):
        pass


    def del_messages(self,request_id):
        Database().delete_row('status', [{"column": "request_id", "value": request_id}])


    def get_status(self, request_id):
        """
        This method will get the exact status from queue, depends on the request ID.
        """
        status = Database().get_record(table='status', where=f'request_id = "{request_id}"')
        if status:
            message = []
            for record in status:
                if record['remote_host'] and record['remote_request_id']:
                    status, response = Request().get_request(record['remote_host'], f"/config/status/{record['remote_request_id']}")
                    if status is False:
                        self.mark_messages_read(request_id)
                    return status, response
                    continue
                else:
                    if record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                self.del_messages(request_id)
                            else:
                                created, *_ = record['created'].split('.') + [None]
                                message.append(created + " :: " + record['message'])
            response = {'message': (';;').join(message) }
            self.mark_messages_read(request_id)
            return True, response
        return False, 'No data for this request'


    def forward_messages(self, remote_request_id, remote_host, local_request_id):
        """
        forward local request_id based status message to another host.
        """
        self.logger.info(f"forwarding messages for {local_request_id} to {remote_host}:{remote_request_id}")
        loop=True
        while loop is True:
            status = Database().get_record(table='status', where=f'request_id = "{local_request_id}"')
            if status:
                messages = []
                for record in status:
                    if 'read' in record and record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                self.del_messages(local_request_id)
                                loop=False
                            messages.append(record)
                response = {'monitor': {'status': {'request_id': remote_request_id, 'messages': messages}}}
                self.mark_messages_read(local_request_id)
                Request().post_request(remote_host, '/monitor/status', response)
            sleep(5)
        self.logger.info(f"no (more) messages for {local_request_id} to be forwarded to {remote_host}:{remote_request_id}")


    def forward_status_request(self, remote_request_id, remote_host, local_request_id, local_host):
        """
        forward local request_id based status message to another host.
        """
        self.logger.info(f"forwarding request_id for {local_request_id} to {remote_host}:{remote_request_id}")
        response = {'monitor': {'status': {'request_id': remote_request_id, 'remote_request_id': local_request_id, 'remote_host': local_host}}}
        self.logger.debug(f"RESPONSE: {response}")
        status,response=Request().post_request(remote_host, '/monitor/status', response)
        return status, response


