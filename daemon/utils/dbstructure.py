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
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from json import dumps,loads
from utils.log import Log
from utils.database import Database
from common.database_layout import *
from utils.helper import Helper

class DBStructure():
    """
    This class offers functions aiding in checking, creating and fixing the database structure
    Typically called by common/bootstrap
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.tables = ['status', 'queue', 'osimage', 'osimagetag', 'nodesecrets',
                       'nodeinterface', 'bmcsetup','ha', 'monitor', 'ipaddress',
                       'groupinterface', 'roles', 'group', 'network', 'user', 'switch',
                       'cloud', 'otherdevices', 'controller', 'groupsecrets', 'node',
                       'cluster', 'tracker', 'dns', 'journal', 'rack', 'rackinventory',
                       'ping', 'reservedipaddress']
   
 
    def check_db_tables(self):
        """
        This method will check whether the database is empty or not.
        """
        num = 0
        for table in self.tables:
            dbcolumns = Database().get_columns(table)
            if dbcolumns:
                num = num+1
                layout = self.get_database_table_structure(table=table)
                self.check_and_fix_table_layout(table=table,layout=layout,dbcolumns=dbcolumns)
        if num == 0:
            # if we reach here this means nothing was there.
            return False
        return True
   
    def check_and_fix_table_layout(self,table,layout=None,dbcolumns=None):
        """
        This method will check and fix the table structure.
        """
        if not layout:
            layout = self.get_database_table_structure(table=table)
        if not dbcolumns:
            dbcolumns = Database().get_columns(table)
        if layout:
            if dbcolumns:
                pending=[]
                for column in layout:
                    if column['column'] not in dbcolumns:
                        if 'key' in column:
                            pending.append(column)
                        else:
                            self.logger.error(f"fix database: column {column['column']} not found in table {table} and will be added")
                            Database().add_column(table, column)
                for column in pending:
                    self.logger.error(f"fix database: column {column['column']} not found in table {table} and will be added")
                    Database().add_column(table, column)
            else:
                self.logger.error(f'Database table {table} does not seem to exist and will be created')
                layout = self.get_database_table_structure(table=table)
                Database().create(table, layout)
        return True
   
    def create_database_tables(self,table=None):
        """
        This method will create DB table
        """
        for table in self.tables:
            layout = get_database_table_structure(table=table)
            Database().create(table, layout)
    
    def get_appended_database_table_structure(self,table=None):
        layout = self.get_database_table_structure(table)
        dbcolumns = Database().get_columns(table)
        if dbcolumns:
            if not layout:
                self.logger.warning(f"database structure not found in defined table layout. all columns will be added with defaults")
                for column in dbcolumns:
                    layout.append({"column": column['column'], "datatype": "VARCHAR", "length": "100"})
            else:
                for column in layout:
                    if column['column'] in dbcolumns:
                        dbcolumns.remove(column['column'])
                for column in dbcolumns:
                    self.logger.warning(f"database structure: column {column} not found in defined table layout and is added with defaults")
                    layout.append({"column": column, "datatype": "VARCHAR", "length": "100"})
        return layout
    
    def get_database_table_structure(self,table=None):
        if not table:
            return
        if table == "status":
            return DATABASE_LAYOUT_status
        if table == "queue":
            return DATABASE_LAYOUT_queue
        if table == "osimage":
            return DATABASE_LAYOUT_osimage
        if table == "osimagetag":
            return DATABASE_LAYOUT_osimagetag
        if table == "nodesecrets":
            return DATABASE_LAYOUT_nodesecrets
        if table == "nodeinterface":
            return DATABASE_LAYOUT_nodeinterface
        if table == "bmcsetup":
            return DATABASE_LAYOUT_bmcsetup
        if table == "monitor":
            return DATABASE_LAYOUT_monitor
        if table == "ipaddress":
            return DATABASE_LAYOUT_ipaddress
        if table == "groupinterface":
            return DATABASE_LAYOUT_groupinterface
        if table == "roles":
            return DATABASE_LAYOUT_roles
        if table == "group":
            return DATABASE_LAYOUT_group
        if table == "network":
            return DATABASE_LAYOUT_network
        if table == "user":
            return DATABASE_LAYOUT_user
        if table == "switch":
            return DATABASE_LAYOUT_switch
        if table == "cloud":
            return DATABASE_LAYOUT_cloud
        if table == "otherdevices":
            return DATABASE_LAYOUT_otherdevices
        if table == "controller":
            return DATABASE_LAYOUT_controller
        if table == "groupsecrets":
            return DATABASE_LAYOUT_groupsecrets
        if table == "node":
            return DATABASE_LAYOUT_node
        if table == "cluster":
            return DATABASE_LAYOUT_cluster
        if table == "tracker":
            return DATABASE_LAYOUT_tracker
        if table == "dns":
            return DATABASE_LAYOUT_dns
        if table == "journal":
            return DATABASE_LAYOUT_journal
        if table == "ha":
            return DATABASE_LAYOUT_ha
        if table == "ping":
            return DATABASE_LAYOUT_ping
        if table == "rack":
            return DATABASE_LAYOUT_rack
        if table == "rackinventory":
            return DATABASE_LAYOUT_rackinventory
        if table == "reservedipaddress":
            return DATABASE_LAYOUT_reservedipaddress
        return None 

