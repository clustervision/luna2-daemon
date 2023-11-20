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
from base64 import b64decode, b64encode
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

class Tables():
    """
    This class offer table specific functions, like hasing etc
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.tables = ['osimage', 'osimagetag', 'nodesecrets', 'nodeinterface', 'bmcsetup', 
              'ipaddress', 'groupinterface', 'roles', 'group', 'network', 'user', 'switch', 
              'otherdevices', 'groupsecrets', 'node', 'cluster', 'dns']


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

