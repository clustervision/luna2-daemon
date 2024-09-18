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
BMC Setup Class will handle all bmc setup operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import uuid
from utils.log import Log
from utils.model import Model
from utils.database import Database


class BMCSetup():
    """
    This class is responsible for all operations for bmc setup.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'bmcsetup'
        self.table_cap = 'BMC Setup'


    def get_all_bmcsetup(self):
        """
        This method will return all the bmcsetup in detailed format.
        """
        status, response = Model().get_record(
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def get_bmcsetup(self, name=None):
        """
        This method will return requested bmcsetup in detailed format.
        """
        status, response = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def get_bmcsetup_member(self, name=None):
        """
        This method will return all the list of all the member node names for a bmcsetup.
        """
        status, response = Model().get_member(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response

    def update_bmcsetup(self, name=None, request_data=None):
        """
        This method will create or update a bmcsetup.
        """
        new_name = 'newbmcname'
        # things we have to set for a bmcsetup
        items = {
            'userid': '2',
            'netchannel': '2',
            'mgmtchannel': '2',
            'username': 'luna'
        }
        items['password']=str(uuid.uuid4().hex.upper()[0:6])+str(uuid.uuid4().hex[0:6])+'#!'
        create, update = False, False
        status, _ = self.get_bmcsetup(name)
        if status:
            update=True
        else:
            create=True
        if request_data:
            if 'config' in request_data and self.table in request_data['config'] and name in request_data['config'][self.table]:
                data=request_data['config'][self.table][name]
                for key, value in items.items():
                    if key in data:
                        data[key] = data[key]
                        if isinstance(value, bool):
                            data[key] = str(Helper().bool_to_string(data[key]))
                    elif create:
                        data[key] = value
                        if isinstance(value, bool):
                            data[key] = str(Helper().bool_to_string(data[key]))
                    if key in data and (not data[key]) and (key not in items):
                        del data[key]
                for key in data:
                    request_data['config'][self.table][name][key] = data[key]
        status, response = Model().change_record(
            name = name,
            new_name = new_name,
            table = self.table,
            table_cap = self.table_cap,
            request_data = request_data
        )
        return status, response


    def clone_bmcsetup(self, name=None, request_data=None):
        """
        This method will clone a bmcsetup.
        """
        new_name = 'newbmcname'
        status, response = Model().clone_record(
            name = name,
            new_name = new_name,
            table = self.table,
            table_cap = self.table_cap,
            request_data = request_data
        )
        return status, response


    def delete_bmcsetup(self, name=None):
        """
        This method will delete a bmcsetup.
        """
        inuse_node = Database().get_record_join(['node.*'], ['bmcsetup.id=node.bmcsetupid'],
                                                f'bmcsetup.name="{name}"')
        inuse_group = Database().get_record_join(['group.*'], ['bmcsetup.id=group.bmcsetupid'],
                                                f'bmcsetup.name="{name}"')
        inuse = []
        if inuse_node:
            inuse += inuse_node                                   
        if inuse_group:
            inuse += inuse_group                                   
        if inuse:
            inuseby=[]
            while len(inuse) > 0 and len(inuseby) < 11:
                node=inuse.pop(0)
                inuseby.append(node['name'])
            response = f"bmcsetup {name} currently in use by "+', '.join(inuseby)+" ..."
            return False, response

        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response
