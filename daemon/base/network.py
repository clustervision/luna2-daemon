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

import re
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
                    del network['dhcp_range_begin_ipv6']
                    del network['dhcp_range_end_ipv6']
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
                if network['network']:
                    network['network'] = Helper().get_network(network['network'], network['subnet'])
                if network['network_ipv6']:
                    network['network_ipv6'] = Helper().get_network(network['network_ipv6'], network['subnet_ipv6'])
                del network['id']
                del network['subnet']
                del network['subnet_ipv6']
                network['dhcp'] = Helper().make_bool(network['dhcp'])
                if not network['dhcp']:
                    del network['dhcp_range_begin']
                    del network['dhcp_range_end']
                    del network['dhcp_range_begin_ipv6']
                    del network['dhcp_range_end_ipv6']
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
        db_data = None
        create, update = False, False

        if request_data:
            used_ips, used6_ips = 0, 0
            redistribute_ipaddress, clear_ipv4, clear_ipv6 = False, False, False
            default_gateway_metric, default_zone = "101", "internal"
            controller_ips=[]

            data = request_data['config']['network'][name]
            data['name'] = name
            network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
            if network:
                used_ips = Helper().get_quantity_occupied_ipaddress_in_network(name,ipversion='ipv4')
                used6_ips = Helper().get_quantity_occupied_ipaddress_in_network(name,ipversion='ipv6')
                db_data = network[0]
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
 
            # ---------------------- parse incoming data -------------------
            if 'network' in data:
                network_ip = Helper().check_ip(data['network'])
                if network_ip:
                    #ipv6=Helper().check_if_ipv6(data['network'])
                    network_details = Helper().get_network_details(data['network'])
                    data['network'] = network_details['network']
                    data['subnet'] = network_details['subnet']
                    self.logger.info(f"NETWORK {name} IP: {data['network']} / {data['subnet']}")
                    where = f" WHERE (`name`!='{name}' AND `name`!='{data['name']}')"
                    where += f" AND ((`network`='{data['network']}' AND `subnet`='{data['subnet']}')"
                    where += f" OR (`network_ipv6`='{data['network']}' AND `subnet_ipv6`='{data['subnet']}'))"
                    claship = Database().get_record(None, 'network', where)
                    if claship:
                        status=False
                        ret_msg = f"Invalid request: Clashing network/subnet with existing network {claship[0]['name']}"
                        return status, ret_msg
                    used_ips = Helper().get_quantity_occupied_ipaddress_in_network(name,ipversion='ipv4')
                    used6_ips = Helper().get_quantity_occupied_ipaddress_in_network(name,ipversion='ipv6')
                    if network: #database data
                        if ((db_data['network'] != data['network'] or db_data['subnet'] != data['subnet']) and
                               (db_data['network_ipv6'] != data['network']) or (db_data['subnet_ipv6'] != data['subnet'])):

                            # renumbering controllers prepare. this could be tricky. - Antoine
                            # for H/A things should be taken in consideration.... 
                            controllers = Database().get_record_join(
                                ['controller.hostname','ipaddress.ipaddress','ipaddress.ipaddress_ipv6','ipaddress.id as ipid'],
                                ['ipaddress.tablerefid=controller.id','ipaddress.networkid=network.id'],
                                ['tableref="controller"',f"network.name='{data['name']}'"]
                            )
                            if controllers:
                                self.logger.info("Network change affects controllers...")
                                for controller in controllers:
                                    controller_details=None
                                    if controller['hostname'] in data:
                                        if controller['ipaddress'] == data[controller['hostname']] or controller['ipaddress_ipv6'] == data[controller['hostname']]:
                                            self.logger.info(f"Not using new ip address {data[controller['hostname']]} for controller {controller['hostname']}")
                                        else:
                                            controller_details = Helper().check_ip_range(data[controller['hostname']], data['network'] + '/' + data['subnet'])
                                            if not controller_details:
                                                status=False
                                                ret_msg = f"Invalid request: Controller address mismatch with network address/subnet. "
                                                ret_msg += f"Please provide valid ip address for controller {controller['hostname']}"
                                                return status, ret_msg
                                            controller_ips.append({'ipaddress': data[controller['hostname']], 'id': controller['ipid'], 'hostname': controller['hostname']})
                                            self.logger.info(f"Using new ip address {data[controller['hostname']]} for controller {controller['hostname']}")
                                            del data[controller['hostname']]
                                    else:
                                        if Helper().check_if_ipv6(data['network']):
                                            controller_details = Helper().check_ip_range(controller['ipaddress_ipv6'], data['network'] + '/' + data['subnet'])
                                        else:
                                            controller_details = Helper().check_ip_range(controller['ipaddress'], data['network'] + '/' + data['subnet'])
                                        if not controller_details:
                                            status=False
                                            ret_msg = f"Invalid request: Controller(s) inside network that doesn't match address/subnet. "
                                            ret_msg += f"Please provide ip address for controller {controller['hostname']}"
                                            return status, ret_msg

                            redistribute_ipaddress = True
                            self.logger.info("We will redistribute ip addresses")
                            if 'gateway' not in data:
                                data['gateway'] = None
                                data['gateway_metric'] = None
                                # we have to remove the gateway if we did not get a new one and an
                                # existing is in place. should we warn the user? pending
                            if 'dhcp' not in data:
                                data['dhcp'] = 0
                                #data['dhcp_range_begin'] = None
                                #data['dhcp_range_end'] = None
                else:
                    status=False
                    return status, f'Invalid request: Incorrect network IP: {data["network"]}'
            elif not network:
                status=False
                ret_msg = 'Invalid request: Not enough details provided. network/subnet in CIDR notation expected'
                return status, ret_msg

            if 'zone' in data:
                if (data['zone'] != "external") and (data['zone'] != "internal"):
                    status=False
                    ret_msg = 'Invalid request: Incorrect zone. Must be either internal or external'
                    return status, ret_msg
                default_zone=data['zone']
            elif create is True:
                data['zone']="internal"
            if 'gateway' in data:
                if data['gateway'] == "":
                    data['gateway'] = None
                elif data['gateway'] is not None:
                    gateway_details=None
                    if 'network' in data and 'subnet' in data:
                        gateway_details = Helper().check_ip_range(data['gateway'],data['network'] + '/' + data['subnet'])
                    elif Helper().check_if_ipv6(data['gateway']) and db_data['network_ipv6'] and db_data['subnet_ipv6']:
                        gateway_details = Helper().check_ip_range(data['gateway'],db_data['network_ipv6'] + '/' + db_data['subnet_ipv6'])
                    elif db_data['network'] and db_data['subnet']:
                        gateway_details = Helper().check_ip_range(data['gateway'],db_data['network'] + '/' + db_data['subnet'])
                    if (not gateway_details) and data['gateway'] != '':
                        status=False
                        return status, f'Invalid request: Incorrect gateway IP: {data["gateway"]}'
                    if 'gateway_metric' not in data:
                        if default_zone == "external":
                            default_gateway_metric="100"
                        data['gateway_metric'] = default_gateway_metric
            if 'nameserver_ip' in data:
                nsip_details = Helper().check_ip(data['nameserver_ip'])
                if (not nsip_details) and data['nameserver_ip'] != '':
                    status=False
                    ret_msg = f'Invalid request: Incorrect Nameserver IP: {data["nameserver_ip"]}'
                    return status, ret_msg
            if 'ntp_server' in data:
                if Helper().check_if_ipv6(data['ntp_server']):
                    status=False
                    return status, f'Invalid request: Incorrect NTP Server IP: {data["ntp_server"]}. Server name or IPv4 address expected'
                ntp_details = Helper().check_ip(data['ntp_server'])
                if (not ntp_details) and data['ntp_server'] != '':
                    regex = re.compile(r"^[a-z0-9\.\-]+$")
                    if not regex.match(data['ntp_server']):
                        status=False
                        return status, f'Invalid request: Incorrect NTP Server IP: {data["ntp_server"]}'
            if 'dhcp' in data:
                data['dhcp'] = Helper().bool_to_string(data['dhcp'])
                if 'dhcp_range_begin' in data:
                    dhcp_start_details = None
                    if 'network' in data and 'subnet' in data:
                        dhcp_start_details = Helper().check_ip_range(data['dhcp_range_begin'], data['network'] + '/' + data['subnet'])
                    elif Helper().check_if_ipv6(data['dhcp_range_begin']) and db_data['network_ipv6'] and db_data['subnet_ipv6']:
                        dhcp_start_details = Helper().check_ip_range(data['dhcp_range_begin'], db_data['network_ipv6'] + '/' + db_data['subnet_ipv6'])
                    elif db_data['network'] and db_data['subnet']:
                        dhcp_start_details = Helper().check_ip_range(data['dhcp_range_begin'], db_data['network'] + '/' + db_data['subnet'])
                    if not dhcp_start_details:
                        status=False
                        ret_msg = f'Invalid request: Incorrect dhcp start: {data["dhcp_range_begin"]}'
                        return status, ret_msg
                elif data['dhcp'] != "0":
                    status=False
                    return status, 'Invalid request: DHCP start range is a required parameter'
                if 'dhcp_range_end' in data:
                    dhcp_end_details = None
                    if 'network' in data and 'subnet' in data:
                        dhcp_end_details = Helper().check_ip_range(data['dhcp_range_end'], data['network'] + '/' + data['subnet'])
                    elif Helper().check_if_ipv6(data['dhcp_range_end']) and db_data['network_ipv6'] and db_data['subnet_ipv6']:
                        dhcp_end_details = Helper().check_ip_range(data['dhcp_range_end'], db_data['network_ipv6'] + '/' + db_data['subnet_ipv6'])
                    elif db_data['network'] and db_data['subnet']:
                        dhcp_end_details = Helper().check_ip_range(data['dhcp_range_end'], db_data['network'] + '/' + db_data['subnet'])
                    if not dhcp_end_details:
                        status=False
                        ret_msg = f'Invalid request: Incorrect dhcp end: {data["dhcp_range_end"]}'
                        return status, ret_msg
                elif data['dhcp'] != "0":
                    status=False
                    return status, 'Invalid request: DHCP end range is a required parameter'
                if data['dhcp'] == "1":
                    redistribute_ipaddress = True
                    # to make sure we do not overlap with existing node ip configs

            if 'clear' in data:
                if data['clear'] == 'ipv6' and db_data['network']:
                    data['network_ipv6']=None
                    data['subnet_ipv6']=None
                    data['gateway_ipv6']=None
                    data['dhcp_range_begin_ipv6']=None
                    data['dhcp_range_end_ipv6']=None
                    clear_ipv6 = True
                elif data['clear'] == 'ipv4' and db_data['network_ipv6']:
                    data['network']=None
                    data['subnet']=None
                    data['gateway']=None
                    data['dhcp_range_begin']=None
                    data['dhcp_range_end']=None
                    clear_ipv4 = True
                else:
                    status=False
                    ret_msg = 'Invalid request: clearing ipv4 requires ipv6 to be configured first and vice versa'
                    return status, ret_msg
                del data['clear']
            else:
                #IPv6, ipv6. we basically allow both types to be send, but we figure out what we're dealing with. - Antoine
                for item in ['dhcp_range_begin','dhcp_range_end','gateway','network','nameserver_ip']:
                    if item in data and Helper().check_if_ipv6(data[item]):
                        data[item+'_ipv6'] = data[item]
                        self.logger.debug(f"** Converting {item} to {item}_ipv6")
                        del data[item]
                        if item == 'network':
                            data['subnet_ipv6'] = data['subnet']
                            del data['subnet']

            # to make sure we ignore presented controller ip config if it's not relevant
            controllers = Database().get_record(None, "controller", None)
            if controllers:
                 for controller in controllers:
                     if controller['hostname'] in data:
                         del data[controller['hostname']]

            for controller in controller_ips:
                where = f"WHERE ipaddress='{controller['ipaddress']}' OR ipaddress_ipv6='{controller['ipaddress']}'"
                claship = Database().get_record(None, 'ipaddress', where)
                if claship:
                    status=False
                    ret_msg = f"Invalid request: Clashing ip address for controller {controller['hostname']} with existing ip address {controller['ipaddress']}"
                    return status, ret_msg
                row=None
                if Helper().check_if_ipv6(controller['ipaddress']):
                    row = Helper().make_rows({'ipaddress_ipv6': controller['ipaddress']})
                else:
                    row = Helper().make_rows({'ipaddress': controller['ipaddress']})
                where = [{"column": "id", "value": controller['id']}]
                status=Database().update('ipaddress', row, where)
                if not status:
                    status=False
                    ret_msg = f"Error updating ip address for controller {controller['hostname']}"
                    return status, ret_msg
                
            network_columns = Database().get_columns('network')
            column_check = Helper().compare_list(data, network_columns)
            if column_check:
                row = Helper().make_rows(data)
                if create:
                    Database().insert('network', row)
                    response = f'Network {name} created successfully'
                    status=True
                elif update:
                    dhcp_size, dhcp6_size = 0, 0
                    if redistribute_ipaddress is True:
                        if 'dhcp_range_begin' in data:
                            dhcp_size = Helper().get_ip_range_size(
                                data['dhcp_range_begin'],
                                data['dhcp_range_end']
                            )
                        if 'dhcp_range_begin_ipv6' in data:
                            dhcp6_size = Helper().get_ip_range_size(
                                data['dhcp_range_begin_ipv6'],
                                data['dhcp_range_end_ipv6']
                            )
                        nwk_size, nwk6_size, avail, avail6 = 0, 0, 0, 0
                        network_ipv6, subnet_ipv6 = None, None
                        network_ipv4, subnet_ipv4 = None, None
                        if 'network' in data:
                            network_ipv4 = data['network']
                            subnet_ipv4 = data['subnet']
                        elif db_data['network']:
                            network_ipv4 = db_data['network']
                            subnet_ipv4 = db_data['subnet']
                        if network_ipv4:
                            nwk_size = Helper().get_network_size(network_ipv4, subnet_ipv4)
                            avail = nwk_size - dhcp_size
                            self.logger.info(f"NETWORK {name} UPDATE. used_ips = {used_ips}, avail: {avail} = nwk_size {nwk_size} - dhcp_size {dhcp_size}")
                            if avail < used_ips:
                                response = f'The proposed network config allows for {nwk_size} ip '
                                response += f'addresses. DHCP range will occupy {dhcp_size} ip '
                                response += 'addresses. The request will not accomodate for the '
                                response += f'currently {used_ips} in use ip addresses'
                                status=False
                                return status, response
                        if 'network_ipv6' in data:
                            network_ipv6 = data['network_ipv6']
                            subnet_ipv6 = data['subnet_ipv6']
                        elif db_data['network_ipv6']:
                            network_ipv6 = db_data['network_ipv6']
                            subnet_ipv6 = db_data['subnet_ipv6']
                        if network_ipv6:
                            nwk6_size = Helper().get_network_size(network_ipv6, subnet_ipv6)
                            avail6 = nwk6_size - dhcp6_size
                            self.logger.info(f"NETWORK {name} UPDATE. used6_ips = {used6_ips}, avail6: {avail6} = nwk6_size {nwk6_size} - dhcp6_size {dhcp6_size}")
                            if avail6 < used6_ips:
                                response = f'The proposed IPv6 network config allows for {nwk6_size} ip '
                                response += f'addresses. DHCP range will occupy {dhcp6_size} ip '
                                response += 'addresses. The request will not accomodate for the '
                                response += f'currently {used6_ips} in use ip addresses'
                                status=False
                                return status, response

                    where = [{"column": "id", "value": networkid}]
                    Database().update('network', row, where)
                    # TWANNIE
                    if redistribute_ipaddress is True:
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
                    if clear_ipv4 or clear_ipv6:
                        entry_list = Database().get_record_join(
                            [
                                'ipaddress.id',
                                'ipaddress.tableref',
                                'ipaddress.tablerefid'
                            ],
                            ['ipaddress.networkid=network.id'],
                            [f"network.name='{data['name']}'"]
                        )
                        if entry_list:
                            clear_data = {}
                            if clear_ipv4:
                                clear_data['ipaddress'] = None
                            if clear_ipv6:
                                clear_data['ipaddress'] = None
                            row = Helper().make_rows(clear_data)
                            for entry in entry_list:
                                where = [{"column": "id", "value": entry['id']}]
                                Database().update('ipaddress', row, where)
                    response = f'Network {name} updated successfully'
                    status=True
                Service().queue('dns','restart')
                Service().queue('dhcp','restart')
                Service().queue('dhcp6','restart')
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
            controller = Database().get_record_join(
                ['controller.*'],
                ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                ['tableref="controller"','controller.beacon=1',f"network.name='{name}'"]
            )
            if not controller:
                Database().delete_row('network', [{"column": "name", "value": name}])
                data = {}
                data['shared'] = ""
                row = Helper().make_rows(data)
                where = [{"column": "shared", "value": name}]
                Database().update('network', row, where)
                Service().queue('dns','restart')
                Service().queue('dhcp','restart')
                Service().queue('dhcp6','restart')
                response = 'Network removed'
                status=True
            else:
                response = f'Network {name} cannot be removed because it is in use by controller'
                status=False
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
            avail = Helper().get_available_ip(network[0]['network'], network[0]['subnet'], ips, ping=True)
        if avail:
            response = {'config': {'network': {name: {'nextip': avail} } } }
            row = Helper().make_rows({'version': 'ipv4', 'ipaddress': avail, 'created': 'NOW'})
            status=Database().insert('reservedipaddress', row)
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
            else:
                response = 'All IP Address are free on Network {name}. None is Taken'
                status=False
        else:
            response = f'Network {name} not present in database'
            status=False
        return status, response

