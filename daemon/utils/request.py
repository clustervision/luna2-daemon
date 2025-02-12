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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

import re
import requests
from requests import Session
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util import Retry

urllib3.disable_warnings()
session = Session()
retries = Retry(
    total = 3,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500, 404],
    allowed_methods = {'GET', 'POST'}
)
session.mount('https://', HTTPAdapter(max_retries=retries))

class Request():
    """
    This class offers remote token functionality. get remote token etc.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.protocol = CONSTANT['API']['PROTOCOL']
        self.verify = Helper().make_bool(CONSTANT['API']["VERIFY_CERTIFICATE"])
        _,self.alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
                                                          ['ipaddress.tablerefid=controller.id'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')


    def get_token(self,host):
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token_credentials = {'username': CONSTANT['API']['USERNAME'], 'password': CONSTANT['API']['PASSWORD']}
        token = None
        try:
            self.logger.debug(f"json for token: {token_credentials}")
            x = session.post(f'{self.protocol}://{endpoint}:{serverport}/token', json=token_credentials, stream=True, timeout=10, verify=self.verify)
            if (str(x.status_code) not in self.bad_ret) and x.text:
                data = loads(x.text)
                self.logger.debug(f"data received for token: {data}")
                if 'token' in data:
                    token=data["token"]
        except Exception as exp:
            self.logger.error(f"{exp}")
        return token

    def get_request(self,host,uri):
        uri = re.sub('^/', '', uri)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/{uri}', headers=headers, stream=True, timeout=10, verify=self.verify)
                if str(x.status_code) in self.good_ret:
                    self.logger.debug(f"get request {uri} on {host} success. returned {x.status_code}")
                    data=None
                    if x.text:
                        data = loads(x.text)
                        self.logger.debug(f"data received for {uri}: {data}")
                    return True, data
                else:
                    self.logger.error(f"get request {uri} on {host} failed. returned {x.status_code}")
                    return False, None
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
        return False, None

    def post_request(self,host,uri,json):
        uri = re.sub('^/', '', uri)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.post(f'{self.protocol}://{endpoint}:{serverport}/{uri}', headers=headers, json=json, stream=True, timeout=10, verify=self.verify)
                if str(x.status_code) in self.good_ret:
                    self.logger.debug(f"post request {uri} on {host} success. returned {x.status_code}")
                    data=None
                    if x.text:
                        data = loads(x.text)
                        self.logger.debug(f"data received for {uri}: {data}")
                    return True, data
                else:
                    self.logger.error(f"post request {uri} on {host} failed. returned {x.status_code}")
                    return False, None
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
        return False, None


    def download_file(self,host,filename,location):
        filename = re.sub('^/', '', filename)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                url = f'{self.protocol}://{endpoint}:{serverport}/files/{filename}'
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/files/{filename}', headers=headers, stream=True, timeout=10, verify=self.verify)
                if str(x.status_code) in self.good_ret:
                    self.logger.debug(f"get request download {filename} on {host} success. returned {x.status_code}")
                    file = open(location+'/'+filename, 'wb')
                    file.write(x.content)
                    file.close()
                    return True, 'success'
                else:
                    self.logger.error(f"get request download {filename} on {host} failed. returned {x.status_code}")
                    return False, None
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
        return False, None


    def get_host_ip(self,host):
        endpoint=host
        if host in self.dict_controllers.keys():
            endpoint=self.dict_controllers[host]['ipaddress_ipv6'] or self.dict_controllers[host]['ipaddress']
        return endpoint

    def get_host_port(self,host):
        port=self.alt_serverport
        if host in self.dict_controllers.keys():
            port=self.dict_controllers[host]['serverport'] or self.alt_serverport
        return port

