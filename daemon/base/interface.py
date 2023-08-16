#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


    def change_node_interface(self, name=None, request_data=None):
        """
        This method will add or update the node interface.
        """
        status=False
        if request_data:
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']

                if 'interfaces' in request_data['config']['node'][name]:
                    for interface in request_data['config']['node'][name]['interfaces']:
                        # Antoine
                        interface_name = interface['interface']
                        macaddress, network, options = None, None, None
                        if 'macaddress' in interface.keys():
                            macaddress = interface['macaddress']
                        if 'options' in interface.keys():
                            options = interface['options']
                        result, message = Config().node_interface_config(
                            nodeid,
                            interface_name,
                            macaddress,
                            options
                        )
                        if result and 'ipaddress' in interface.keys():
                            ipaddress=interface['ipaddress']
                            if 'network' in interface.keys():
                                network=interface['network']
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
                            # disabled the next two for testing. Antoine aug 8 2023
                            #Service().queue('dhcp', 'restart')
                            #Service().queue('dns', 'restart')
                            # below might look as redundant but is added to prevent a possible
                            # race condition when many nodes are added in a loop.
                            # the below tasks ensures that even the last node will be included
                            # in dhcp/dns
                            Queue().add_task_to_queue(
                                'dhcp:restart',
                                'housekeeper',
                                '__node_interface_post__'
                            )
                            Queue().add_task_to_queue(
                                'dns:restart',
                                'housekeeper',
                                '__node_interface_post__'
                            )
                            response = 'Interface updated'
                            status=True
                else:
                    self.logger.error(f'Interface for Node {name} not provided.')
                    response = 'Invalid request: interface not provided'
                    status=False
            else:
                self.logger.error(f'Node {name} is not available.')
                response = f'Node {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not receive Data'
            status=False
        return status, response


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


    def delete_node_interface(self, name=None, interface=None):
        """
        This method will delete a node.
        """
        status=False
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            nodeid = node[0]['id']
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
                response = f'Node {name} interface {interface} removed successfully'
                status=True
            else:
                response = f'Node {name} interface {interface} not present in database'
                status=False
        else:
            response = f'Node {name} not present in database'
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
            f'Group {name} not present in database'
            status=False
        return status, response
