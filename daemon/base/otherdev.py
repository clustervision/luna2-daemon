#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OtherDev Class will handle all other device operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from json import dumps
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.config import Config
from utils.service import Service
from utils.model import Model


class OtherDev():
    """
    This class is responsible for all operations for other devices.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'otherdevices'
        self.table_cap = 'Other Device'

    def get_all_otherdev(self):
        """
        This method will return all the other devices in detailed format.
        """
        status, response = Model().get_record(
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True,
            new_table = 'otherdev'
        )
        return status, response


    def get_otherdev(self, name=None):
        """
        This method will return requested other device in detailed format.
        """
        status, response = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True,
            new_table = 'otherdev'
        )
        return status, response


    def update_otherdev(self, name=None, request_data=None):
        """
        This method will create or update a other device.
        """
        status=False
        data, response = {}, ""
        create, update = False, False
        if request_data:
            data = request_data['config']['otherdev'][name]
            data['name'] = name
            device = Database().get_record(table=self.table, where=f' WHERE `name` = "{name}"')
            if device:
                device_id = device[0]['id']
                if 'newotherdevname' in request_data['config']['otherdev'][name]:
                    data['name'] = data['newotherdevname']
                    del data['newotherdevname']
                update = True
            else:
                create = True
            device_columns = Database().get_columns(self.table)
            ipaddress, network = None, None
            if 'ipaddress' in data.keys():
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data.keys():
                network = data['network']
                del data['network']
            column_check = Helper().compare_list(data, device_columns)
            data = Helper().check_ip_exist(data)
            if data:
                row = Helper().make_rows(data)
                if column_check:
                    if create:
                        device_id = Database().insert(self.table, row)
                        response = f'Device {name} created successfully'
                        status=True
                    if update:
                        where = [{"column": "id", "value": device_id}]
                        Database().update(self.table, row, where)
                        response = f'Device {name} updated successfully'
                        status=True
                else:
                    status=False
                    return status, 'Invalid request: Columns are incorrect'
            # Antoine --->> interface(s) update/create -------------
            if ipaddress or network:
                result, message = Config().device_ipaddress_config(
                    device_id,
                    self.table,
                    ipaddress,
                    network
                )
                if result is False:
                    response = f'{message}'
                    status=False
                else:
                    Service().queue('dhcp','restart')
                    Service().queue('dns','restart')
            return status, response
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def clone_otherdev(self, name=None, request_data=None):
        """
        This method will clone a other device.
        """
        status=False
        data, response = {}, ""
        create = False
        ipaddress, networkname = None, None
        if request_data:
            data = request_data['config']['otherdev'][name]
            if 'newotherdevname' in data:
                data['name'] = data['newotherdevname']
                newotherdevname = data['newotherdevname']
                del data['newotherdevname']
            else:
                status=False
                return status, 'Invalid request: New device name not provided'
            where = f' WHERE `name` = "{newotherdevname}"'
            device = Database().get_record(table=self.table, where=where)
            if device:
                status=False
                return status, f'{newotherdevname} already present in database'
            else:
                create = True
            ipaddress, network = None, None
            if 'ipaddress' in data:
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data:
                networkname=data['network']
                del data['network']
            device_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, device_columns)
            if data:
                if column_check:
                    if create:
                        where=f' WHERE `name` = "{name}"'
                        device = Database().get_record(table=self.table, where=where)
                        del device[0]['id']
                        for key in device[0]:
                            if key not in data:
                                data[key] = device[0][key]

                        row = Helper().make_rows(data)
                        device_id = Database().insert(self.table, row)
                        if not device_id:
                            status=False
                            return status, 'Device not cloned due to clashing config'
                        status=True
                        network = None
                        if networkname:
                            network = Database().get_record_join(
                                [
                                    'ipaddress.ipaddress',
                                    'ipaddress.networkid as networkid',
                                    'network.network',
                                    'network.subnet'
                                ],
                                ['network.id=ipaddress.networkid'],
                                [f"network.name='{networkname}'"]
                            )
                        else:
                            network = Database().get_record_join(
                                [
                                    'ipaddress.ipaddress',
                                    'ipaddress.networkid as networkid',
                                    'network.name as networkname',
                                    'network.network',
                                    'network.subnet'
                                ],
                                [
                                    'network.id=ipaddress.networkid',
                                    'ipaddress.tablerefid=otherdevices.id'
                                ],
                                [f'otherdevices.name="{name}"', 'ipaddress.tableref="otherdevices"']
                            )
                            if network:
                                networkname = network[0]['networkname']
                        if not ipaddress:
                            if not network:
                                where = f' WHERE `name` = "{networkname}"'
                                network = Database().get_record(None, 'network', where)
                                if network:
                                    networkname = network[0]['networkname']
                            if network:
                                ips = Config().get_all_occupied_ips_from_network(networkname)
                                ret, avail = 0, None
                                max_count = 10
                                # we try to ping for 10 ips, if none of these are free, something
                                # else is going on (read: rogue devices)....
                                while(max_count > 0 and ret != 1):
                                    avail = Helper().get_available_ip(
                                        network[0]['network'],
                                        network[0]['subnet'],
                                        ips
                                    )
                                    ips.append(avail)
                                    _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                    max_count -= 1
                                if avail:
                                    ipaddress = avail
                            else:
                                status=False
                                return status, 'Invalid request: Network and ipaddress not provided'
                        result, message = Config().device_ipaddress_config(
                            device_id,
                            self.table,
                            ipaddress,
                            networkname
                        )
                        if result is False:
                            where = [{"column": "id", "value": device_id}]
                            Database().delete_row(self.table, where)
                            # roll back
                            status=False
                            response = f'{message}'
                        else:
                            Service().queue('dhcp', 'restart')
                            Service().queue('dns', 'restart')
                            response = 'Device created'
                else:
                    response = 'Invalid request: Columns are incorrect'
                    status=False
            else:
                response = 'Invalid request: Not enough details to create the device'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_otherdev(self, name=None):
        """
        This method will delete a other device.
        """
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return status, response

