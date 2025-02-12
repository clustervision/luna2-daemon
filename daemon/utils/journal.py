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
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import sys
import re
import hashlib
from multiprocessing import Lock
from threading import Semaphore, Lock as tLock
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
from utils.request import Request
from utils.ha import HA
from utils.tables import Tables
from utils.downloader import Downloader
from utils.controller import Controller

from base.node import Node
from base.group import Group
from base.interface import Interface
from base.osimage import OSImage
from base.cluster import Cluster
from base.bmcsetup import BMCSetup
from base.switch import Switch
from base.otherdev import OtherDev
from base.rack import Rack
from base.network import Network
from base.dns import DNS
from base.secret import Secret
from base.osuser import OsUser
from base.monitor import Monitor
from base.cloud import Cloud
from base.plugin_import import Import

lock = Lock()
#sem = Semaphore()
sem = tLock()

class Journal():
    """
    This class is responsible for all journal and replication operations
    """

    def __init__(self,me=None,shadow=None):
        self.logger = Log.get_logger()
        self.ha_object = HA()
        self.sharedip = self.ha_object.get_sharedip()
        self.beacon = Controller().get_beacon()
        self.me=me
        self.shadow=shadow
        if not self.me:
            self.me=self.ha_object.get_me()
        if self.shadow is None:
            self.shadow=self.ha_object.get_shadow()
        
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6',
                                                           'network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')


    def get_me(self):
        return self.me


    def add_request(self,function,object=None,param=None,payload=None,masteronly=False,misc=None,sendnow=True,keeptrying=5):
        if not self.ha_object.get_hastate():
            return True, "Not in H/A mode"
        if not self.ha_object.get_overrule():
            while not self.ha_object.get_insync() and keeptrying>0:
                sleep(1)
                keeptrying-=1
            if not self.ha_object.get_insync():
                return False, "Currently not able to handle request as i am not in sync yet"
        if payload:
            encoded = None
            try:
                string = dumps(payload)
                encoded = b64encode(string.encode())
            except:
                encoded = b64encode(payload)
            payload = encoded.decode("ascii")
        if self.me:
            if self.all_controllers:
                data={}
                data['function'] = function
                data['object'] = object
                data['param'] = param
                data['payload'] = payload
                data['masteronly'] = Helper().bool_to_string(masteronly)
                data['misc'] = misc
                data['sendby'] = self.me
                data['sendto'] = None
                data['created'] = "NOW"
                data['tries'] = "0"
                for controller in self.all_controllers:
                    if controller['hostname'] == self.me:
                        continue
                    elif self.sharedip and controller['beacon']:
                        continue
                    if self.shadow and controller['shadow']:
                        data['sendto'] = self.beacon
                    data['sendfor'] = controller['hostname']
                    row = Helper().make_rows(data)
                    request_id = Database().insert('journal', row)
                    self.logger.info(f"adding {function}({object},{param},payload) to journal for {controller['hostname']} with id {request_id}")
                if sendnow is True:
                    executor = ThreadPoolExecutor(max_workers=1)
                    executor.submit(self.pushto_controllers)
                    executor.shutdown(wait=False)
                    #self.pushto_controllers()
            else:
                self.logger.error(f"No controllers are configured")
        else:
            self.logger.error(f"I do not know who i am. cannot replicate")
        return True, "request added to journal"


    def handle_requests(self):
        status=False
        if self.me:
            all_records = Database().get_record(["*","strftime('%s',created) AS createdsec"],'journal',f"WHERE sendfor='{self.me}' ORDER BY created,id ASC")
            if all_records:
                master=HA().get_role()
                status=True
                for record in all_records:
                    masteronly=Helper().make_bool(record['masteronly'])
                    self.logger.debug(f"master: {master}, masteronly: {masteronly}")
                    if masteronly is True and master is False:
                        self.logger.info(f"request {record['function']}({record['object']}) is not for us. master ({master}) != masteronly ({masteronly})")
                        Database().delete_row('journal', [{"column": "id", "value": record['id']}])
                        continue
   
                    payload=None
                    if record['payload']:
                        payload = None
                        decoded = b64decode(record['payload'])
                        string = decoded.decode("ascii")
                        try:
                            payload = loads(string)
                        except:
                            payload = string
                        self.logger.debug(f"replication payload: {payload}")
                   
                    class_name,function_name=record['function'].split('.')
                    self.logger.info(f"executing {class_name}().{function_name}({record['object']},{record['param']},payload)/{record['tries']} send by {record['sendby']} on {record['created']}")

                    returned=[]
                    repl_class = globals()[class_name]                # -> base.node.Node
                    repl_function = getattr(repl_class,function_name) # -> base.node.Node.node_update

                    # introducing some uglyness since we do not use the created field in classes.
                    if class_name == "HA" and function_name == "set_role":
                        returned=repl_function(repl_class(),record['object'],record['createdsec'])
                    elif record['param'] and payload:
                        returned=repl_function(repl_class(),record['object'],record['param'],payload)
                    elif record['param']:
                        returned=repl_function(repl_class(),record['object'],record['param'])
                    elif record['object'] and payload:
                        returned=repl_function(repl_class(),record['object'],payload)
                    elif payload:
                        returned=repl_function(repl_class(),payload)
                    else:
                        returned=repl_function(repl_class(),record['object'])
                    if returned:
                        status_, message = None, None
                        if isinstance(returned, bool):
                            status_=returned
                            self.logger.info(f"result for {record['function']}({record['object']}): {status_}")
                        elif isinstance(returned, int):
                            status_=returned
                            self.logger.info(f"result for {record['function']}({record['object']}): {status_}")
                        else:
                            status_=returned[0]
                            message=returned[1]

                            self.logger.info(f"result for {record['function']}({record['object']}): {status_}, {message}")
                            request_id=None
                            if len(returned)>2:
                                request_id=returned[2]

                            if class_name == 'OSImage':
                                if status_ is True:
                                    if function_name in ['pack','change_kernel']:
                                        self.queue_source_sync(record['object'],request_id)
                                    elif function_name == 'clone_osimage':
                                        self.logger.debug(f"CLONE object: {record['object']}, payload: {payload}")
                                        self.queue_target_sync(record['object'],payload,request_id)
                                    elif function_name == 'grab':
                                        self.queue_source_sync_by_node_name(record['object'],request_id)
                                else:
                                    # something went wrong. we have to inform the remote host
                                    if not request_id:
                                        request_id=str(time()) + str(randint(1001, 9999)) + str(getpid())
                                    Status().add_message(request_id, "luna", message)
                                    Status().add_message(request_id, "luna", "EOF")
                                        
                                if record['misc'] and request_id:
                                    # we have to keep track of the request_id as we have to inform the requestor about the progress.
                                    Status().forward_status_request(record['misc'], record['sendby'], request_id, self.me)
                    else:
                        self.logger.info(f"result for {record['function']}({record['object']}): {returned}")

                    # we *always* have to remove the entries in the DB regarding outcome.
                    Database().delete_row('journal', [{"column": "id", "value": record['id']}])
        return status


    def queue_source_sync(self,source,request_id=None):
        try:
            queue_id,queue_response = Queue().add_task_to_queue(task='sync_osimage_with_master', param=f'{source}:{self.me}',
                                                                subsystem='osimage', request_id=request_id)
            if queue_id:
                Queue().update_task_status_in_queue(queue_id,'parked')
        except Exception as exp:
            self.logger.error(f"{exp}")

    def queue_target_sync(self,source,payload,request_id=None):
        try:
            target=payload['config']['osimage'][source]['name']
            self.queue_source_sync(target,request_id)
        except Exception as exp:
            self.logger.error(f"{exp}")

    def queue_source_sync_by_node_name(self,name,request_id=None):
        try:
            _,node_config=Node().get_node(None,name)
            if node_config and 'config' in node_config and 'node' in node_config['config'] and name in node_config['config']['node']:
                osimage = node_config['config']['node'][name]['osimage']
                self.queue_source_sync(osimage,request_id)
        except Exception as exp:
            self.logger.error(f"{exp}")


    def pushto_controllers(self,forward=None):
        if self.me and self.dict_controllers:
            lock.acquire()
            try:
                sem.acquire()
                try:
                    all_entries={}
                    del_ids={}
                    host_key=None
                    query=None
                    # do we only push the forwarded ones or everything?
                    if forward:
                        query=f"sendto='{self.me}'"
                    else:
                        query=f"sendby='{self.me}' OR sendto='{self.me}'"
                    # we fetch all journal coming from me (sendby) or from some other host that i need to forward as replicator (sendto)
                    all_records = Database().get_record(["*","strftime('%s',created) AS created"],"journal",f"WHERE {query} ORDER BY sendfor,created,id ASC")
                    if all_records:
                        for record in all_records:
                            # we have journal for a host but send it to a replicator
                            if record['sendto'] and record['sendby'] == self.me:
                                host_key = record['sendto']
                            # we either have journal for a host coming from us, or it's replication
                            else:
                                host_key = record['sendfor']
                            if not host_key in all_entries:
                                all_entries[host_key]=[]
                            if not host_key in del_ids:
                                del_ids[host_key]=[]
                            del_ids[host_key].append(record['id'])
                            del record['id']
                            all_entries[host_key].append(record)
                        for host in all_entries:
                            self.logger.debug(f"JOURNAL HOST {host}: {all_entries[host]}")
                            status,_=Request().post_request(host,'/journal',{'journal': all_entries[host]})
                            if status is True:
                                for del_id in del_ids[host]:
                                    Database().delete_row('journal', [{"column": "id", "value": del_id}])
                            else:
                                self.logger.error(f"attempt to push journal to {host} failed. host might be down.")
                finally:
                    sem.release()
            finally:
                lock.release()
        return


    def pullfrom_controllers(self):
        if self.me:
            if self.all_controllers:
                for controller in self.all_controllers:
                    if controller['hostname']  == self.me:
                        continue
                    elif self.sharedip and controller['beacon']:
                        continue
                    if self.shadow and controller['shadow']:
                        self.logger.info(f"skipping pull journal from {controller['hostname']} being marked shadow")
                        continue
                    self.logger.info(f"pulling journal from {controller['hostname']}")
                    status=self.pull_journal(controller['hostname'])
                    self.logger.info(f"pulling status: {status}")
                    if status is False:
                        return False
                    #status=self.delete_journal(controller['hostname'])
                    #if status is False:
                    #    return False
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
        
