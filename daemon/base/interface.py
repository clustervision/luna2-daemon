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
        """This method will return all the node interfaces in detailed format."""
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                ['network.name as network', 'nodeinterface.macaddress', 'nodeinterface.interface', 'ipaddress.ipaddress', 'nodeinterface.options'],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            if node_interfaces:
                my_interface = []
                for interface in node_interfaces:
                    interface['options'] = interface['options'] or ""
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface
                self.logger.info(f'Returned group {name} with details.')
                access_code = 200
            else:
                self.logger.error(f'Node {name} dont have any interface.')
                response = {'message': f'Node {name} dont have any interface'}
                access_code = 404
        else:
            self.logger.error('No nodes are available.')
            response = {'message': 'No nodes are available'}
            access_code = 404
        return dumps(response), access_code


    def change_node_interface(self, name=None, http_request=None):
        """This method will add or update the node interface."""
        request_data = http_request.data
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
                        result, message = Config().node_interface_config(nodeid, interface_name, macaddress, options)
                        if result and 'ipaddress' in interface.keys():
                            ipaddress=interface['ipaddress']
                            if 'network' in interface.keys():
                                network=interface['network']
                            result, message = Config().node_interface_ipaddress_config(nodeid, interface_name, ipaddress, network)

                        if result is False:
                            response = {'message': f'{message}'}
                            access_code = 404
                        else:
                            Service().queue('dhcp','restart')
                            Service().queue('dns','restart')
                            # below might look as redundant but is added to prevent a possible
                            # race condition when many nodes are added in a loop.
                            # the below tasks ensures that even the last node will be included
                            # in dhcp/dns
                            Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_interface_post__')
                            Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_interface_post__')
                            response = {'message': 'Interface updated'}
                            access_code = 204
                else:
                    self.logger.error(f'Interface for Node {name} not provided.')
                    response = {'message': 'interface not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Node {name} is not available.')
                response = {'message': f'Node {name} is not available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received Data'}
            access_code = 400
        return dumps(response), access_code


    def get_node_interface(self, name=None, interface=None):
        """This method will provide a node interface."""
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            response = {'config': {'node': {name: {'interfaces': [] } } } }
            nodeid = node[0]['id']
            node_interfaces = Database().get_record_join(
                ['network.name as network', 'nodeinterface.macaddress', 'nodeinterface.interface', 'ipaddress.ipaddress', 'nodeinterface.options'],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'", f"nodeinterface.interface='{interface}'"]
            )
            if node_interfaces:
                my_interface = []
                for interface in node_interfaces:
                    interface['options'] = interface['options'] or ""
                    my_interface.append(interface)
                    response['config']['node'][name]['interfaces'] = my_interface

                self.logger.info(f'Returned group {name} with details.')
                access_code = 200
            else:
                self.logger.error(f'Node {name} does not have {interface} interface.')
                response = {'message': f'Node {name} does not have {interface} interface'}
                access_code = 404
        else:
            self.logger.error('Node is not available.')
            response = {'message': 'Node is not available'}
            access_code = 404
        return dumps(response), access_code


    def delete_node_interface(self, name=None, interface=None):
        """This method will delete a node."""
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            nodeid = node[0]['id']
            where = f' WHERE `interface` = "{interface}" AND `nodeid` = "{nodeid}"'
            node_interface = Database().get_record_join(
                ['nodeinterface.id as ifid', 'ipaddress.id as ipid'],
                ['ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'", f"nodeinterface.interface='{interface}'"]
            )
            if node_interface:
                where = [{"column": "id", "value": node_interface[0]['ipid']}]
                Database().delete_row('ipaddress', where)
                where = [{"column": "id", "value": node_interface[0]['ifid']}]
                Database().delete_row('nodeinterface', where)
                Service().queue('dhcp','restart')
                Service().queue('dns','restart')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_interface_delete__')
                Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_interface_delete__')
                response = {'message': f'Node {name} interface {interface} removed successfully'}
                access_code = 204
            else:
                response = {'message': f'Node {name} interface {interface} not present in database'}
                access_code = 404
        else:
            response = {'message': f'Node {name} not present in database'}
            access_code = 404
        return dumps(response), access_code


    def get_all_group_interface(self, name=None):
        """
        This method will return all the group interfaces in detailed format for a desired group.
        """
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
                    response = {'message': f'Group {name} does not have any interface'}
                    access_code = 404
            self.logger.info(f'Returned group {name} with details.')
            access_code = 200
        else:
            self.logger.error('No group is available.')
            response = {'message': 'No group is available'}
            access_code = 404
        return dumps(response), access_code


    def change_group_interface(self, name=None, http_request=None):
        """This method will add or update the group interface."""
        request_data = http_request.data
        if request_data:
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                group_id = group[0]['id']
                if 'interfaces' in request_data['config']['group'][name]:
                    for ifx in request_data['config']['group'][name]['interfaces']:
                        if (not 'network' in ifx) or (not 'interface' in ifx):
                            response = {'message': 'Interface and/or network not specified'}
                            access_code = 400
                            return dumps(response), access_code
                        network = Database().getid_byname('network', ifx['network'])
                        if network is None:
                            response = {'message': f'Network {network} does not exist'}
                            access_code = 404
                            return dumps(response), access_code
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
                        response = {'message': 'Interface updated'}
                        access_code = 204
                        # below section takes care(in the background), adding/renaming/deleting.
                        # for adding next free ip-s will be selected. time consuming
                        # therefor background
                        queue_id, _ = Queue().add_task_to_queue(f'add_interface_to_group_nodes:{name}:{interface}', 'group_interface')
                        next_id = Queue().next_task_in_queue('group_interface')
                        if queue_id == next_id:
                            executor = ThreadPoolExecutor(max_workers=1)
                            executor.submit(Config().update_interface_on_group_nodes,name)
                            executor.shutdown(wait=False)
                            # Config().update_interface_on_group_nodes(name)
                else:
                    self.logger.error('interface not provided.')
                    response = {'message': 'interface not provided'}
                    access_code = 400
            else:
                self.logger.error('No group is available.')
                response = {'message': 'No group is available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def get_group_interface(self, name=None, interface=None):
        """This method will provide a group interface."""
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
                access_code = 200
            else:
                self.logger.error(f'Group {name} does not have {interface} interface.')
                response = {'message': f'Group {name} does not have {interface} interface'}
                access_code = 404
        else:
            self.logger.error('Group is not available.')
            response = {'message': 'Group is not available'}
            access_code = 404
        return dumps(response), access_code


    def delete_group_interface(self, name=None, interface=None):
        """This method will delete a group interface."""
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
                queue_id, _ = Queue().add_task_to_queue(f'delete_interface_from_group_nodes:{name}:{interface}', 'group_interface')
                next_id = Queue().next_task_in_queue('group_interface')
                if queue_id == next_id:
                    # executor = ThreadPoolExecutor(max_workers=1)
                    # executor.submit(Config().update_interface_on_group_nodes,name)
                    # executor.shutdown(wait=False)
                    Config().update_interface_on_group_nodes(name)
                response = {'message': f'Group {name} interface {interface} removed'}
                access_code = 204
            else:
                response = {'message': f'Group {name} interface {interface} not present in database'}
                access_code = 404
        else:
            response = {'message': f'Group {name} not present in database'}
            access_code = 404
        return dumps(response), access_code
