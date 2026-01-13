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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

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
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                [
                    'nodeinterface.interface',
                    'ipaddress.ipaddress',
                    'ipaddress.ipaddress_ipv6',
                    'ipaddress.dhcp',
                    'nodeinterface.macaddress',
                    'network.name as network',
                    'nodeinterface.mtu',
                    'nodeinterface.vlanid',
                    'nodeinterface.vlan_parent',
                    'nodeinterface.bond_mode',
                    'nodeinterface.bond_slaves',
                    'nodeinterface.options',
                    'network.dhcp as networkdhcp',
                    'network.dhcp_nodes_in_pool'
                ],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            if node_interfaces:
                my_interface = []
                for interface in node_interfaces:
                    interface['dhcp'] = Helper().make_bool(interface['dhcp'])
                    for item in ['mtu','options','vlanid','vlan_parent','bond_mode','bond_slaves','ipaddress','ipaddress_ipv6']:
                        if not interface[item]:
                            del interface[item]
                    if 'vlan_parent' in interface and 'vlanid' not in interface:
                        del interface['vlan_parent']
                    if interface['dhcp_nodes_in_pool'] and interface['networkdhcp'] and interface['dhcp']:
                        if 'ipaddress_ipv6' in interface:
                            del interface['ipaddress_ipv6']
                            interface['comment'] = 'ipaddress configured but ignored using dhcp and dhcp_nodes_in_pool set'
                        if 'ipaddress' in interface:
                            del interface['ipaddress']
                            interface['comment'] = 'ipaddress configured but ignored using dhcp and dhcp_nodes_in_pool set'
                    if not interface['dhcp']:
                        del interface['dhcp']
                    elif not interface['networkdhcp']:
                        interface['comment'] = 'dhcp configured but ignored with network having dhcp disabled'
                    del interface['dhcp_nodes_in_pool']
                    del interface['networkdhcp']
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface
                status=True
            else:
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
                node = Database().get_record(table='node', where=f'name = "{name}"')
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
                ipaddress, macaddress, network, clear_ip = None, None, None, False
                options, vlanid, force, dhcp, set_dhcp = None, None, False, None, False
                vlan_parent, bond_mode, bond_slaves, mtu = None, None, None, None
                if 'macaddress' in interface.keys():
                    macaddress = interface['macaddress']
                if 'mtu' in interface.keys():
                    mtu = interface['mtu']
                if 'options' in interface.keys():
                    options = interface['options']
                if 'vlanid' in interface.keys():
                    vlanid = interface['vlanid']
                if 'vlan_parent' in interface.keys():
                    vlan_parent = interface['vlan_parent']
                if 'bond_mode' in interface.keys():
                    bond_mode = interface['bond_mode']
                if 'bond_slaves' in interface.keys():
                    bond_slaves = interface['bond_slaves']
                if 'network' in interface.keys():
                    network = interface['network']
                if 'ipaddress' in interface.keys():
                    ipaddress = interface['ipaddress']
                if 'force' in interface.keys():
                    force = interface['force']
                if 'dhcp' in interface.keys():
                    dhcp = interface['dhcp']
                    set_dhcp = True
                if ipaddress == '': # clearing the config!
                    clear_ip = True
                   
                result, message = Config().node_interface_config(
                    nodeid=nodeid, interface_name=interface_name,
                    macaddress=macaddress, mtu=mtu,
                    vlanid=vlanid, vlan_parent=vlan_parent,
                    bond_mode=bond_mode, bond_slaves=bond_slaves,
                    options=options
                )
                if result:
                    existing = Database().get_record_join(
                        [
                            'ipaddress.ipaddress','ipaddress.ipaddress_ipv6',
                            'ipaddress.dhcp', 'network.name as networkname',
                            'network.dhcp_nodes_in_pool', 'network.dhcp as networkdhcp'
                        ],
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
                    if network or ipaddress or set_dhcp or clear_ip:
                        ipaddress_ipv6 = None
                        clear_ipv4, clear_ipv6 = False, False
                        nodes_in_pool = False # only used as confirmation variable
                        if not ipaddress:
                            if existing:
                                if set_dhcp and dhcp and not network: # first set see if we just toggle
                                    network = existing[0]['networkname']
                                if network == existing[0]['networkname']:
                                    ipaddress = existing[0]['ipaddress']
                                    if existing[0]['ipaddress_ipv6'] and not ipaddress:
                                        ipaddress = existing[0]['ipaddress_ipv6']
                            if (not clear_ip) and (not ipaddress):
                                if (not network) and existing:
                                    network = existing[0]['networkname']
                                if network:
                                    where = f"name = '{network}'"
                                    network_details = Database().get_record(table='network', where=where)
                                    if network_details:
                                        if network_details[0]['dhcp'] and network_details[0]['dhcp_nodes_in_pool']:
                                            nodes_in_pool = True
                                            clear_ip = True
                                        else:
                                            if network_details[0]['network']:
                                                ips = Config().get_all_occupied_ips_from_network(network)
                                                avail = Helper().get_available_ip(
                                                    network_details[0]['network'],
                                                    network_details[0]['subnet'],
                                                    ips
                                                )
                                                if avail:
                                                    ipaddress = avail
                                            else: # when we no longer have ipv4 for the new network
                                                clear_ipv4 = True
                                            if network_details[0]['network_ipv6']:
                                                ips = Config().get_all_occupied_ips_from_network(network,'ipv6')
                                                avail = Helper().get_available_ip(
                                                    network_details[0]['network_ipv6'],
                                                    network_details[0]['subnet_ipv6'],
                                                    ips
                                                )
                                                if avail:
                                                    ipaddress_ipv6 = avail
                                            else: # when we no longer have ipv6 for the new network
                                                clear_ipv6 = True
                                    else:
                                        message=f"Invalid request: network {network} does not exist"
                                        return False, message
                        elif not network:
                            if existing:
                                network = existing[0]['networkname']

                        if ipaddress_ipv6 and not ipaddress:
                            ipaddress = ipaddress_ipv6
                            ipaddress_ipv6 = None

                        result = True
                        # ------------------ prevent having an unconfigured interface ---------------------
                        if set_dhcp and not dhcp:
                            if existing:
                                if clear_ip and not existing[0]['dhcp']:
                                    result=False
                                    message="Invalid request: dhcp not set while clearing ip addresses"
                                elif (not existing[0]['ipaddress']) or (not existing[0]['ipaddress_ipv6']):
                                    if (not ipaddress) and (not ipaddress_ipv6):
                                        result=False
                                        message="Invalid request: dhcp unset while not having configured ip addresses"
                                        if nodes_in_pool:
                                            message+=". "
                                            message+=f"network {existing[0]['networkname']} has dhcp_nodes_in_pool configured"
                                            message+=". "
                                            message+="automatic ip address assignment not available"
                            else:
                                if (not ipaddress) and (not ipaddress_ipv6):
                                    result=False
                                    message="Invalid request: dhcp unset while not having configured ip addresses"
                                    if nodes_in_pool:
                                        message+=". "
                                        message+="the network has dhcp_nodes_in_pool configured"
                                        message+=". "
                                        message+="automatic ip address assignment not available"
                        elif nodes_in_pool: # and (not existing): # <- not sure if we need to check if network already exists
                            # the interface itself exists, but there is not ipaddress config.
                            # can we safely create the interface? We inherit?                            
                            set_dhcp = True
                            dhcp = True
                        # ---------------------------------------------------------------------------------

                        if result and clear_ip:
                            self.logger.debug(f"------------ clearing all IPs --------------")
                            for ipversion in ['ipv4','ipv6']:
                                result, message = Config().node_interface_clear_ipaddress(
                                    nodeid,
                                    interface_name,
                                    ipversion=ipversion
                                )
                                self.logger.info(f"result: [{result}]")

                        if result and clear_ipv4:
                            self.logger.debug(f"------------ clearing IPv4 --------------")
                            result, message = Config().node_interface_clear_ipaddress(
                                    nodeid,
                                    interface_name,
                                    ipversion='ipv4'
                                )

                        if result and clear_ipv6:
                            self.logger.debug(f"------------ clearing IPv6 --------------")
                            result, message = Config().node_interface_clear_ipaddress(
                                    nodeid,
                                    interface_name,
                                    ipversion='ipv6'
                                )

                        if result and set_dhcp:
                            self.logger.debug(f"------------ set dhcp --------------")
                            result, message = Config().node_interface_dhcp_config(
                                nodeid,
                                interface_name,
                                dhcp,
                                network
                            )

                        if ipaddress or ipaddress_ipv6:
                            if result and ipaddress:
                                self.logger.debug(f"------------ IPv4 --------------")
                                result, message = Config().node_interface_ipaddress_config(
                                    nodeid,
                                    interface_name,
                                    ipaddress,
                                    network,
                                    force
                                )
                            if result and ipaddress_ipv6:
                                self.logger.debug(f"------------ IPv6 --------------")
                                result, message = Config().node_interface_ipaddress_config(
                                    nodeid,
                                    interface_name,
                                    ipaddress_ipv6,
                                    network,
                                    force
                                )
                    elif ((macaddress is None) and (options is None) and (vlan_parent is None) and (vlanid is None) and
                        (bond_mode is None) and (bond_slaves is None) and (mtu is None)):
                            # this means we just made an empty interface. a no no - Antoine
                            # beware that we _have_ to test for None as 
                            #    clearing parameters by "" is caught by 'not maccaddress'
                        result=False
                        message="Invalid request: missing minimal parameters"
                    elif not existing:
                        result=False
                        message="Invalid request: missing minimal parameters creating new interface"
                    if result is False and not existing:
                        # roll back
                        self.delete_node_interface(nodeid=nodeid, interface=interface_name)

                if result is False:
                    response = f'{message} for {interface_name}'
                    status=False
                    break
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
            existing_if = Database().get_record(table='nodeinterface', where=f"nodeid={nodeid}")
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
                        'groupinterface.mtu',
                        'groupinterface.vlanid',
                        'groupinterface.vlan_parent',
                        'groupinterface.bond_mode',
                        'groupinterface.bond_slaves',
                        'groupinterface.options',
                        'groupinterface.dhcp'
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
                    'groupinterface.mtu',
                    'groupinterface.vlanid',
                    'groupinterface.vlan_parent',
                    'groupinterface.bond_mode',
                    'groupinterface.bond_slaves',
                    'groupinterface.options',
                    'groupinterface.dhcp'
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
                                        self.logger.info(f"not changing existing interface {group_interface['interface']} for node with id {nodeid}")
                    if add_interface is True:
                        result, message = Config().node_interface_config(
                            nodeid=nodeid,
                            interface_name=group_interface['interface'],
                            macaddress=None,
                            mtu=group_interface['mtu'],
                            vlanid=group_interface['vlanid'],
                            vlan_parent=group_interface['vlan_parent'],
                            bond_mode=group_interface['bond_mode'],
                            bond_slaves=group_interface['bond_slaves'],
                            options=group_interface['options']
                        )
                        if result:
                            where = f"name = \"{group_interface['network']}\""
                            network = Database().get_record(table='network', where=where)
                            if network:
                                if network[0]['network'] and not network[0]['dhcp_nodes_in_pool']:
                                    ips = Config().get_all_occupied_ips_from_network(
                                        group_interface['network']
                                    )
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
                                else:
                                    result, message = Config().node_interface_clear_ipaddress(
                                        nodeid,
                                        group_interface['interface'],
                                        'ipv4'
                                    )
                                if network[0]['network_ipv6'] and not network[0]['dhcp_nodes_in_pool']:
                                    ips = Config().get_all_occupied_ips_from_network(
                                        group_interface['network'], 'ipv6'
                                    )
                                    avail = Helper().get_available_ip(
                                        network[0]['network_ipv6'],
                                        network[0]['subnet_ipv6'],
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
                                else:
                                    result, message = Config().node_interface_clear_ipaddress(
                                        nodeid,
                                        group_interface['interface'],
                                        'ipv6'
                                    )
                            if 'dhcp' in group_interface:
                                result, message = Config().node_interface_dhcp_config(
                                    nodeid,
                                    group_interface['interface'],
                                    group_interface['dhcp'],
                                    group_interface['network']
                                )
                                if result:
                                    if if_dict and group_interface['interface'] in if_dict.keys():
                                        del if_dict[group_interface['interface']]

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
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                [
                    'nodeinterface.interface',
                    'ipaddress.ipaddress',
                    'ipaddress.ipaddress_ipv6',
                    'ipaddress.dhcp',
                    'nodeinterface.macaddress',
                    'network.name as network',
                    'nodeinterface.vlanid',
                    'nodeinterface.vlan_parent',
                    'nodeinterface.bond_mode',
                    'nodeinterface.bond_slaves',
                    'nodeinterface.options',
                    'network.dhcp as networkdhcp',
                    'network.dhcp_nodes_in_pool'
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
                    interface['dhcp'] = Helper().make_bool(interface['dhcp'])
                    for item in ['options','vlanid','vlan_parent','bond_mode','bond_slaves','ipaddress','ipaddress_ipv6']:
                        if not interface[item]:
                            del interface[item]
                    if 'vlan_parent' in interface and 'vlanid' not in interface:
                        del interface['vlan_parent']
                    if interface['dhcp_nodes_in_pool'] and interface['networkdhcp'] and interface['dhcp']:
                        if 'ipaddress_ipv6' in interface:
                            del interface['ipaddress_ipv6']
                            interface['comment'] = 'ipaddress configured but ignored using dhcp and dhcp_nodes_in_pool set'
                        if 'ipaddress' in interface:
                            del interface['ipaddress']
                            interface['comment'] = 'ipaddress configured but ignored using dhcp and dhcp_nodes_in_pool set'
                    if not interface['dhcp']:
                        del interface['dhcp']
                    elif not interface['networkdhcp']:
                        interface['comment'] = 'dhcp configured but ignored with network having dhcp disabled'
                    del interface['dhcp_nodes_in_pool']
                    del interface['networkdhcp']
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface
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
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            status, response = self.delete_node_interface(node[0]['id'], interface)
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
                #Service().queue('dns','reload')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue(task='restart', param='dhcp', 
                                          subsystem='housekeeper', request_id='__node_interface_delete__')
                Queue().add_task_to_queue(task='restart', param='dhcp6', 
                                          subsystem='housekeeper', request_id='__node_interface_delete__')
                Queue().add_task_to_queue(task='reload', param='dns', 
                                          subsystem='housekeeper', request_id='__node_interface_delete__')
                response = f'Interface {interface} removed successfully'
                status=True
            else:
                where = f'interface = "{interface}" AND `nodeid` = "{nodeid}"'
                node_interface = Database().get_record(table='nodeinterface', where=where)
                if node_interface:
                    where = [{"column": "id", "value": node_interface[0]['id']}]
                    Database().delete_row('nodeinterface', where)
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
        groups = Database().get_record(table='group', where=f'name = "{name}"')
        if groups:
            response = {'config': {'group': {name: {'interfaces': [] } } } }
            for group in groups:
                groupname = group['name']
                groupid = group['id']
                group_interface = Database().get_record_join(
                    [
                        'groupinterface.interface',
                        'network.name as network',
                        'groupinterface.vlanid',
                        'groupinterface.vlan_parent',
                        'groupinterface.bond_mode',
                        'groupinterface.bond_slaves',
                        'groupinterface.options',
                        'groupinterface.dhcp',
                        'network.dhcp as networkdhcp'
                    ],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{groupid}'"]
                )
                if group_interface:
                    group_interfaces = []
                    for interface in group_interface:
                        for item in ['options','vlanid','vlan_parent','bond_mode','bond_slaves']:
                            if not interface[item]:
                                del interface[item]
                        interface['dhcp'] = Helper().make_bool(interface['dhcp']) or False
                        if not interface['dhcp']:
                            del interface['dhcp']
                        elif not interface['networkdhcp']:
                            interface['comment'] = 'dhcp configured but ignored with network having dhcp disabled'
                        del interface['networkdhcp']
                        group_interfaces.append(interface)
                    response['config']['group'][groupname]['interfaces'] = group_interfaces
                else:
                    self.logger.error(f'Group {name} does not have any interface.')
                    response = f'Group {name} does not have any interface'
                    status=False
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
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if group:
                group_id = group[0]['id']
                if 'interfaces' in request_data['config']['group'][name]:
                    for ifx in request_data['config']['group'][name]['interfaces']:
                        if not 'interface' in ifx:
                            status=False
                            return status, 'Invalid request: interface name is required for this operation'
                        interface_name = ifx['interface']

                        where_interface = f'groupid = "{group_id}" AND interface = "{interface_name}"'
                        check_interface = Database().get_record(table='groupinterface', where=where_interface)

                        network, bond_mode, bond_slaves, mtu = None, None, None, None
                        vlanid, vlan_parent, dhcp, options = None, None, None, None
                        if 'network' in ifx:
                            network = ifx['network']
                        if 'mtu' in ifx:
                            mtu = ifx['mtu']
                        if 'bond_mode' in ifx:
                            bond_mode = ifx['bond_mode']
                        if 'bond_slaves' in ifx:
                            bond_slaves  = ifx['bond_slaves']
                        if 'vlanid' in ifx:
                            vlanid = ifx['vlanid']
                        if 'vlan_parent' in ifx:
                            vlan_parent = ifx['vlan_parent']
                        if 'dhcp' in ifx:
                            dhcp = ifx['dhcp']
                        if 'options' in ifx:
                            options = ifx['options']

                        result, response = Config().group_interface_config(groupid=group_id,
                                                                interface_name=interface_name,
                                                                network=network, mtu=mtu, vlanid=vlanid,
                                                                vlan_parent=vlan_parent, bond_mode=bond_mode,
                                                                bond_slaves=bond_slaves, dhcp=dhcp,
                                                                options=options)

                        # below section takes care(in the background) the adding/renaming/deleting.
                        # for adding next free ip-s will be selected. time consuming there for
                        # background
                        if result:
                            status = True
                            queue_id = None
                            if check_interface:
                                response = 'Interface updated'
                                queue_id, _ = Queue().add_task_to_queue(
                                    task='update_interface_for_group_nodes',
                                    param=f'{name}:{interface_name}',
                                    subsystem='group_interface'
                                )
                            else:
                                response = 'Interface created'
                                queue_id, _ = Queue().add_task_to_queue(
                                    task='add_interface_to_group_nodes',
                                    param=f'{name}:{interface_name}',
                                    subsystem='group_interface'
                                )

                            next_id = Queue().next_task_in_queue('group_interface')
                            if queue_id == next_id:
                                executor = ThreadPoolExecutor(max_workers=1)
                                executor.submit(Config().update_interface_on_group_nodes,name)
                                executor.shutdown(wait=False)
                                # Config().update_interface_on_group_nodes(name)
                        else:
                            status = False
                            return False, response
                else:
                    self.logger.error('interface not provided.')
                    response = 'Invalid request: interface not provided'
                    status=False
            else:
                response = f'group {name} not available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def get_group_interface(self, name=None, interface=None):
        """
        This method will provide detailed interface info for a group.
        """
        status=False
        group = Database().get_record(table='group', where=f'name = "{name}"')
        if group:
            response = {'config': {'group': {name: {'interfaces': [] } } } }
            groupid = group[0]['id']
            grp_interfaces = Database().get_record_join(
                [
                    'groupinterface.interface',
                    'network.name as network',
                    'groupinterface.vlanid',
                    'groupinterface.vlan_parent',
                    'groupinterface.bond_mode',
                    'groupinterface.bond_slaves',
                    'groupinterface.options',
                    'groupinterface.dhcp',
                    'network.dhcp as networkdhcp'
                ],
                ['network.id=groupinterface.networkid'],
                [f"groupid = '{groupid}'", f"groupinterface.interface='{interface}'"]
            )
            if grp_interfaces:
                my_interface = []
                for interface in grp_interfaces:
                    for item in ['options','vlanid','vlan_parent','bond_mode','bond_slaves']:
                        if not interface[item]:
                            del interface[item]
                    interface['dhcp'] = Helper().make_bool(interface['dhcp']) or False
                    if not interface['dhcp']:
                        del interface['dhcp']
                    elif not interface['networkdhcp']:
                        interface['comment'] = 'dhcp configured but ignored with network having dhcp disabled'
                    del interface['networkdhcp']
                    my_interface.append(interface)
                    response['config']['group'][name]['interfaces'] = my_interface
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
        group = Database().get_record(table='group', where=f'name = "{name}"')
        if group:
            groupid = group[0]['id']
            where = f'interface = "{interface}" AND `groupid` = "{groupid}"'
            group_interface = Database().get_record(table='groupinterface', where=where)
            if group_interface:
                where = [{"column": "id", "value": group_interface[0]['id']}]
                Database().delete_row('groupinterface', where)
                # below section takes care (in the background), adding/renaming/deleting.
                # for adding next free ip-s will be selected. time consuming therefor background
                queue_id, _ = Queue().add_task_to_queue(
                    task='delete_interface_from_group_nodes',
                    param=f'{name}:{interface}',
                    subsystem='group_interface'
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
