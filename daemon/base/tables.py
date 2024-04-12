#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#This code is part of the TrinityX software suite
#Copyright (C) 2023  ClusterVision Solutions b.v.
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>


"""
Journal class. handles internal journal calls
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from base64 import b64decode, b64encode
from utils.database import Database
from utils.helper import Helper
from utils.log import Log
from utils.ha import HA
from utils.tables import Tables as UTables


class Tables():
    """
    This class is responsible for RPC table mangling.
    """

    def __init__(self):
        self.logger = Log.get_logger()


    def get_table_hashes(self):
        status=False
        response='not master'
        master = HA().get_role()
        if master is True:
            status=True
            hashes = UTables().get_table_hashes()
            response = {'table': {'hashes': hashes} }
        return status, response
    
    
    def get_table_data(self,table=None):
        status=False
        response="Invalid request: table not supplied"
        if table:

            status=True
            response={}
            response[table]=UTables().export_table(table)

#            response={}
#            response[table]=[]
#            dbcolumns = Database().get_columns(table)
#            if dbcolumns:
#                status=True
#                sequence=Database().get_sequence(table)
#                if sequence:
#                    response[table].append({'SQLITE_SEQUENCE': sequence})
#                data=Database().get_record(dbcolumns,table)
#                if data:
#                    for record in data:
#                        response[table].append(record)
#                        #group_data = b64encode(data.encode())
#                        #group_data = group_data.decode("ascii")
#                response={'table': {'data': response}}
#            else:
#                response=f"Table {table} not in database"
        return status, response

