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

# id, request, payload, sendfor sendby tries created

class Journal():
    """
    This class is responsible for all journal and replication operations
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.me=None
        self.all_controllers = Database().get_record_join(['ipaddress.ipaddress','controller.hostname'],
                                                          ['ipaddress.tablerefid=controller.id'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            me=None
            for interface in ni.interfaces():
                ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
                self.logger.debug(f"Interface {interface} has ip {ip}")
                for controller in self.all_controllers:
                    if controller['hostname'] == "controller":
                        continue
                    if controller['ipaddress'] == ip:
                        self.me=controller['hostname']
                        self.logger.info(f"My ipaddress is {ip} and i am {self.me}")


    def add_request(self,request,payload=None):
        if payload:
            string = dumps(payload)
            encoded = b64encode(string.encode())
            payload = encoded.decode("ascii")
        if self.me:
            if self.all_controllers:
                data={}
                data['request'] = request
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
                    self.logger.info(f"replicating {request} to {controller['hostname']} with id {request_id}")
            else:
                self.logger.error(f"No controllers are configured")
        else:
            self.logger.error(f"I do not know who i am. cannot replicate")
        return


    def handle_requests(self):
        if self.me:
            all_records = Database().get_record(None,'journal',f"WHERE sendfor='{self.me}' AND tries<'5' ORDER BY created ASC")
            if all_records:
                for record in all_records:
                    decoded = b64decode(record['payload'])
                    string = decoded.decode("ascii")
                    record['payload'] = loads(string)
                    self.logger.info(f"executing {record['request']}/{record['tries']} received by {record['sendby']} on {record['created']}")
        return


