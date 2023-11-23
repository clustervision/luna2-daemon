
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
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from time import sleep, time
from random import randint
from utils.log import Log
from utils.database import Database
#from utils.helper import Helper


class Status(object):

    def __init__(self):
        self.logger = Log.get_logger()


    def gen_request_id(self):
        return str(time()) + str(randint(1001, 9999)) + str(getpid())


    def add_message(self,request_id,username_initiator,message):
        mymessage=f"{message}"
        mymessage=mymessage.replace('"',"'")
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
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            message = []
            for record in status:
                if 'read' in record:
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


    def forward_messages(remote_request_id, remote_host, local_request_id):
        """
        forward local request_id based status message to another host.
        """
        loop=True
        while loop is True:
            status = Database().get_record(None , 'status', f' WHERE request_id = "{local_request_id}"')
            if status:
                message = []
                for record in status:
                    if 'read' in record and record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                self.del_messages(request_id)
                                loop=False
                            message.append(record)
                response = {'request_id': remote_request_id, 'messages': message}
                self.mark_messages_read(request_id)
                Request.post_request(remote_host,'/status',response)
            sleep(5)

