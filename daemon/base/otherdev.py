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
OtherDev Class will handle all other device operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

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
            nonetwork = False
            if 'nonetwork' in data:
                nonetwork = Helper().make_bool(data['nonetwork'])
                del data['nonetwork']
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
            if nonetwork:
                result, message = Config().device_raw_ipaddress_config(
                    device_id,
                    self.table,
                    ipaddress
                )
                if result is False:
                    response = f'{message}'
                    status=False
            elif ipaddress or network:
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
                    Service().queue('dhcp6','restart')
                    Service().queue('dns','reload')
            return status, response
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def clone_otherdev(self, name=None, request_data=None):
        """
        This method clones an other device.
        """
        status=False
        data, response = {}, ""
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
                    where=f' WHERE `name` = "{name}"'
                    device = Database().get_record(table=self.table, where=where)
                    if not device:
                        status = False
                        return status, f"Source device {name} does not exist"
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
                                'ipaddress.ipaddress_ipv6',
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
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.networkid as networkid',
                                'network.name as networkname',
                                'network.network', 'network.network_ipv6',
                                'network.subnet', 'network.subnet_ipv6'
                            ],
                            [
                                'network.id=ipaddress.networkid',
                                'ipaddress.tablerefid=otherdevices.id'
                            ],
                            [f'otherdevices.name="{name}"', 'ipaddress.tableref="otherdevices"']
                        )
                        if network:
                            networkname = network[0]['networkname']
                    ipaddress6, result, result6, avail = None, False, True, None
                    if not ipaddress:
                        if not network:
                            where = f' WHERE `name` = "{networkname}"'
                            network = Database().get_record(None, 'network', where)
                            if network:
                                networkname = network[0]['networkname']
                        if network:
                            if network[0]['network']:
                                ips = Config().get_all_occupied_ips_from_network(networkname)
                                if 'ipaddress' in network[0]:
                                    avail = Helper().get_next_ip(network[0]['ipaddress'], ips, ping=True)
                                if not avail:
                                    avail = Helper().get_available_ip(
                                        network[0]['network'],
                                        network[0]['subnet'],
                                        ips, ping=True
                                    )
                                if avail:
                                    ipaddress = avail
                            avail = None
                            if network[0]['network_ipv6']:
                                ips = Config().get_all_occupied_ips_from_network(networkname,'ipv6')
                                if 'ipaddress_ipv6' in network[0]:
                                    avail = Helper().get_next_ip(network[0]['ipaddress_ipv6'], ips, ping=True)
                                if not avail:
                                    avail = Helper().get_available_ip(
                                        network[0]['network_ipv6'],
                                        network[0]['subnet_ipv6'],
                                        ips, ping=True
                                    )
                                if avail:
                                    ipaddress6 = avail
                        else:
                            status=False
                            return status, 'Invalid request: Network and ipaddress not provided'
                    if ipaddress:
                        result, message = Config().device_ipaddress_config(
                            device_id,
                            self.table,
                            ipaddress,
                            networkname
                        )
                    if ipaddress6:
                        result6, message = Config().device_ipaddress_config(
                            device_id,
                            self.table,
                            ipaddress6,
                            networkname
                        )
                    if result is False or result6 is False:
                        where = [{"column": "id", "value": device_id}]
                        Database().delete_row(self.table, where)
                        # roll back
                        status=False
                        response = f'{message}'
                    else:
                        Service().queue('dhcp', 'restart')
                        Service().queue('dhcp6','restart')
                        Service().queue('dns', 'reload')
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
        This method will delete an other-device.
        """
        device = Database().get_record(table='otherdevices', where=f' WHERE `name` = "{name}"')
        if device:
            Database().delete_row('rackinventory', [{"column": "tablerefid", "value": device[0]['id']},
                                                    {"column": "tableref", "value": "otherdevices"}])
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return status, response

