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
#import sys
import hashlib
#from base64 import b64decode, b64encode
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.request import Request
from utils.ha import HA


class Tables():
    """
    This class offer table specific functions, like hasing, verification etc
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.tables = ['osimage', 'osimagetag', 'nodesecrets', 'nodeinterface', 'bmcsetup', 
              'ipaddress', 'groupinterface', 'roles', 'group', 'network', 'user', 'switch', 
              'otherdevices', 'groupsecrets', 'node', 'cluster', 'dns','controller']

    def get_tables(self):
        return self.tables

    def get_table_hashes(self):
        hashes={}
        for table in self.tables:
            order='name'
            dbcolumns = Database().get_columns(table)
            self.logger.debug(f"TABLE: {table}, DBCOLUMNS: {dbcolumns}")
            hashes[table]="0"
            if dbcolumns:
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
                    elif 'hostname' in dbcolumns:
                        order='hostname'
                order=f"ORDER BY {order} ASC"
                data=Database().get_record(dbcolumns,table,order)
                if data:
                    merged="#"
                    for record in data:
                        merged+=dumps(data)+";"
                    hashes[table]=str(hashlib.sha256(merged.encode()).hexdigest())
        self.logger.debug(f"HASHES: {hashes}")
        return hashes


    def verify_tablehashes_controllers(self,me=None):
        mismatch_tables=[]
        if not me:
            me=HA().get_me()
        if me:
            all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6',
                                                          'network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
            if all_controllers:
                my_hashes=Tables().get_table_hashes()
                for controller in all_controllers:
                    if controller['hostname'] == me:
                        continue
                    elif controller['beacon']:
                        continue
                    host=controller['hostname']
                    status,data=Request().get_request(host,f'/table/hashes')
                    if status is True and data:
                        if 'message' in data and data['message'] == "not master":
                            pass
                        elif 'table' in data and 'hashes' in data['table']:
                            other_hashes=data['table']['hashes']
                            for table in my_hashes.keys():
                                if table in other_hashes.keys():
                                    if my_hashes[table] != other_hashes[table]:
                                        self.logger.warning(f"table {table} hash mismatch. me: {my_hashes[table]}, {host}: {other_hashes[table]}")
                                        mismatch_tables.append({'table': table, 'host': host})
                                else:
                                    self.logger.warning(f"no table hash for table {table} supplied by {host}")
                        else:
                            self.logger.warning(f"no valid data supplied by {host}")
                    else:
                        self.logger.error(f"table hashes fetch from {host} failed")
        return mismatch_tables


    def fetch_table(self,table,host):
        response=None
        status, data=Request().get_request(host,f'/table/data/{table}')
        if status is True and data:
            if 'table' in data and 'data' in data['table'] and table in data['table']['data']:
                response=data['table']['data'][table]
            else:
                self.logger.warning(f"no valid table data supplied by {host}")
        else:
            self.logger.error(f"table data fetch from {host} failed")
        return status, response


    def import_table(self,table,data=[],emptyok=False):
        seq=None
        if not data:
            if data is None:
                self.logger.error(f"data for table {table} is 'None' which i cannot permit. bailing out.")
                return False
            if not emptyok:
                self.logger.error(f"data for table {table} is empty but clashes with emptyok {emptyok}")
                return False
        Database().clear(table)
        if not data:
            self.logger.warning(f"No data for table {table} found so we only cleared the table")
            return True
        for record in data:
            if 'SQLITE_SEQUENCE' in record:
                seq=record['SQLITE_SEQUENCE']
                continue
            row = Helper().make_rows(record)
            result=Database().insert(table,row)
            if not result:
                self.logger.error(f"Error importing data for table {table}")
                return False
        self.logger.info(f"Success importing data for table {table}")
        Database().update_sequence(table,seq)
        return True


    def import_table_from_host(self,table,host):
        status, data=self.fetch_table(table,host)
        if not status:
            return False
        self.import_table(table=table,data=data,emptyok=True)
        return True


    def export_table(self,table,sequence=True):
        data=[]
        dbcolumns = Database().get_columns(table)
        if dbcolumns:
            status=True
            if sequence:
                dbsequence=Database().get_sequence(table)
                if dbsequence:
                    data.append({'SQLITE_SEQUENCE': dbsequence})
            dbdata=Database().get_record(dbcolumns,table)
            if dbdata:
                for record in dbdata:
                    data.append(record)
                    #group_data = b64encode(data.encode())
                    #group_data = group_data.decode("ascii")
        return data

