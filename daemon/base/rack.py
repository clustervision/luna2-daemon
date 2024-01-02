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
Rack Class will handle all rack operations.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'support@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.model import Model

class Rack():
    """
    This class is responsible for all operations for rack.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'rack'
        self.table_cap = self.table.capitalize()


    def get_rack(self,name=None):
        """
        This method will return all the racks in detailed format.
        """
        status=False
        response={'config': {'rack': {} }}
        for device_type in ['node','switch','otherdevices','controller']:
            where=[f"rackinventory.tableref='{device_type}'"]
            if name:
                where.append(f"rack.name='{name}'")
            rack_data = Database().get_record_join(
                   ['rack.*','rack.id as rackid','rackinventory.*',
                    'rackinventory.id as invid',f'{device_type}.name as devicename'],
                   [f'rackinventory.tablerefid={device_type}.id','rackinventory.rackid=rack.id'],
                   where)
            if rack_data:
                status=True
                for device in rack_data:
                    if device['name'] not in response['config']['rack'].keys():
                        response['config']['rack'][device['name']]={'size': device['size'] or '42', 
                                                                    'order': device['order'] or 'ascending', 
                                                                    'room': device['room'], 'site': device['site'], 
                                                                    'name': device['name'], 'devices': []}
                    response['config']['rack'][device['name']]['devices'].append({
                                                          'name': device['devicename'],
                                                          'type': device_type,
                                                          'orientation': device['orientation'],
                                                          'height': device['height'],
                                                          'position': device['position']})
        self.logger.debug(f"RACK: {response}")               
        return status, response


    def update_rack(self, name=None, request_data=None):
        """
        This method will create or update a rack.
        """
        status=False
        response="Internal error"
        network = False
        data, response = {}, {}
        create, update = False, False

        # things we have to set for a rack
        items = {
            'orientation': 'front',
            'order': 'ascending'
        }
        if request_data:
            data = request_data['config'][self.table][name]
            data['name'] = name
            where = f' WHERE `name` = "{name}"'
            check_rack = Database().get_record(table=self.table, where=where)
            if check_rack:
                rackid = check_rack[0]['id']
                if 'newrackname' in request_data['config'][self.table][name]:
                    data['name'] = data['newrackname']
                    del data['newrackname']
                update = True
            else:
                create = True

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

            return status, response
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_rack(self, name=None):
        """
        This method will delete a rack.
        """
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return status, response

