#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""
Journal class tracks incoming requests that requires replication to other controllers.
It also receives requests that need to be dealt with by the controller itself.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import re
import hashlib
from time import sleep, time
from os import getpid, path
from random import randint
from base64 import b64decode, b64encode
from concurrent.futures import ThreadPoolExecutor
from json import dumps,loads
from common.constant import CONSTANT
from utils.status import Status
from utils.osimage import OsImage as OsImager
from utils.database import Database
from utils.log import Log
from utils.queue import Queue
from utils.helper import Helper
from utils.model import Model
from utils.tables import Tables
from utils.request import Request
from utils.ha import HA

from base.node import Node
from base.group import Group
from base.interface import Interface
from base.osimage import OSImage
from base.cluster import Cluster
from base.bmcsetup import BMCSetup
from base.switch import Switch
from base.otherdev import OtherDev
from base.network import Network
from base.dns import DNS
from base.secret import Secret
from base.osuser import OsUser

# id, function, object, payload, sendfor sendby tries created

class Journal():
    """
    This class is responsible for all journal and replication operations
    """

    def __init__(self,me=None):
        self.logger = Log.get_logger()
        self.me=me
        if not self.me:
            self.me=HA().get_me()
        self.insync=False
        self.hastate=None
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')


    def get_me(self):
        return self.me


    def add_request(self,function,object,param=None,payload=None):
        if not HA().get_hastate():
            return True, "Not in H/A mode"
        if not HA().get_insync():
            return False, "Currently not able to handle request as i am not in sync yet"
        if payload:
            string = dumps(payload)
            encoded = b64encode(string.encode())
            payload = encoded.decode("ascii")
        if self.me:
            if self.all_controllers:
                data={}
                data['function'] = function
                data['object'] = object
                data['param'] = param
                data['payload'] = payload
                data['sendby'] = self.me
                data['created'] = "NOW"
                data['tries'] = "0"
                for controller in self.all_controllers:
                    if controller['hostname'] in ["controller",self.me]:
                        continue
                    data['sendfor'] = controller['hostname']
                    row = Helper().make_rows(data)
                    request_id = Database().insert('journal', row)
                    self.logger.info(f"adding {function}({object},{param},payload) to journal for {controller['hostname']} with id {request_id}")
                self.pushto_controllers()
            else:
                self.logger.error(f"No controllers are configured")
        else:
            self.logger.error(f"I do not know who i am. cannot replicate")
        return True, "request added to journal"


    def handle_requests(self):
        status=False
        if self.me:
            all_records = Database().get_record(None,'journal',f"WHERE sendfor='{self.me}' ORDER BY created,id ASC")
            if all_records:
                status=True
                for record in all_records:
                    payload=None
                    if record['payload']:
                        decoded = b64decode(record['payload'])
                        string = decoded.decode("ascii")
                        payload = loads(string)
                        self.logger.debug(f"replication payload: {payload}")
                   
                    class_name,function_name=record['function'].split('.')
                    self.logger.info(f"executing {class_name}().{function_name}({record['object']},{record['param']},payload)/{record['tries']} received by {record['sendby']} on {record['created']}")

                    repl_class = globals()[class_name]                # -> base.node.Node
                    repl_function = getattr(repl_class,function_name) # -> base.node.Node.node_update
                    if record['param'] and payload:
                        status_,message=repl_function(repl_class(),record['object'],record['param'],payload)
                    if record['param']:
                        status_,message=repl_function(repl_class(),record['object'],record['param'])
                    elif record['object'] and payload:
                        status_,message=repl_function(repl_class(),record['object'],payload)
                    elif payload:
                        status_,message=repl_function(repl_class(),payload)
                    else:
                        status_,message=repl_function(repl_class(),record['object'])

                    self.logger.info(f"result for {record['function']}({record['object']}): {status_}, {message}")
                    # we always have to remove the entries in the DB regarding outcome.
                    Database().delete_row('journal', [{"column": "id", "value": record['id']}])
        return status


    def pushto_controllers(self):
        if self.me and self.dict_controllers:
            current_controller=None
            failed_controllers=[]
            all_records = Database().get_record(["*","strftime('%s',created) AS created"],"journal",f"WHERE sendby='{self.me}' ORDER BY sendfor,created,id ASC")
            if all_records:
                for record in all_records:
                    if (not current_controller) or current_controller != record['sendfor']:
                        current_controller=record['sendfor']
                    if current_controller not in failed_controllers:
                        function=record['function']
                        object=record['object']
                        param=record['param']
                        payload=record['payload']
                        host=record['sendfor']
                        created=record['created']
                        status=self.send_request(host=host,function=function,object=object,param=param,created=created,payload=payload)
                        if status is True:
                            Database().delete_row('journal', [{"column": "id", "value": record['id']}])
                        else:
                            failed_controllers.append(current_controller)
                            self.logger.error(f"attempt to sync {current_controller} failed. stopping all attempts for this controller")
        return


    def send_request(self,host,function,object,created,param=None,payload=None):
        entry={'journal': [{'function': function, 'object': object, 'param': param, 'payload': payload, 'sendfor': host, 'sendby': self.me, 'created': created}] }
        status,_=Request().post_request(host,'/journal',entry)
        if status is False:
            self.logger.info(f"journal for {function}({object})/payload forward to {host} failed")
        return status


    def pullfrom_controllers(self):
        if self.me:
            if self.all_controllers:
                for controller in self.all_controllers:
                    if controller['hostname'] in ["controller",self.me]:
                        continue
                    self.logger.info(f"pulling journal from {controller['hostname']}")
                    status=self.pull_journal(controller['hostname'])
                    self.logger.info(f"pulling status: {status}")
                    if status is False:
                        return False
                    status=self.delete_journal(controller['hostname'])
                    if status is False:
                        return False
        return True


    def pull_journal(self,host):
        status,data=Request().get_request(host,f'/journal/{self.me}')
        if status is True and data:
            if 'journal' in data:
                NDATA=data['journal']
                for entry in NDATA:
                    row = Helper().make_rows(entry)
                    request_id = Database().insert('journal', row)
                return True
        else:
            self.logger.error(f"journal pull from {host} failed")
        return status


    def delete_journal(self,host):
        status,_=Request().get_request(host,f'/journal/{self.me}/_delete')
        if status is False:
            self.logger.error(f"journal delete from {host} failed")
        return status
        
