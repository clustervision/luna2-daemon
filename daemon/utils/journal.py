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
import netifaces as ni
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
from utils.ha import HA

import requests
from requests import Session
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util import Retry

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

urllib3.disable_warnings()
session = Session()
retries = Retry(
    total = 10,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500, 404],
    allowed_methods = {'GET', 'POST'}
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# id, function, object, payload, sendfor sendby tries created

class Journal():
    """
    This class is responsible for all journal and replication operations
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.protocol = CONSTANT['API']['PROTOCOL']
        _,self.alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.me=None
        self.insync=False
        self.hastate=None
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')
            for interface in ni.interfaces():
                ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
                self.logger.debug(f"Interface {interface} has ip {ip}")
                for controller in self.all_controllers:
                    if controller['hostname'] == "controller":
                        continue
                    if not self.me and controller['ipaddress'] == ip:
                        self.me=controller['hostname']
                        self.logger.info(f"My ipaddress is {ip} and i am {self.me}")

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
        if self.me:
            all_records = Database().get_record(None,'journal',f"WHERE sendfor='{self.me}' ORDER BY created,id ASC")
            if all_records:
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
                        status,message=repl_function(repl_class(),record['object'],record['param'],payload)
                    if record['param']:
                        status,message=repl_function(repl_class(),record['object'],record['param'])
                    elif record['object'] and payload:
                        status,message=repl_function(repl_class(),record['object'],payload)
                    elif payload:
                        status,message=repl_function(repl_class(),payload)
                    else:
                        status,message=repl_function(repl_class(),record['object'])

                    self.logger.info(f"result for {record['function']}({record['object']}): {status}, {message}")
                    # we always have to remove the entries in the DB regarding outcome.
                    Database().delete_row('journal', [{"column": "id", "value": record['id']}])
                HA().set_insync(True)
        return


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
        domain=self.dict_controllers[host]['domain']
        serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
        #endpoint=f"{host}.{domain}"
        endpoint=self.dict_controllers[host]['ipaddress']
        token=self.get_token(host)
        if token:
            entry={'journal': [{'function': function, 'object': object, 'param': param, 'payload': payload, 'sendfor': host, 'sendby': self.me, 'created': created}] }
            headers = {'x-access-tokens': token}
            try:
                x = session.post(f'{self.protocol}://{endpoint}:{serverport}/journal', json=entry, headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                if str(x.status_code) in self.good_ret:
                    self.logger.info(f"journal for {function}({object})/payload sync to {host} success. Returned {x.status_code}")
                    return True
                else:
                    self.logger.error(f"journal for {function}({object})/payload sync to {host} failed. Returned {x.status_code}")
                    return False
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"No token to forward {function}({object})/payload sync to {host}. Invalid credentials or host is down.")
        return False


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
        domain=self.dict_controllers[host]['domain']
        serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
        #endpoint=f"{host}.{domain}"
        endpoint=self.dict_controllers[host]['ipaddress']
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/journal/{self.me}', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                if str(x.status_code) in self.good_ret:
                    self.logger.info(f"journal pull from {host} success. Returned {x.status_code}")
                    if x.text:
                        DATA = loads(x.text)
                        self.logger.debug(f"data received for pull: {DATA}")
                        if 'journal' in DATA:
                            NDATA=DATA['journal']
                            for entry in NDATA:
                                row = Helper().make_rows(entry)
                                request_id = Database().insert('journal', row)
                    return True
                else:
                    self.logger.error(f"journal pull from {host} failed. Returned {x.status_code}")
                    return False
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"No token to pull journal from host {host}. Invalid credentials or host is down.")
        return False


    def delete_journal(self,host):
        domain=self.dict_controllers[host]['domain']
        serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
        #endpoint=f"{host}.{domain}"
        endpoint=self.dict_controllers[host]['ipaddress']
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/journal/{self.me}/_delete', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                if str(x.status_code) in self.good_ret:
                    self.logger.info(f"journal delete from {host} success. Returned {x.status_code}")
                    return True
                else:
                    self.logger.error(f"journal delete from {host} failed. Returned {x.status_code}")
                    return False
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"No token to delete journal from host {host}. Invalid credentials or host is down.")
        return False


    def get_token(self,host):
        domain=self.dict_controllers[host]['domain']
        serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
        #endpoint=f"{host}.{domain}"
        endpoint=self.dict_controllers[host]['ipaddress']
        token_credentials = {'username': CONSTANT['API']['USERNAME'], 'password': CONSTANT['API']['PASSWORD']}
        token = None
        try:
            self.logger.debug(f"json for token: {token_credentials}")
            x = session.post(f'{self.protocol}://{endpoint}:{serverport}/token', json=token_credentials, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
            if (str(x.status_code) not in self.bad_ret) and x.text:
                DATA = loads(x.text)
                self.logger.debug(f"data received for token: {DATA}")
                if 'token' in DATA:
                    token=DATA["token"]
        except Exception as exp:
            self.logger.error(f"{exp}")
        return token


    def verify_tablehashes_controllers(self):
        if self.me:
            if self.all_controllers:
                my_hashes=Tables().get_table_hashes()
                for controller in self.all_controllers:
                    if controller['hostname'] in ["controller",self.me]:
                        continue
                    host=controller['hostname']
                    serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
                    endpoint=self.dict_controllers[host]['ipaddress']
                    token=self.get_token(host)
                    if token:
                        headers = {'x-access-tokens': token}
                        try:
                            x = session.get(f'{self.protocol}://{endpoint}:{serverport}/table/hashes', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                            if str(x.status_code) in self.good_ret:
                                if x.text:
                                    DATA = loads(x.text)
                                    self.logger.info(f"DATA: {DATA}")
                                    if 'message' in DATA and DATA['message'] == "not master":
                                        pass
                                    else:
                                        if 'table' in DATA and 'hashes' in DATA['table']:
                                            other_hashes=DATA['table']['hashes']
                                            for table in my_hashes.keys():
                                                if table in other_hashes.keys():
                                                    if my_hashes[table] != other_hashes[table]:
                                                        self.logger.info(f"table {table} hash mismatch. me: {my_hashes[table]}, {host}: {other_hashes[table]}")
                                                else:
                                                    self.logger.warning(f"no table hash for table {table} supplied by {host}")
                                        else:
                                            self.logger.warning(f"no table hashes supplied by {host}")
                                else:
                                    self.logger.warning(f"no data supplied by {host}")
                            else:
                                self.logger.error(f"table hashes fetch from {host} failed. Returned {x.status_code}")
                        except Exception as exp:
                            self.logger.error(f"{exp}")
                    else:
                        self.logger.error(f"No token to fetch table hashes from host {host}. Invalid credentials or host is down.")
        return True


