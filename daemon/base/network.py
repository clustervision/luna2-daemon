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
Network Class will handle all network operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

#from json import dumps
from concurrent.futures import ThreadPoolExecutor
from utils.queue import Queue
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.config import Config
from utils.service import Service


class Network():
    """
    This class is responsible for all operations for network.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_networks(self):
        """
        This method will return all the network in detailed format.
        """
        status=False
        networks = Database().get_record(None, 'network', None)
        if networks:
            response = {'config': {'network': {} }}
            for network in networks:
                network['network'] = Helper().get_network(network['network'], network['subnet'])
                del network['id']
                del network['subnet']
                network['dhcp'] = Helper().make_bool(network['dhcp'])
                if not network['dhcp']:
                    del network['dhcp_range_begin']
                    del network['dhcp_range_end']
                    network['dhcp'] = False
                else:
                    network['dhcp'] = True
                network['type'] = network['type'] or 'ethernet'
                response['config']['network'][network['name']] = network
            status=True
        else:
            self.logger.error('No networks is available.')
            response = 'No networks is available'
            status=False
        return status, response


    def get_network(self, name=None):
        """
        This method will return requested network in detailed format.
        """
        status=False
        networks = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if networks:
            response = {'config': {'network': {} }}
            for network in networks:
                network['network'] = Helper().get_network(network['network'], network['subnet'])
                del network['id']
                del network['subnet']
                network['dhcp'] = Helper().make_bool(network['dhcp'])
                if not network['dhcp']:
                    del network['dhcp_range_begin']
                    del network['dhcp_range_end']
                    network['dhcp'] = False
                else:
                    network['dhcp'] = True
                network['type'] = network['type'] or 'ethernet'
                response['config']['network'][name] = network
            status=True
        else:
            self.logger.error(f'Network {name} is not available.')
            response = f'Network {name} is not available'
            status=False
        return status, response


    def update_network(self, name=None, request_data=None):
        """
        This method will create or update a network.
        """
        status=True
        response="Internal error"
        data = {}
        create, update = False, False
        if request_data:
            data = request_data['config']['network'][name]
            data['name'] = name
            network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
            if network:
                networkid = network[0]['id']
                if 'newnetname' in request_data['config']['network'][name]:
                    newnetname = request_data['config']['network'][name]['newnetname']
                    where = f' WHERE `name` = "{newnetname}"'
                    check_network = Database().get_record(None, 'network', where)
                    if check_network:
                        status=False
                        return status, f'{newnetname} already present in database'
                    else:
                        data['name'] = data['newnetname']
                        del data['newnetname']
                update = True
            else:
                create = True
            used_ips, dhcp_size, redistribute_ipaddress = 0, 0, None
            if 'network' in data:
                network_ip = Helper().check_ip(data['network'])
                if network_ip:
                    network_details = Helper().get_network_details(data['network'])
                    data['network'] = network_ip
                    data['subnet'] = network_details['subnet']
                    used_ips = Helper().get_quantity_occupied_ipaddress_in_network(name)
                    if network:
                        if (network[0]['network'] != data['network']) or (network[0]['subnet'] != data['subnet']):
                            redistribute_ipaddress = True
                            self.logger.info("We will redistribute ip addresses")
                            if 'gateway' not in data:
                                data['gateway'] = ''
                                # we have to remove the gateway if we did not get a new one and an
                                # existing is in place. should we warn the user? pending
                else:
                    status=False
                    return status, f'Invalid request: Incorrect network IP: {data["network"]}'
            elif network:
                # we fetch what we have from the DB
                data['network'] = network[0]['network']
                data['subnet'] = network[0]['subnet']
            else:
                status=False
                ret_msg = 'Invalid request: Not enough details provided.' \
                          ' network/subnet in CIDR notation expected'
                return status, ret_msg
            if 'zone' in data:
                if (data['zone'] != "external") and (data['zone'] != "internal"):
                    status=False
                    ret_msg = 'Invalid request: Incorrect zone. Must be either internal or external'
                    return status, ret_msg
            elif create is True:
                data['zone']="internal"
            if 'gateway' in data:
                gateway_details = Helper().check_ip_range(
                    data['gateway'],
                    data['network'] + '/' + data['subnet']
                )
                if (not gateway_details) and data['gateway'] != '':
                    status=False
                    return status, f'Invalid request: Incorrect gateway IP: {data["gateway"]}'
            if 'nameserver_ip' in data:
                nsip_details = Helper().check_ip_range(
                    data['nameserver_ip'],
                    data['network'] + '/' + data['subnet']
                )
                if (not nsip_details) and data['nameserver_ip'] != '':
                    status=False
                    ret_msg = f'Invalid request: Incorrect Nameserver IP: {data["nameserver_ip"]}'
                    return status, ret_msg
            if 'ntp_server' in data:
                subnet = data['network'] + '/' + data['subnet']
                ntp_details = Helper().check_ip_range(data['ntp_server'], subnet)
                if (not ntp_details) and data['ntp_server'] != '':
                    status=False
                    return status, f'Invalid request: Incorrect NTP Server IP: {data["ntp_server"]}'
            if 'dhcp' in data:
                data['dhcp'] = Helper().bool_to_string(data['dhcp'])
                self.logger.info(f"dhcp is set to {data['dhcp']}")
                if 'dhcp_range_begin' in data:
                    subnet = data['network']+'/'+data['subnet']
                    dhcp_start_details = Helper().check_ip_range(data['dhcp_range_begin'], subnet)
                    if not dhcp_start_details:
                        status=False
                        ret_msg = f'Invalid request: Incorrect dhcp start: {data["dhcp_range_begin"]}'
                        return status, ret_msg
                elif data['dhcp'] != "0":
                    status=False
                    return status, 'Invalid request: DHCP start range is a required parameter'
                if 'dhcp_range_end' in data:
                    subnet = data['network']+'/'+data['subnet']
                    dhcp_end_details = Helper().check_ip_range(data['dhcp_range_end'], subnet)
                    if not dhcp_end_details:
                        status=False
                        ret_msg = f'Invalid request: Incorrect dhcp end: {data["dhcp_range_end"]}'
                        return status, ret_msg
                elif data['dhcp'] != "0":
                    status=False
                    return status, 'Invalid request: DHCP end range is a required parameter'
                if data['dhcp'] == "1":
                    dhcp_size = Helper().get_ip_range_size(
                        data['dhcp_range_begin'],
                        data['dhcp_range_end']
                    )
                    redistribute_ipaddress = True
                    # to make sure we do not overlap with existing node ip configs
            else:
                if network:
                    data['dhcp'] = network[0]['dhcp']
                    data['dhcp_range_begin'] = network[0]['dhcp_range_begin']
                    data['dhcp_range_end'] = network[0]['dhcp_range_end']
                    dhcp_size = Helper().get_ip_range_size(
                        data['dhcp_range_begin'],
                        data['dhcp_range_end']
                    )
                else:
                    data['dhcp'] = 0
                    data['dhcp_range_begin'] = ""
                    data['dhcp_range_end'] = ""

            network_columns = Database().get_columns('network')
            column_check = Helper().compare_list(data, network_columns)
            if column_check:
                row = Helper().make_rows(data)
                if create:
                    Database().insert('network', row)
                    response = f'Network {name} created successfully'
                    status=True
                elif update:
                    if redistribute_ipaddress:
                        nwk_size = Helper().get_network_size(data['network'], data['subnet'])
                        avail = nwk_size - dhcp_size
                        if avail < used_ips:
                            response = f'The proposed network config allows for {nwk_size} ip '
                            response += f'addresses. DHCP range will occupy {dhcp_size} ip '
                            response += 'addresses. The request will not accomodate for the '
                            response += f'currently {used_ips} in use ip addresses.'
                            status=False
                            return status, response
                    where = [{"column": "id", "value": networkid}]
                    Database().update('network', row, where)
                    # TWANNIE
                    if redistribute_ipaddress:
                        Config().update_dhcp_range_on_network_change(name)
                        # below section takes care (in the background), adding/renaming/deleting.
                        # for adding next free ip-s will be selected.
                        # time consuming therefor background
                        queue_id, _ = Queue().add_task_to_queue(
                            f'update_all_interface_ipaddress:{name}',
                            'network_change'
                        )
                        next_id = Queue().next_task_in_queue('network_change')
                        if queue_id == next_id:
                            executor = ThreadPoolExecutor(max_workers=1)
                            executor.submit(
                                Config().update_interface_ipaddress_on_network_change,
                                name
                            )
                            executor.shutdown(wait=False)
                            # Config().update_interface_ipaddress_on_network_change(name)
                    response = f'Network {name} updated successfully'
                    status=True
                Service().queue('dns','restart')
                Service().queue('dhcp','restart')
                # technically only needed when dhcp changes, but it doesn't hurt to just do it
            else:
                status=False
                response='Invalid request: Columns are incorrect'
        else:
            status=False
            response='Invalid request: Did not receive data'
        return status, response


    def delete_network(self, name=None):
        """
        This method will delete a network.
        """
        status=False
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            Database().delete_row('network', [{"column": "name", "value": name}])
            data = {}
            data['shared'] = ""
            row = Helper().make_rows(data)
            where = [{"column": "shared", "value": name}]
            Database().update('network', row, where)
            Service().queue('dns','restart')
            Service().queue('dhcp','restart')
            response = 'Network removed'
            status=True
        else:
            response = f'Network {name} not present in database'
            status=False
        return status, response


    def network_ip(self, name=None, ipaddress=None):
        """
        This method will identifies the requested ipaddress is available or not.
        """
        status=False
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            ip_with_subnet = network[0]['network'] + '/' + network[0]['subnet']
            ip_detail = Helper().check_ip_range(ipaddress, ip_with_subnet)
            if ip_detail:
                where = f' WHERE ipaddress = "{ipaddress}"'
                check_ip = Database().get_record(None, 'ipaddress', where)
                if check_ip:
                    response = {'config': {'network': {ipaddress: {'status': 'taken'} } } }
                    status=True
                else:
                    response = {'config': {'network': {ipaddress: {'status': 'free'} } } }
                    status=True
            else:
                response = f'{ipaddress} is not in the range'
                status=False
        else:
            response = f'Network {name} not present in database'
            status=False
        return status, response


    def next_free_ip(self, name=None):
        """
        This method will identify the next available ipaddress on a network.
        """
        response = f'Network {name} not present in database'
        status=False
        #Antoine
        ips = Config().get_all_occupied_ips_from_network(name)
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        avail = None
        if network:
            response = f'Network {name} has no free addresses'
            ret = 0
            max_count = 10
            # we try to ping for 10 ips, if none of these are free, something else is going on
            # (read: rogue devices)....
            while(max_count > 0 and ret != 1):
                avail = Helper().get_available_ip(network[0]['network'], network[0]['subnet'], ips)
                ips.append(avail)
                _,ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                max_count-=1
        if avail:
            response = {'config': {'network': {name: {'nextip': avail} } } }
            status=True
        else:
            response = f'network {name} does not provide for any free IP address'
        return status, response


    def taken_ip(self, name=None):
        """
        This method will identify the all taken ipaddress on a network.
        """
        # TODO ->
        # Need to convert in Join query.
        # Get ipaddress from ipaddress table and device name which have the network name provided.
        # device can be node, controller, switch, otherdevices. Remember nodeinterface table.
        status=False
        taken = []
        network_id = Database().id_by_name('network', name)
        if network_id:
            where = f' WHERE `networkid` = "{network_id}"'
            ip_list = Database().get_record("*", 'ipaddress', where=where)
            if ip_list:
                for each in ip_list:
                    if 'interface' in each['tableref']:
                        tablerefid = each['tablerefid']
                        where = f' WHERE `id` = "{tablerefid}"'
                        nodeid = Database().get_record("*",'nodeinterface', where)
                        nodeid = nodeid[0]['nodeid']
                        device_name = Database().name_by_id('node', nodeid)
                    elif 'controller' in each['tableref']:
                        tablerefid = each['tablerefid']
                        where = f' WHERE `id` = "{tablerefid}"'
                        hostname = Database().get_record("*",'controller', where)
                        self.logger.info(hostname)
                        if hostname:
                            device_name = hostname[0]['hostname']
                        else:
                            device_name = "Controller has No Hostname"
                    else:
                        device_name = Database().name_by_id(each['tableref'], each['tablerefid'])
                    taken.append({'ipaddress': each['ipaddress'], 'device': device_name})
                    device_name = ""
                response = {'config': {'network': {name: {'taken': taken} } } }
                status=True
                self.logger.info(response)
            else:
                response = 'All IP Address are free on Network {name}. None is Taken.'
                status=False
        else:
            response = f'Network {name} not present in database.'
            status=False
        return status, response
