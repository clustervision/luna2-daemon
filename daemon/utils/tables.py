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
import netifaces as ni
from base64 import b64decode, b64encode
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.token import Token

import requests
from requests import Session
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util import Retry

urllib3.disable_warnings()
session = Session()
retries = Retry(
    total = 10,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500, 404],
    allowed_methods = {'GET', 'POST'}
)
session.mount('https://', HTTPAdapter(max_retries=retries))

class Tables():
    """
    This class offer table specific functions, like hasing, verification etc
    """

    def __init__(self,me=None):
        self.logger = Log.get_logger()
        self.tables = ['osimage', 'osimagetag', 'nodesecrets', 'nodeinterface', 'bmcsetup', 
              'ipaddress', 'groupinterface', 'roles', 'group', 'network', 'user', 'switch', 
              'otherdevices', 'groupsecrets', 'node', 'cluster', 'dns']
        self.protocol = CONSTANT['API']['PROTOCOL']
        _,self.alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.dict_controllers=None
        self.me=me
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
                            self.logger.info(f"My ipaddress is {ip} and i am {self.me}")


    def get_table_hashes(self):
        hashes={}
        for table in self.tables:
            order='name'
            dbcolumns = Database().get_columns(table)
            self.logger.debug(f"TABLE: {table}, DBCOLUMNS: {dbcolumns}")
            if dbcolumns:
                if 'id' in dbcolumns:
                    dbcolumns.remove('id')
                if 'name' not in dbcolumns:
                    if 'tablerefid' in dbcolumns:
                        order='tablerefid'
                        if 'tableref' in dbcolumns:
                            order+=',tableref'
                    elif 'host' in dbcolumns:
                        order='host'
                        if 'networkid' in dbcolumns:
                            order+=',networkid'
                    elif 'nodeid' in dbcolumns:
                        order='nodeid'
                        if 'interface' in dbcolumns:
                            order+=',interface'
                    elif 'groupid' in dbcolumns:
                        order='groupid'
                        if 'interface' in dbcolumns:
                            order+=',interface'
                    elif 'username' in dbcolumns:
                        order='username'
                order=f"ORDER BY {order} ASC"
                data=Database().get_record(dbcolumns,table,order)
                if data:
                    merged="#"
                    for record in data:
                        merged+=dumps(data)+";"
                    hashes[table]=str(hashlib.sha256(merged.encode()).hexdigest())
        self.logger.debug(f"HASHES: {hashes}")
        return hashes


    def verify_tablehashes_controllers(self):
        mismatch_tables=[]
        if self.me:
            if self.all_controllers:
                my_hashes=Tables().get_table_hashes()
                for controller in self.all_controllers:
                    if controller['hostname'] in ["controller",self.me]:
                        continue
                    host=controller['hostname']
                    serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
                    endpoint=self.dict_controllers[host]['ipaddress']
                    token=Token().get_token(host)
                    if token:
                        headers = {'x-access-tokens': token}
                        try:
                            x = session.get(f'{self.protocol}://{endpoint}:{serverport}/table/hashes', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                            if str(x.status_code) in self.good_ret:
                                if x.text:
                                    DATA = loads(x.text)
                                    if 'message' in DATA and DATA['message'] == "not master":
                                        pass
                                    else:
                                        if 'table' in DATA and 'hashes' in DATA['table']:
                                            other_hashes=DATA['table']['hashes']
                                            for table in my_hashes.keys():
                                                if table in other_hashes.keys():
                                                    if my_hashes[table] != other_hashes[table]:
                                                        self.logger.warning(f"table {table} hash mismatch. me: {my_hashes[table]}, {host}: {other_hashes[table]}")
                                                        mismatch_tables.append({'table': table, 'host': host})
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
        return mismatch_tables


    def fetch_table(self,table,host):
        response=None
        if self.all_controllers:
            serverport=self.dict_controllers[host]['serverport'] or self.alt_serverport
            endpoint=self.dict_controllers[host]['ipaddress']
            token=Token().get_token(host)
            if token:
                headers = {'x-access-tokens': token}
                try:
                    x = session.get(f'{self.protocol}://{endpoint}:{serverport}/table/data/{table}', headers=headers, stream=True, timeout=10, verify=CONSTANT['API']["VERIFY_CERTIFICATE"])
                    if str(x.status_code) in self.good_ret:
                        if x.text:
                            DATA = loads(x.text)
                            if 'table' in DATA and 'data' in DATA['table'] and table in DATA['table']['data']:
                                response=DATA['table']['data'][table]
                                self.logger.info(f"DATA: {response}")
                        else:
                            self.logger.warning(f"no data supplied by {host}")
                    else:
                        self.logger.error(f"table hashes fetch from {host} failed. Returned {x.status_code}")
                except Exception as exp:
                    self.logger.error(f"{exp}")
            else:
                self.logger.error(f"No token to fetch table hashes from host {host}. Invalid credentials or host is down.")
        return True


    def import_table(self,table,data):
        if table == 'ipaddress':
            return True
        if table and data:
            for record in data:
                where=None
                if 'name' in record:
                    where = [{"column": "name", "value": {record['name']}}]
                else:
                    if 'tablerefid' in record:
                        where = [{"column": "tablerefid", "value": {record['tablerefid']}}]
                        if 'tableref' in record:
                            where.append({"column": "tableref", "value": {record['tableref']}}
                    elif 'host' in record:
                        where = [{"column": "host", "value": {record['host']}}]
                        if 'networkid' in record:
                            where.append({"column": "networkid", "value": {record['networkid']}}
                    elif 'nodeid' in record:
                        where = [{"column": "", "value": {record['']}}]
                        primary='nodeid'
                        if 'interface' in record:
                            where.append({"column": "interface", "value": {record['interface']}}
                    elif 'groupid' in record:
                        where = [{"column": "", "value": {record['']}}]
                        if 'interface' in record:
                            where.append({"column": "interface", "value": {record['interface']}}
                    elif 'username' in record:
                        where = [{"column": "username", "value": {record['name']}}]
                row = Helper().make_rows(record)
                self.logger.info(f"---------------------------------------------------")
                self.logger.info(f"ROW: {row}")
                self.logger.info(f"WHERE: {where}")
#                try:
#                    result=Database().update(table,row,where)
#                except:
#                    try:
#                        result=Database().insert(table,row)
#                    except Exception as exp:
#                        self.logger.error(f"{exp}")
#                        return False
        return True


