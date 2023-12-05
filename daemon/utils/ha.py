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
from time import sleep, time
from random import randint
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.request import Request

import requests
from requests import Session
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util import Retry

urllib3.disable_warnings()
session = Session()
retries = Retry(
    total = 1,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500, 404],
    allowed_methods = {'GET', 'POST'}
)
session.mount('https://', HTTPAdapter(max_retries=retries))

class HA():
    """
    This class is responsible for all H/A related business
    """

    def __init__(self,me=None):
        self.logger = Log.get_logger()
        self.insync=False
        self.hastate=None
        self.syncimages=True
        self.master=False
        self.protocol = CONSTANT['API']['PROTOCOL']
        self.verify = Helper().make_bool(CONSTANT['API']["VERIFY_CERTIFICATE"])
        _,self.alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.dict_controllers=None
        self.me=me
        self.ip=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')
            if not self.me:
                for interface in ni.interfaces():
                    ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
                    self.logger.debug(f"Interface {interface} has ip {ip}")
                    for controller in self.all_controllers:
                        if controller['hostname'] == "controller":
                            continue
                        if not self.me and controller['ipaddress'] == ip:
                            self.me=controller['hostname']
                            self.ip=ip
                            self.logger.debug(f"My ipaddress is {ip} and i am {self.me}")


    def get_me(self):
        return self.me

    def get_my_ip(self):
        return self.ip

    def set_insync(self,state):
        oldstate=self.get_insync()
        if state != oldstate:
            self.logger.info(f"set_insync state to {state}")
        return self.set_property('insync',state)

    def get_insync(self):
        self.insync=self.get_property('insync')
        return self.insync

    def get_hastate(self):
        self.hastate=self.get_property('enabled')
        return self.hastate

    def set_hastate(self,state):
        return self.set_property('enabled',state)

    def get_role(self):
        self.master=self.get_property('master')
        return self.master

    def set_role(self,state):
        self.logger.info(f"set_role (master) to {state}")
        return self.set_property('master',state)

    def get_syncimages(self):
        self.syncimages=self.get_property('syncimages')
        return self.syncimages

    def set_syncimages(self,state):
        return self.set_property('syncimage',state)

    def get_overrule(self):
        self.overrule=self.get_property('overrule')
        return self.overrule

    def set_overrule(self,state):
        return self.set_property('overrule',state)

    # --------------------------------------------------------------------------

    def set_property(self,name,value):
        property={}
        property[name]=0
        if value is True:
            property[name]=1
        self.logger.debug(f"set_{name} set to {property}")
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            where = [{"column": name, "value": ha_data[0][name]}]
            row = Helper().make_rows(property)
            result=Database().update('ha', row, where)
            if result:
                return True
        return False

    def get_property(self,name):
        value=False
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            value=ha_data[0][name] or False
        value=Helper().make_bool(value)
        self.logger.debug(f"{name} state: {value}")
        return value

    # --------------------------------------------------------------------------

    def get_full_state(self):
        data = {}
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            data = ha_data[0]
            for item in ['master','syncimages','enabled','insync']:
                data[item] = Helper().make_bool(data[item])
        return data

    def ping_all_controllers(self):
        status=True
        if self.all_controllers:
            for controller in self.all_controllers:
                status=self.ping_host(controller['hostname'])
                if status is False:
                    return False
        return status

    def ping_host(self,host):
        domain=self.dict_controllers[host]['domain']
        serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
        endpoint=self.dict_controllers[host]['ipaddress']
        try:
            x = session.get(f'{self.protocol}://{endpoint}:{serverport}/ping', stream=True, timeout=10, verify=self.verify)
            if str(x.status_code) in self.good_ret:
                self.logger.debug(f"ping from {host} success. Returned {x.status_code}")
                return True
            else:
                self.logger.error(f"ping from {host} failed. Returned {x.status_code}")
                return False
        except Exception as exp:
            self.logger.error(f"{exp}")
        return False

