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
Switch Class will handle all switch operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.config import Config
from utils.service import Service
from utils.model import Model

class Switch():
    """
    This class is responsible for all operations for switch.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'switch'
        self.table_cap = self.table.capitalize()


    def get_all_switches(self):
        """
        This method will return all the switches in detailed format.
        """
        status, response = Model().get_record(
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        if status is True:
            self.attach_mgmt_interface(response)
        return status, response


    def get_switch(self, name=None):
        """
        This method will return requested switch in detailed format.
        """
        status, response = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        if status is True:
            self.attach_mgmt_interface(response)
        return status, response


    def attach_mgmt_interface(self, response):
        """Annotate each switch in a get_record response with its management interface (the mgmt=1
        one): its name, and the switch's own IP/MAC -- which under the unify model live on that
        interface, not the switch row. Model.get_record's ip_check looks at tableref="switch" and so
        finds nothing now; sourcing IP/MAC here is what keeps `switch show` reporting them, above the
        (legacy, now-empty) macaddress row column."""
        for name, record in response['config'][self.table].items():
            mgmt = Database().get_record_join(
                ['switchinterface.id', 'switchinterface.interface', 'switchinterface.macaddress'],
                ['switchinterface.switchid=switch.id'],
                [f'switch.name="{name}"', 'switchinterface.mgmt=1']
            )
            if not mgmt:
                continue
            record['mgmt_interface'] = mgmt[0]['interface']
            if mgmt[0]['macaddress']:
                record['macaddress'] = mgmt[0]['macaddress']
            ipaddress, ipaddress_ipv6, network = Model().get_ip_network(
                table='switchinterface', record_id=mgmt[0]['id']
            )
            if ipaddress or ipaddress_ipv6:
                record['ipaddress'] = ipaddress
                record['ipaddress_ipv6'] = ipaddress_ipv6
                record['network'] = network


    def ensure_mgmt_interface(self, switchid):
        """The id of the switch's management interface (mgmt=1), creating a default 'eth0' one if the
        switch has none yet. Routes the switch's own IP/MAC (from -I/-N/-m) onto it (unify model)."""
        rows = Database().get_record(table='switchinterface', where=f"switchid='{switchid}' AND mgmt=1")
        if rows:
            return sorted(rows, key=lambda r: r['id'])[0]['id']
        name = 'eth0'
        if Database().get_record(table='switchinterface', where=f"switchid='{switchid}' AND interface='{name}'"):
            name = 'mgmt0'
        return Database().insert('switchinterface', [
            {'column': 'switchid', 'value': switchid},
            {'column': 'interface', 'value': name},
            {'column': 'mgmt', 'value': 1}])


    def update_switch(self, name=None, request_data=None):
        """
        This method will create or update a switch.
        """
        status=False
        response="Internal error"
        network = False
        data, response = {}, {}
        create, update = False, False

        # things we have to set for a switch
        items = {
            'oid': '.1.3.6.1.2.1.17.7.1.2.2.1.2',
            'read': 'public',
            'rw': 'trusted'
        }
        if request_data:
            data = request_data['config'][self.table][name]
            data['name'] = name
            nonetwork = False
            if 'nonetwork' in data:
                nonetwork = Helper().make_bool(data['nonetwork'])
                del data['nonetwork']
            where = f"name = '{name}'"
            check_switch = Database().get_record(table=self.table, where=where)
            if check_switch:
                switchid = check_switch[0]['id']
                if 'newswitchname' in request_data['config'][self.table][name]:
                    data['name'] = data['newswitchname']
                    del data['newswitchname']
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

            # an empty string from the CLI means: clear the field. Store NULL so
            # a cleared field reads back the same as a never-set one ("None").
            for key in ('bootfile', 'default_url', 'ztpconfig', 'ztpformat',
                        'url_protocol', 'url_server', 'ostype'):
                if key in data and str(data[key]).strip() == '':
                    data[key] = None

            ipaddress, network, macaddress = None, None, None
            if 'ipaddress' in data.keys():
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data.keys():
                network = data['network']
                del data['network']
            # the switch's own MAC belongs to its management interface (unify model), not the switch
            # row; take it out of the row data and apply it to that interface below.
            if 'macaddress' in data.keys():
                macaddress = data['macaddress']
                del data['macaddress']

            switch_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, switch_columns)
            data = Helper().check_ip_exist(data)
            if data:
                row = Helper().make_rows(data)
                if column_check:
                    if create:
                        switchid = Database().insert(self.table, row)
                        response = f'Switch {name} created successfully'
                        status=True
                    if update:
                        where = [{"column": "id", "value": switchid}]
                        Database().update(self.table, row, where)
                        response = f'Switch {name} updated successfully'
                        status=True
                else:
                    response = 'Invalid request: Columns are incorrect'
                    status=False
                    return status, response
            # ----------- management interface (mgmt=1) update/create -------------
            # the switch's own IP/MAC live on its management interface, not the switch row.
            if macaddress is not None or ipaddress is not None or network is not None or nonetwork:
                mgmt_ifid = self.ensure_mgmt_interface(switchid)
                if macaddress is not None:
                    Database().update('switchinterface',
                                      [{'column': 'macaddress', 'value': macaddress or None}],
                                      [{'column': 'id', 'value': mgmt_ifid}])
                if nonetwork:
                    result, message = Config().device_raw_ipaddress_config(
                        mgmt_ifid, 'switchinterface', ipaddress)
                    if result is False:
                        response = f'{message}'
                        status=False
                        if create:
                            self.delete_switch(name)
                elif ipaddress or network:
                    result, message = Config().device_ipaddress_config(
                        mgmt_ifid, 'switchinterface', ipaddress, network)
                    if result is False:
                        response = f'{message}'
                        status=False
                        if create:
                            self.delete_switch(name)
                    else:
                        Service().queue('dhcp','restart')
                        Service().queue('dhcp6','restart')
                        Service().queue('dns','reload')
            return status, response
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def clone_switch(self, name=None, request_data=None):
        """
        This method will clone a switch.
        """
        status=False
        data, response = {}, ""
        ipaddress, networkname = None, None
        if request_data:
            data = request_data['config'][self.table][name]
            if 'newswitchname' in data:
                data['name'] = data['newswitchname']
                newswitchname = data['newswitchname']
                del data['newswitchname']
            else:
                status=False
                return status, 'Invalid request: New switch name not provided'
            where = f"name = '{newswitchname}'"
            check_switch = Database().get_record(table=self.table, where=where)
            if check_switch:
                status=False
                return status, f'Invalid request: {newswitchname} already present in database'
            ipaddress, network = None, None
            if 'ipaddress' in data:
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data:
                networkname = data['network']
                del data['network']
            switch_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, switch_columns)
            if data:
                if column_check:
                    where = f"name = '{name}'"
                    switch = Database().get_record(table=self.table, where=where)
                    if not switch:
                        status = False
                        return status, f"Source switch {name} does not exist"
                    del switch[0]['id']
                    for key in switch[0]:
                        if key not in data:
                            data[key] = switch[0][key]
                    row = Helper().make_rows(data)
                    switch_id = Database().insert(self.table, row)
                    if not switch_id:
                        status=False
                        return status, 'Internal error: Switch not cloned due to clashing config'
                    status=True
                    network=None
                    if networkname:
                        network = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.networkid as networkid',
                                'network.network', 'network.network_ipv6',
                                'network.subnet', 'network.subnet_ipv6'
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
                                'ipaddress.tablerefid=switch.id'
                            ],
                            [f'switch.name="{name}"', 'ipaddress.tableref="switch"']
                        )
                        if network:
                            data['network'] = network[0]['networkname']
                            networkname=data['network']
                    ipaddress6, result, result6, avail = None, False, True, None
                    if not ipaddress:
                        if not network:
                            where = f"name = '{networkname}'"
                            network = Database().get_record(table='network', where=where)
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
                            return True, 'Switch cloned without network or ipaddress'
                    if ipaddress:
                        result, message = Config().device_ipaddress_config(
                            switch_id,
                            self.table,
                            ipaddress,
                            networkname
                        )
                    if ipaddress6:
                        result6, message = Config().device_ipaddress_config(
                            switch_id,
                            self.table,
                            ipaddress6,
                            networkname
                        )
                    if result is False or result6 is False:
                        where = [{"column": "id", "value": switch_id}]
                        Database().delete_row(self.table, where)
                        # roll back
                        status=False
                        response = f'Invalid request: {message}'
                    else:
                        Service().queue('dhcp', 'restart')
                        Service().queue('dhcp6', 'restart')
                        Service().queue('dns', 'reload')
                        response = 'Switch cloned'
                else:
                    response = 'Invalid request: Columns are incorrect'
                    status=False
            else:
                response = 'Invalid request: Not enough information provided'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        self.logger.info(f"my response: {response}")
        return status, response


    def delete_switch(self, name=None):
        """
        This method will delete a switch.
        """
        switch = Database().get_record(table='switch', where=f"name = '{name}'")
        if switch:
            switchid=switch[0]['id']
            inuse = Database().get_record(table='node', where=f"switchid='{switchid}'")
            if inuse:
                inuseby=[]
                while len(inuse) > 0 and len(inuseby) < 11:
                    node=inuse.pop(0)
                    inuseby.append(node['name'])
                response = f"Invalid request: switch {name} currently in use by "+', '.join(inuseby)+" ..."
                return False, response

            # a switch's interfaces (and their ipaddress rows) are not owned by Model().delete_record,
            # so clear them here or they orphan when the switch is deleted.
            for switch_interface in Database().get_record(table='switchinterface',
                                                          where=f"switchid='{switchid}'"):
                Database().delete_row('ipaddress',
                                      [{"column": "tablerefid", "value": switch_interface['id']},
                                       {"column": "tableref", "value": "switchinterface"}])
            Database().delete_row('switchinterface', [{"column": "switchid", "value": switchid}])

            Database().delete_row('rackinventory', [{"column": "tablerefid", "value": switchid},
                                                    {"column": "tableref", "value": "switch"}])
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return status, response

