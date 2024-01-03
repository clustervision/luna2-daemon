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
            empty_rack=False
            dbname='name'
            if device_type == 'controller':
                dbname='hostname'
            where=[f"rackinventory.tableref='{device_type}'"]
            if name:
                where.append(f"rack.name='{name}'")
            rack_data = Database().get_record_join(
                   ['rack.*','rack.id as rackid','rackinventory.*',
                    'rackinventory.id as invid',f'{device_type}.{dbname} as devicename'],
                   [f'rackinventory.tablerefid={device_type}.id','rackinventory.rackid=rack.id'],
                   where)
            if not rack_data:
                empty_rack=True
                rack_data = Database().get_record(None,'rack')
            if rack_data:
                status=True
                for device in rack_data:
                    if device['name'] not in response['config']['rack'].keys():
                        response['config']['rack'][device['name']]={'size': device['size'] or '42', 
                                                                    'order': device['order'] or 'ascending', 
                                                                    'room': device['room'], 'site': device['site'], 
                                                                    'name': device['name'], 'devices': []}
                    if not empty_rack:
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
            'size': '42',
            'order': 'ascending'
        }
        # things we have to set for devices
        inventory_items = {
            'orientation': 'front',
            'height': '1',
        }
        if request_data:
            devices_dict = {}
            all_devices_dict = {}
            for device_type in ['node','switch','otherdevices','controller']:
                dbname='name'
                if device_type == 'controller':
                    dbname='hostname'
                devices_in_db = Database().get_record_join([f'{device_type}.{dbname}', f'{device_type}.id as devid', 'rackinventory.id as invid'],
                                                       [f'rackinventory.tablerefid={device_type}.id'], 
                                                       [f"rackinventory.tableref='{device_type}'"])
                if devices_in_db:
                    devices_dict[device_type] = Helper().convert_list_to_dict(devices_in_db, dbname)
                all_devices_in_db = Database().get_record(None, device_type)
                if all_devices_in_db:
                    all_devices_dict[device_type] = Helper().convert_list_to_dict(all_devices_in_db, dbname)

            data = request_data['config']['rack'][name]
            data['name'] = name
            devices = None
            if 'devices' in data:
                devices = data['devices']
                del data['devices']
            rackid = None
            check_rack = Database().get_record(table='rack', where=f' WHERE `name` = "{name}"')
            if check_rack:
                rackid = check_rack[0]['id']
                if 'newrackname' in request_data['config']['rack'][name]:
                    data['name'] = data['newrackname']
                    del data['newrackname']
                update = True
            else:
                create = True

            for key, value in items.items():
                if key in data:
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                elif create:
                    data[key] = value
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                if key in data and (not data[key]) and (key not in items):
                    del data[key]

            if update:
                where = [{"column": "id", "value": rackid}]
                row = Helper().make_rows(data)
                Database().update('rack', row, where)
            elif create:
                row = Helper().make_rows(data)
                rackid = Database().insert('rack', row)

            if not rackid:
                return False, f"Could not update or create rack {name}"
                
            if devices:
                self.logger.debug(f"    DEV: {devices_dict}")
                self.logger.debug(f" ALLDEV: {all_devices_dict}")
                self.logger.debug(f"DEVICES: {devices}")
                for device in devices:
                    if 'name' not in device:
                        return False, "device name not supplied in data structure"
                    inventory_id = None
                    create, update = False, False
                    for device_type in ['node','switch','otherdevices','controller']:
                        if device_type in devices_dict.keys() and device['name'] in devices_dict[device_type].keys():
                            update = True
                            inventory_id = devices_dict[device_type][device['name']]['invid']
                            break
                    if not update:
                        create = True

                    device_data = { 'rackid': rackid }
                    if 'type' in device:
                        device_data['tableref'] = device['type']
                    elif create:
                        return False, f"Type for {device['name']} not found in data structure"

                    for item in ['height','position','orientation']:
                        if item in device:
                            device_data[item] = device[item]
                            
                    for key, value in inventory_items.items():
                        if key in device_data:
                            if isinstance(value, bool):
                                device_data[key] = str(Helper().bool_to_string(device_data[key]))
                        elif create:
                            device_data[key] = value
                            if isinstance(value, bool):
                                device_data[key] = str(Helper().bool_to_string(device_data[key]))
                        if key in device_data and (not device_data[key]) and (key not in inventory_items):
                            del device_data[key]
                    
                    if update and inventory_id:
                        self.logger.debug(f"UPDATE: {device_data}")
                        where = [{"column": "id", "value": inventory_id}]
                        row = Helper().make_rows(device_data)
                        Database().update('rackinventory', row, where)
                    elif create:
                        if device['type'] in all_devices_dict.keys() and device['name'] in all_devices_dict[device['type']].keys():
                            device_data['tablerefid'] = all_devices_dict[device['type']][device['name']]['id']
                            self.logger.debug(f"CREATE : {device_data}")
                            row = Helper().make_rows(device_data)
                            inventory_id = Database().insert('rackinventory', row)
                        else:
                            return False, f"{device['name']} was not found in any inventory"

            response = "Rack information updated"
            status = True 
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_rack(self, name=None):
        """
        This method will delete a rack.
        """
        status = False
        response = f"Rack {name} not in inventory"
        check_rack = Database().get_record(table='rack', where=f' WHERE `name` = "{name}"')
        if check_rack:
            device_data = { 'rackid': None, 'position': None }
            where = [{"column": "rackid", "value": check_rack[0]['id']}]
            row = Helper().make_rows(device_data)
            Database().update('rackinventory', row, where)
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = False
        )
        return status, response


    def get_inventory(self):
        """
        This method will return all inventory, configured or not in detailed format.
        """
        status=False
        response={'config': {'rack': {'inventory': [] }}}
        devices_dict = {}
        all_devices_dict = {}
        for device_type in ['node','switch','otherdevices','controller']:
            dbname='name'
            if device_type == 'controller':
                dbname='hostname'
            devices_in_db = Database().get_record_join([f'{device_type}.{dbname}', 'rackinventory.*'],
                                                       [f'rackinventory.tablerefid={device_type}.id'], 
                                                       [f"rackinventory.tableref='{device_type}'"])
            if devices_in_db:
                devices_dict[device_type] = Helper().convert_list_to_dict(devices_in_db, dbname)
            all_devices_in_db = Database().get_record(None, device_type)
            if all_devices_in_db:
                all_devices_dict[device_type] = Helper().convert_list_to_dict(all_devices_in_db, dbname)

        for device_type in ['node','switch','otherdevices','controller']:
            if device_type in all_devices_dict:
                for device in all_devices_dict[device_type].keys():
                    status = True
                    if device_type in devices_dict.keys() and device in devices_dict[device_type].keys():
                        response['config']['rack']['inventory'].append({
                                              'name': device,
                                              'type': device_type,
                                              'height': devices_dict[device_type][device]['height'] or '1',
                                              'orientation': devices_dict[device_type][device]['orientation'] or 'front'
                                              })
                    else:
                        response['config']['rack']['inventory'].append({
                                              'name': device,
                                              'type': device_type
                                              })
                    
        return status, response


    def update_inventory(self, request_data=None):
        """
        This method will create or update inventory
        """
        status=False
        response="Internal error"
        network = False
        data, response = {}, {}

        # things we have to set for devices
        inventory_items = {
            'orientation': 'front',
            'height': '1',
        }
        if request_data:
            data = request_data['config']['rack']['inventory']
            devices_dict = {}
            all_devices_dict = {}
            for device_type in ['node','switch','otherdevices','controller']:
                dbname='name'
                if device_type == 'controller':
                    dbname='hostname'
                devices_in_db = Database().get_record_join([f'{device_type}.{dbname}', 'rackinventory.id as invid'],
                                                       [f'rackinventory.tablerefid={device_type}.id'], 
                                                       [f"rackinventory.tableref='{device_type}'"])
                if devices_in_db:
                    devices_dict[device_type] = Helper().convert_list_to_dict(devices_in_db, dbname)
                all_devices_in_db = Database().get_record(None, device_type)
                if all_devices_in_db:
                    all_devices_dict[device_type] = Helper().convert_list_to_dict(all_devices_in_db, dbname)

            for device in data:
                if 'name' not in device:
                    return False, "device name not supplied in data structure"
                create, update = False, False
                inventory_id = None
                for device_type in ['node','switch','otherdevices','controller']:
                    if device_type in devices_dict and device['name'] in devices_dict[device_type]:
                        update = True
                        inventory_id = devices_dict[device_type][device['name']]['invid']
                        break
                if not update:
                    create = True
                   
                device_data = {} 
                if 'type' in device:
                    device_data['tableref'] = device['type']
                elif create:
                    return False, f"Type for {device['name']} not found in data structure"

                for item in ['height','orientation']:
                    if item in device:
                        device_data[item] = device[item]
                           
                for key, value in inventory_items.items():
                    if key in device_data:
                        if isinstance(value, bool):
                            device_data[key] = str(Helper().bool_to_string(device_data[key]))
                    elif create:
                        device_data[key] = value
                        if isinstance(value, bool):
                            device_data[key] = str(Helper().bool_to_string(device_data[key]))
                    if key in device_data and (not device_data[key]) and (key not in inventory_items):
                        del device_data[key]

                if update and inventory_id:
                    self.logger.debug(f"UPDATE: {device_data}")
                    where = [{"column": "id", "value": inventory_id}]
                    row = Helper().make_rows(device_data)
                    Database().update('rackinventory', row, where)
                elif create:
                    if device['type'] in all_devices_dict.keys() and device['name'] in all_devices_dict[device['type']].keys():
                        device_data['tablerefid'] = all_devices_dict[device['type']][device['name']]['id']
                        self.logger.debug(f"CREATE : {device_data}")
                        row = Helper().make_rows(device_data)
                        inventory_id = Database().insert('rackinventory', row)
                    else:
                        return False, f"{device['name']} was not found in any inventory"

            response = "Inventory information updated"
            status = True 
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_inventory(self, name=None, device_type=None):
        """
        This method will delete (clear) inventory.
        """
        status = True
        response = "Inventory cleared"
        data = None
        if name and type:
            devices_dict = {}
            dbname='name'
            if device_type == 'controller':
                dbname='hostname'
            device_in_db = Database().get_record_join(['rackinventory.id as invid'],
                                                       [f'rackinventory.tablerefid={device_type}.id'], 
                                                       [f"rackinventory.tableref='{device_type}'",f"{device_type}.{dbname}='{name}'"])
            if device_in_db:
                where = [{"column": "id", "value": device_in_db[0]['invid']}]
                device_data = { 'rackid': None, 'position': None }
                row = Helper().make_rows(device_data)
                Database().update('rackinventory', row, where)
            else:
                status = False
                response = f"{name} of type {device_type} not in configured inventory"
        else:
            status = False
            response = "device name and/or type not supplied"

        return status, response

