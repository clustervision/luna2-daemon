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
Interface Class will make all operations on node and group interfaces.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from json import dumps
from concurrent.futures import ThreadPoolExecutor
from utils.database import Database
from utils.log import Log
from utils.config import Config
from utils.service import Service
from utils.queue import Queue
from utils.helper import Helper


class Interface():
    """
    This class is responsible for all operations on interface of node and group .
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_node_interface(self, name=None):
        """
        This method will return all the node interfaces in detailed format.
        """
        status=False
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                [
                    'network.name as network',
                    'nodeinterface.macaddress',
                    'nodeinterface.interface',
                    'ipaddress.ipaddress',
                    'nodeinterface.options'
                ],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            if node_interfaces:
                my_interface = []
                for interface in node_interfaces:
                    interface['options'] = interface['options'] or ""
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface
                self.logger.info(f'Returned node interface {name} details.')
                status=True
            else:
                self.logger.error(f'Node {name} dont have any interface.')
                response = f'Node {name} dont have any interface'
                status=False
        else:
            self.logger.error('No nodes available.')
            response = 'No nodes available'
            status=False
        return status, response


    def change_node_interface_by_name(self, name=None, request_data=None):
        """
        wrapper to call below function but gets nodeid first
        """
        status=False
        if request_data:
            if name in request_data['config']['node'] and 'interfaces' in request_data['config']['node'][name]:
                new_data = request_data['config']['node'][name]['interfaces']
                node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
                if node:
                    status, response = self.change_node_interface(node[0]['id'], new_data)
                else:
                    response = f'Node {name} is not available'
                    status=False
            else:
                response = 'Invalid request: interface not provided'
                status=False
        else:
            response = 'Invalid request: Did not receive Data'
            status=False
        return status, response


    def change_node_interface(self, nodeid=None, data=None):
        """
        This method will add or update the node interface.
        """
        status=False
        if data and nodeid:
            for interface in data:
                # Antoine
                interface_name = interface['interface']
                ipaddress, macaddress, network, options = None, None, None, None
                if 'macaddress' in interface.keys():
                    macaddress = interface['macaddress']
                if 'options' in interface.keys():
                    options = interface['options']
                if 'network' in interface.keys():
                    network = interface['network']
                result, message = Config().node_interface_config(
                    nodeid,
                    interface_name,
                    macaddress,
                    options
                )
                if result:
                    if network or ipaddress:
                        if not ipaddress:
                            ips = Config().get_all_occupied_ips_from_network(network)
                            where = f" WHERE `name` = '{network}'"
                            network_details = Database().get_record(None, 'network', where)
                            if network_details:
                                avail = Helper().get_available_ip(
                                    network_details[0]['network'],
                                    network_details[0]['subnet'],
                                    ips
                                )
                                if avail:
                                    ipaddress = avail
                        elif not network:
                            existing = Database().get_record_join(
                                ['ipaddress.ipaddress','network.name as networkname'],
                                [
                                    'nodeinterface.nodeid=node.id',  
                                    'ipaddress.tablerefid=nodeinterface.id',
                                    'network.id=ipaddress.networkid'
                                ],
                                [
                                    f"node.id='{nodeid}'",
                                    "ipaddress.tableref='nodeinterface'",
                                    f"nodeinterface.interface='{interface_name}'"
                                ]
                            )
                            if existing:
                                network = existing[0]['networkname']

                        result, message = Config().node_interface_ipaddress_config(
                            nodeid,
                            interface_name,
                            ipaddress,
                            network
                        )

                if result is False:
                    response = f'{message}'
                    status=False
                else:
                    response = 'Interface updated'
                    status=True
        else:
            response = 'Invalid request: did not receive Data'
            status=False
        return status, response


    def update_node_group_interface(self, nodeid=None, groupid=None, oldgroupid=None):
        """
        This function adds/updates group interfaces for one node
        Typically used when a node is changed, added or when a group has changed for a node
        If oldgroup id is provided we compare with what the old group has versus the node.
        It tries to figure out what needs to be added or removed for a node. pffffff......
        """
        if nodeid and groupid:
            # ----> GROUP interface. WIP. pending. should work but i keep it WIP
            # we fetch interfaces and ip-s separate as interfaces might not have IPs set in weird cases
            existing_if = Database().get_record(None, 'nodeinterface', f"WHERE nodeid={nodeid}")
            existing_ip = Database().get_record_join(
                ['nodeinterface.interface','ipaddress.*'],
                ['ipaddress.tablerefid=nodeinterface.id'],
                ["ipaddress.tableref='nodeinterface'",f"nodeinterface.nodeid={nodeid}"]
            )
            if_dict, ip_dict = None, None
            if existing_if:
                if_dict = Helper().convert_list_to_dict(existing_if, 'interface')
            if existing_ip:
                ip_dict = Helper().convert_list_to_dict(existing_ip, 'interface')
            if_old_group_dict = None
            if oldgroupid:
                old_group_interfaces = Database().get_record_join(
                    [
                        'groupinterface.interface',
                        'network.name as network',
                        'network.id as networkid',
                        'groupinterface.options'
                    ],
                    ['network.id=groupinterface.networkid'],
                    [f"groupinterface.groupid={oldgroupid}"]
                )
                if old_group_interfaces:
                    if_old_group_dict = Helper().convert_list_to_dict(old_group_interfaces, 'interface')
            group_interfaces = Database().get_record_join(
                [
                    'groupinterface.interface',
                    'network.name as network',
                    'network.id as networkid',
                    'groupinterface.options'
                ],
                ['network.id=groupinterface.networkid'],
                [f"groupinterface.groupid={groupid}"]
            )
            if group_interfaces:
                for group_interface in group_interfaces:
                    add_interface = True
                    # now we go into the rabbit hole. we figure if the node already has this interface
                    # confgured, with network and matching ip. if so, we leave it alone.
                    if if_dict and group_interface['interface'] in if_dict.keys():
                        # good, we already have an interface with that name
                        if ip_dict and group_interface['interface'] in ip_dict.keys():
                            # and it already has an IP
                            if 'networkid' in ip_dict[group_interface['interface']]:
                                if group_interface['networkid'] == ip_dict[group_interface['interface']]['networkid']:
                                    if ip_dict[group_interface['interface']]['ipaddress']:
                                        # we already have such interface with matching config. we do nothing
                                        add_interface = False
                                        del if_dict[group_interface['interface']]
                    if add_interface is True:
                        result, message = Config().node_interface_config(
                            nodeid,
                            group_interface['interface'],
                            None,
                            group_interface['options']
                        )
                        if result:
                            ips = Config().get_all_occupied_ips_from_network(
                                group_interface['network']
                            )
                            where = f" WHERE `name` = \"{group_interface['network']}\""
                            network = Database().get_record(None, 'network', where)
                            if network:
                                avail = Helper().get_available_ip(
                                    network[0]['network'],
                                    network[0]['subnet'],
                                    ips
                                )
                                if avail:
                                    result, message = Config().node_interface_ipaddress_config(
                                        nodeid,
                                        group_interface['interface'],
                                        avail,
                                        group_interface['network']
                                    )
                                    if result:
                                        if if_dict and group_interface['interface'] in if_dict.keys():
                                            del if_dict[group_interface['interface']]
                                # we do not ping nodes as it will take time if we add bulk
                                # nodes, it'll take 1s per node. code block removal pending?
                                # ret=0
                                # max=5
                                # we try to ping for X ips, if none of these are free,
                                # something else is going on (read: rogue devices)....
                                # while(max>0 and ret!=1):
                                #     avail = Helper().get_available_ip(
                                #       network[0]['network'],
                                #       network[0]['subnet'],
                                #       ips
                                #     )
                                #     ips.append(avail)
                                #     command = f"ping -w1 -c1 {avail}"
                                #     output, ret = Helper().runcommand(command, True, 3)
                                #     max-= 1

            if if_dict and if_old_group_dict:
                for interface in if_dict.keys():
                    # should we really police everything? what if a node has something else for a bootif?
                    # We leave it up to the intelligence of the admins and we commented out the below section
                    #if if_dict[interface]['interface'] == "BOOTIF":
                    #    continue
                    if if_dict[interface]['interface'] in if_old_group_dict.keys():
                        # This means that the interface existed in the previous group, therefor we 
                        # conclude to remove it. Seems legit no?
                        self.delete_node_interface(nodeid=nodeid, interface=if_dict[interface]['interface'])
        else:
            return False, "nodeid and/or group not defined"
        return True, "success"


    def get_node_interface(self, name=None, interface=None):
        """
        This method will provide a node interface.
        """
        status=False
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                [
                    'network.name as network',
                    'nodeinterface.macaddress',
                    'nodeinterface.interface',
                    'ipaddress.ipaddress',
                    'nodeinterface.options'
                ],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{nodeid}'",
                    f"nodeinterface.interface='{interface}'"
                ]
            )
            if node_interfaces:
                my_interface = []
                for interface in node_interfaces:
                    interface['options'] = interface['options'] or ""
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface

                self.logger.info(f'Returned node interface {name} details.')
                status=True
            else:
                self.logger.error(f'Node {name} does not have {interface} interface.')
                response = f'Node {name} does not have {interface} interface'
                status=False
        else:
            self.logger.error('Node is not available.')
            response = 'Node is not available'
        return status, response


    def delete_node_interface_by_name(self, name=None, interface=None):
        """
        This method will delete a node's interface.
        same as function below but this one can be called by node name
        """
        status=False
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            status, response = self.delete_node_interface(node[0]['name'], interface)
        else:
            response = f'Node {name} not present in database'
            status=False
        return status, response


    def delete_node_interface(self, nodeid=None, interface=None):
        """
        This method will delete a node's interface.
        """
        status=False
        if nodeid:
            where = f' WHERE `interface` = "{interface}" AND `nodeid` = "{nodeid}"'
            node_interface = Database().get_record_join(
                ['nodeinterface.id as ifid', 'ipaddress.id as ipid'],
                ['ipaddress.tablerefid=nodeinterface.id'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{nodeid}'",
                    f"nodeinterface.interface='{interface}'"
                ]
            )
            if node_interface:
                where = [{"column": "id", "value": node_interface[0]['ipid']}]
                Database().delete_row('ipaddress', where)
                where = [{"column": "id", "value": node_interface[0]['ifid']}]
                Database().delete_row('nodeinterface', where)
                # disabled the next two for testing. Antoine aug 8 2023
                #Service().queue('dhcp','restart')
                #Service().queue('dns','restart')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue(
                    'dhcp:restart',
                    'housekeeper',
                    '__node_interface_delete__'
                )
                Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_interface_delete__')
                response = f'Interface {interface} removed successfully'
                status=True
            else:
                response = f'Interface {interface} not present in database'
                status=False
        else:
            response = 'Invalid request: did not receive Data'
            status=False
        return status, response


    def get_all_group_interface(self, name=None):
        """
        This method will return all the group interfaces in detailed format for a desired group.
        """
        status=False
        groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if groups:
            response = {'config': {'group': {name: {'interfaces': [] } } } }
            for group in groups:
                groupname = group['name']
                groupid = group['id']
                group_interface = Database().get_record_join(
                    ['groupinterface.interface','groupinterface.options','network.name as network'],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{groupid}'"]
                )
                if group_interface:
                    group_interfaces = []
                    for interface in group_interface:
                        group_interfaces.append(interface)
                    response['config']['group'][groupname]['interfaces'] = group_interfaces
                else:
                    self.logger.error(f'Group {name} does not have any interface.')
                    response = f'Group {name} does not have any interface'
                    status=False
            self.logger.info(f'Returned group {name} with details.')
            status=True
        else:
            self.logger.error('No group is available.')
            response = 'No group is available'
            status=False
        return status, response


    def change_group_interface(self, name=None, request_data=None):
        """
        This method will add or update the group interface.
        """
        status=False
        response="Internal error"
        if request_data:
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                group_id = group[0]['id']
                if 'interfaces' in request_data['config']['group'][name]:
                    for ifx in request_data['config']['group'][name]['interfaces']:
                        if (not 'network' in ifx) or (not 'interface' in ifx):
                            status=False
                            return status, 'Invalid request: Interface and/or network not specified'
                        network = Database().id_by_name('network', ifx['network'])
                        if network is None:
                            status=False
                            return status, f'Invalid request: Network {network} does not exist'
                        else:
                            ifx['networkid'] = network
                            ifx['groupid'] = group_id
                            del ifx['network']
                        interface = ifx['interface']
                        grp_clause = f'groupid = "{group_id}"'
                        network_clause = f'networkid = "{network}"'
                        interface_clause = f'interface = "{interface}"'
                        where = f' WHERE {grp_clause} AND {network_clause} AND {interface_clause}'
                        interface_check = Database().get_record(None, 'groupinterface', where)
                        if not interface_check:
                            row = Helper().make_rows(ifx)
                            Database().insert('groupinterface', row)
                        response = 'Interface updated'
                        status=True
                        # below section takes care(in the background), adding/renaming/deleting.
                        # for adding next free ip-s will be selected. time consuming
                        # therefor background
                        queue_id, _ = Queue().add_task_to_queue(
                            f'add_interface_to_group_nodes:{name}:{interface}',
                            'group_interface'
                        )
                        next_id = Queue().next_task_in_queue('group_interface')
                        if queue_id == next_id:
                            executor = ThreadPoolExecutor(max_workers=1)
                            executor.submit(Config().update_interface_on_group_nodes,name)
                            executor.shutdown(wait=False)
                            # Config().update_interface_on_group_nodes(name)
                else:
                    self.logger.error('interface not provided.')
                    response = 'Invalid request: interface not provided'
                    status=False
            else:
                self.logger.error('No group is available.')
                response = 'No group is available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def get_group_interface(self, name=None, interface=None):
        """
        This method will provide a group interface.
        """
        status=False
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            response = {'config': {'group': {name: {'interfaces': [] } } } }
            groupid = group[0]['id']
            grp_interfaces = Database().get_record_join(
                ['groupinterface.interface', 'groupinterface.options', 'network.name as network'],
                ['network.id=groupinterface.networkid'],
                [f"groupid = '{groupid}'", f"groupinterface.interface='{interface}'"]
            )
            if grp_interfaces:
                my_interface = []
                for interface in grp_interfaces:
                    interface['options']=interface['options'] or ""
                    my_interface.append(interface)
                    response['config']['group'][name]['interfaces'] = my_interface

                self.logger.info(f'Returned group {name} with details.')
                status=True
            else:
                self.logger.error(f'Group {name} does not have {interface} interface.')
                response = f'Group {name} does not have {interface} interface'
                status=True
        else:
            self.logger.error('Group is not available.')
            response = 'Group is not available'
            status=False
        return status, response


    def delete_group_interface(self, name=None, interface=None):
        """
        This method will delete a group interface.
        """
        response="Internal error"
        status=False
        group = Database().get_record(None, 'group', f' WHERE `name` = "{name}"')
        if group:
            groupid = group[0]['id']
            where = f' WHERE `interface` = "{interface}" AND `groupid` = "{groupid}"'
            group_interface = Database().get_record(None, 'groupinterface', where)
            if group_interface:
                where = [{"column": "id", "value": group_interface[0]['id']}]
                Database().delete_row('groupinterface', where)
                # below section takes care (in the background), adding/renaming/deleting.
                # for adding next free ip-s will be selected. time consuming therefor background
                queue_id, _ = Queue().add_task_to_queue(
                    f'delete_interface_from_group_nodes:{name}:{interface}',
                    'group_interface'
                )
                next_id = Queue().next_task_in_queue('group_interface')
                if queue_id == next_id:
                    # executor = ThreadPoolExecutor(max_workers=1)
                    # executor.submit(Config().update_interface_on_group_nodes,name)
                    # executor.shutdown(wait=False)
                    Config().update_interface_on_group_nodes(name)
                response = f'Group {name} interface {interface} removed'
                status=True
            else:
                response = f'Group {name} interface {interface} not present in database'
                status=False
        else:
            response = f'Group {name} not present in database'
            status=False
        return status, response

