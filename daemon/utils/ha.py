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
from time import sleep, time
from random import randint
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

class HA():
    """
    This class is responsible for all H/A related business
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.insync=False
        self.hastate=None
        self.master=False
        self.protocol = CONSTANT['API']['PROTOCOL']
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')

    def set_insync(self,state):
        ha_state={}
        ha_state['insync']=0
        if state is True:
            ha_state['insync']=1
        self.logger.info(f"set_insync ha_state: {ha_state}")
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            where = [{"column": "insync", "value": ha_data[0]['insync']}]
            row = Helper().make_rows(ha_state)
            Database().update('ha', row, where)
        return self.get_insync()

    def get_insync(self):
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            self.logger.debug(f"get_insync new ha_state: {ha_data}")
            self.insync=Helper().make_bool(ha_data[0]['insync'])
            self.logger.debug(f"get_insync new_self.insync: {self.insync}")
        else:
            return False
        return self.insync

    def get_hastate(self):
        if self.hastate is None:
            ha_data = Database().get_record(None, 'ha')
            if ha_data:
                self.logger.info(f"get_hastate new ha_state: {ha_data}")
                self.hastate=Helper().make_bool(ha_data[0]['enabled'])
                self.logger.debug(f"get_hastate new_self.hastate: {self.hastate}")
        return self.hastate

    def set_hastate(self,state):
        ha_state={}
        ha_state['enabled']=0
        if state is True:
            ha_state['enabled']=1
        self.logger.info(f"set_hastate ha_state: {ha_state}")
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            where = [{"column": "enabled", "value": ha_data[0]['enabled']}]
            row = Helper().make_rows(ha_state)
            Database().update('ha', row, where)
        return self.get_hastate()

    def get_role(self):
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            self.master=Helper().make_bool(ha_data[0]['master'])
        return self.master


    def ping(self):
        status=True
        if self.all_controllers:
            for controller in self.all_controllers:
                status=self.ping_host(controller)
                if status is False:
                    return False
        return status


    def ping_host(self,host):
        domain=self.dict_controllers[host]['domain']
        _,alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        serverport=self.dict_controllers[host]['serverport'] or alt_serverport
        #endpoint=f"{host}.{domain}"
        endpoint=self.dict_controllers[host]['ipaddress']
        #token=self.get_token(host)
        #if token:
        if True:
            #headers = {'x-access-tokens': token}
            try:
                #x = session.get(f'{self.protocol}://{endpoint}:{serverport}/ping', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/ping', stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                if str(x.status_code) in self.good_ret:
                    self.logger.info(f"ping from {host} success. Returned {x.status_code}")
                    return True
                else:
                    self.logger.info(f"ping from {host} failed. Returned {x.status_code}")
                    return False
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"No token to ping host {host}. Invalid credentials or host is down.")
        return False


    def get_token(self,host):
        domain=self.dict_controllers[host]['domain']
        _,alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        serverport=self.dict_controllers[host]['serverport'] or alt_serverport
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


