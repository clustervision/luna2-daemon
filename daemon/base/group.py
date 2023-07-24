#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Group Class have all kind of group operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from base64 import b64encode
from json import dumps
from concurrent.futures import ThreadPoolExecutor
from utils.database import Database
from utils.log import Log
from utils.config import Config
from utils.queue import Queue
from utils.helper import Helper


class Group():
    """
    This class is responsible for all operations on groups.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_group(self):
        """This method will return all the groups in detailed format."""
        groups = Database().get_record(None, 'group', None)
        if groups:
            response = {'config': {'group': {} }}
            for group in groups:
                name = group['name']
                group_id = group['id']
                group_interface = Database().get_record_join(
                    ['groupinterface.interface','network.name as network','groupinterface.options'],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{group_id}'"]
                )
                if group_interface:
                    group['interfaces'] = []
                    for interface in group_interface:
                        interface['options'] = interface['options'] or ""
                        group['interfaces'].append(interface)
                del group['id']
                group['setupbmc'] = Helper().make_bool(group['setupbmc'])
                group['netboot'] = Helper().make_bool(group['netboot'])
                group['localinstall'] = Helper().make_bool(group['localinstall'])
                group['bootmenu'] = Helper().make_bool(group['bootmenu'])
                group['osimage'] = Database().name_by_id('osimage', group['osimageid'])
                del group['osimageid']
                if group['bmcsetupid']:
                    group['bmcsetupname'] = Database().name_by_id('bmcsetup', group['bmcsetupid'])
                del group['bmcsetupid']
                response['config']['group'][name] = group
            self.logger.info('Provided list of all groups with details.')
        else:
            self.logger.error('No group is available.')
            response = {'message': 'No group is available'}
            return False, response
        return True,response


    def get_group(self, name=None):
        """This method will return requested group in detailed format."""
        # things we have to set for a group
        items = {
            # 'prescript': '<empty>',
            # 'partscript': '<empty>',
            # 'postscript': '<empty>',
            'setupbmc':False,
            'netboot':False,
            'localinstall':False,
            'bootmenu':False,
            'provision_interface':'BOOTIF',
            'provision_method': 'torrent',
            'provision_fallback': 'http'
        }
        # same as above but now specifically base64
        b64items = {
            'prescript': '<empty>',
            'partscript': '<empty>',
            'postscript': '<empty>'
        }
        cluster = Database().get_record(None, 'cluster', None)
        groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if groups:
            response = {'config': {'group': {} }}
            for group in groups:
                group_id = group['id']
                group_interface = Database().get_record_join(
                    ['groupinterface.interface', 'network.name as network', 'groupinterface.options'],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{group_id}'"]
                )
                if group_interface:
                    group['interfaces'] = []
                    for interface in group_interface:
                        if not interface['options']:
                            del interface['options']
                        group['interfaces'].append(interface)
                del group['id']
                for item in items.keys():
                    if item in cluster[0]:
                        if isinstance(items[item], bool):
                            cluster[0][item] = str(Helper().make_bool(cluster[0][item]))
                        cluster[0][item] = cluster[0][item] or str(items[item]+' (default)')
                    if item in group:
                        if isinstance(items[item], bool):
                            group[item] = str(Helper().make_bool(group[item]))
                    if item in cluster[0] and ((not item in group) or (not group[item])):
                        group[item] = str(cluster[0][item])+' (cluster)'
                    else:
                        if item in group:
                            group[item] = group[item] or str(items[item]+' (default)')
                        else:
                            if isinstance(items[item], bool):
                                group[item] = str(Helper().make_bool(group[item]))
                            group[item] = str(items[item]+' (default)')
                try:
                    for item in b64items.keys():
                        default_str = str(b64items[item]+' (default)')
                        default_data = b64encode(default_str.encode())
                        default_data = default_data.decode("ascii")
                        if item in group:
                            group[item] = group[item] or default_data
                        else:
                            group[item] = default_data
                except Exception as exp:
                    self.logger.error(f"{exp}")

                group['osimage'] = Database().name_by_id('osimage', group['osimageid'])
                del group['osimageid']
                if group['bmcsetupid']:
                    group['bmcsetupname'] = Database().name_by_id('bmcsetup', group['bmcsetupid'])
                del group['bmcsetupid']
                response['config']['group'][name] = group
            self.logger.info(f'Returned Group {name} with Details.')
        else:
            self.logger.error('No group is available.')
            response = {'message': 'No group is available'}
            return False,response
        return True,response


    def get_group_member(self, name=None):
        """This method will return all the list of all the member node names for a group."""
        groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if groups:
            group = groups[0]
            groupid = group['id']
            response = {'config': {'group': {name: {'members': []}} }}
            node_list = Database().get_record(None, 'node', f' WHERE groupid = "{groupid}"')
            if node_list:
                nodes = []
                for node in node_list:
                    nodes.append(node['name'])
                response['config']['group'][name]['members'] = nodes
                self.logger.info(f'Provided all group member nodes {nodes}.')
                access_code = 200
            else:
                self.logger.error(f'Group {name} is not have any member node.')
                response = {'message': f'Group {name} is not have any member node'}
                access_code = 404
        else:
            self.logger.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_group(self, name=None, http_request=None):
        """This method will create or update a group."""
        data = {}
        # things we have to set for a group
        items = {
            'prescript': '',
            'partscript': '',
            'postscript': '',
            'setupbmc': False,
            'netboot': False,
            'localinstall': False,
            'bootmenu': False,
            'provision_interface': 'BOOTIF'
        }
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config']['group'][name]
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                group_id = group[0]['id']
                if 'newgroupname' in data:
                    newgroupname = data['newgroupname']
                    where = f' WHERE `name` = "{newgroupname}"'
                    check_group = Database().get_record(None, 'group', where)
                    if check_group:
                        response = {'message': f'{newgroupname} Already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newgroupname']
                        del data['newgroupname']
                update = True
            else:
                if 'newgroupname' in data:
                    response = {'message': f'{newgroupname} is not allowed while creating a new group'}
                    access_code = 400
                    return dumps(response), access_code
                create = True

            for item in items:
                if item in data:
                    data[item] = data[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().bool_to_string(data[item]))
                elif create:
                    data[item] = items[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().bool_to_string(data[item]))
                if item in data and (not data[item]) and (item not in items):
                    del data[item]

            if 'bmcsetupname' in data:
                bmcsetupname = data['bmcsetupname']
                data['bmcsetupid'] = Database().id_by_name('bmcsetup', data['bmcsetupname'])
                if data['bmcsetupid']:
                    del data['bmcsetupname']
                else:
                    response = {'message': f'BMC Setup {bmcsetupname} does not exist'}
                    access_code = 404
                    return dumps(response), access_code
            if 'osimage' in data:
                osimage = data['osimage']
                data['osimageid'] = Database().id_by_name('osimage', osimage)
                if data['osimageid']:
                    del data['osimage']
                else:
                    response = {'message': f'OSimage {osimage} does not exist'}
                    access_code = 404
                    return dumps(response), access_code

            new_interface = None
            if 'interfaces' in data:
                new_interface = data['interfaces']
                del data['interfaces']

            group_columns = Database().get_columns('group')
            column_check = Helper().compare_list(data, group_columns)
            if column_check:
                if update:
                    where = [{"column": "id", "value": group_id}]
                    row = Helper().make_rows(data)
                    Database().update('group', row, where)
                    response = {'message': f'Group {name} updated successfully'}
                    access_code = 204
                if create:
                    data['name'] = name
                    row = Helper().make_rows(data)
                    group_id = Database().insert('group', row)
                    response = {'message': f'Group {name} created successfully'}
                    access_code = 201
                if new_interface:
                    for ifx in new_interface:
                        if not 'interface' in ifx:
                            response = {'message': 'Bad Request; Interface name is required for this operation'}
                            access_code = 400
                            return dumps(response), access_code
                        interface_name = ifx['interface']
                        network = None
                        if not 'network' in ifx:
                            nwk=Database().get_record_join(
                                ['network.name as network', 'network.id as networkid'],
                                ['network.id=groupinterface.networkid', 'groupinterface.groupid=group.id'],
                                [f"`group`.name='{name}'", f"groupinterface.interface='{interface_name}'"]
                            )
                            if nwk and 'networkid' in nwk[0]:
                                network=nwk[0]['networkid']
                        else:
                            network = Database().id_by_name('network', ifx['network'])
                            del ifx['network']
                        if network is None:
                            response = {'message': 'Bad Request; Network not provided or does not exist'}
                            access_code = 404
                            return dumps(response), access_code
                        else:
                            ifx['networkid'] = network
                            ifx['groupid'] = group_id
                        group_clause = f'groupid = "{group_id}"'
                        # network_clause = f'networkid = "{network}"'
                        interface_clause = f'interface = "{interface_name}"'
                        # where = f' WHERE {group_clause} AND {network_clause} AND {interface_clause}'
                        where = f' WHERE {group_clause} AND {interface_clause}'
                        check_interface = Database().get_record(None, 'groupinterface', where)
                        result, queue_id = None, None
                        if not check_interface:
                            row = Helper().make_rows(ifx)
                            result = Database().insert('groupinterface', row)
                            self.logger.info(f'Interface created => {result} .')
                            queue_id, _ = Queue().add_task_to_queue(f'add_interface_to_group_nodes:{name}:{interface_name}', 'group_interface')
                        else: # we update only
                            row = Helper().make_rows(ifx)
                            where=[{"column": "groupid", "value": group_id},{"column": "interface", "value": interface_name}]
                            result = Database().update('groupinterface', row, where)
                            self.logger.info(f'Interface updated => {result} .')
                            queue_id, _ = Queue().add_task_to_queue(f'update_interface_for_group_nodes:{name}:{interface_name}', 'group_interface')
                        # below section takes care(in the background) the adding/renaming/deleting.
                        # for adding next free ip-s will be selected. time consuming there for
                        # background
                        if result:
                            next_id = Queue().next_task_in_queue('group_interface')
                            if queue_id == next_id:
                                executor = ThreadPoolExecutor(max_workers=1)
                                executor.submit(Config().update_interface_on_group_nodes,name)
                                executor.shutdown(wait=False)
                                # Config().update_interface_on_group_nodes(name)

            else:
                response = {'message': 'Bad Request; Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def clone_group(self, name=None, http_request=None):
        """This method will clone a node."""
        data = {}
        # things we have to set for a group
        items = {
            'prescript': '',
            'partscript': '',
            'postscript': '',
            'setupbmc': False,
            'netboot': True,
            'localinstall': False,
            'bootmenu': False,
        }
        request_data = http_request.data
        if request_data:
            data = request_data['config']['group'][name]
            grp = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if grp:
                group_id = grp[0]['id']
                if 'newgroupname' in data:
                    newgroupname = data['newgroupname']
                    where = f' WHERE `name` = "{newgroupname}"'
                    check_group = Database().get_record(None, 'group', where)
                    if check_group:
                        response = {'message': f'{newgroupname} Already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    data['name'] = data['newgroupname']
                    del data['newgroupname']
                else:
                    response = {'message': 'Bad Request; Destination group name not supplied'}
                    access_code = 400
                    return dumps(response), access_code
            else:
                response = {'message': f'Bad Request; Source group {name} does not exist'}
                access_code = 400
                return dumps(response), access_code

            del grp[0]['id']
            for item in grp[0]:
                if item in data:
                    data[item] = data[item]
                    if item in items and isinstance(items[item], bool):
                        data[item]=str(Helper().bool_to_string(data[item]))
                else:
                    data[item] = grp[0][item]
                    if item in items and isinstance(items[item], bool):
                        data[item]=str(Helper().bool_to_string(data[item]))
                if item in items:
                    data[item] = data[item] or items[item]
                    if item in items and isinstance(items[item], bool):
                        data[item]=str(Helper().bool_to_string(data[item]))
                if (not data[item]) and (item not in items):
                    del data[item]
            if 'bmcsetupname' in data:
                bmcsetupname = data['bmcsetupname']
                data['bmcsetupid'] = Database().id_by_name('bmcsetup', data['bmcsetupname'])
                if data['bmcsetupid']:
                    del data['bmcsetupname']
                else:
                    response = {'message': f'BMC Setup {bmcsetupname} does not exist'}
                    access_code = 404
                    return dumps(response), access_code
            if 'osimage' in data:
                osimage = data['osimage']
                del data['osimage']
                data['osimageid'] = Database().id_by_name('osimage', osimage)
            new_interface = None
            if 'interfaces' in data:
                new_interface = data['interfaces']
                del data['interfaces']
            group_columns = Database().get_columns('group')
            column_check = Helper().compare_list(data, group_columns)
            if column_check:
                row = Helper().make_rows(data)
                new_group_id = Database().insert('group', row)
                if not new_group_id:
                    response = {'message': f'Node {newgroupname} could not be created due to possible property clash'}
                    access_code = 404
                    return dumps(response), access_code
                response = {'message': f'Group {name} created successfully'}
                access_code = 201
                group_interfaces = Database().get_record_join(
                    ['groupinterface.interface', 'network.name as network', 'network.id as networkid', 'groupinterface.options'],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{group_id}'"]
                )

                if new_interface:
                    for ifx in new_interface:
                        network = Database().id_by_name('network', ifx['network'])
                        if network is None:
                            response = {'message': f'Bad Request; Network {network} not exist'}
                            access_code = 404
                            return dumps(response), access_code
                        else:
                            ifx['networkid'] = network
                            ifx['groupid'] = group_id
                            del ifx['network']
                        interface_name = ifx['interface']
                        for grp_ifx in group_interfaces:
                            if grp_ifx['interface'] == interface_name:
                                del group_interfaces[grp_ifx]
                        row = Helper().make_rows(ifx)
                        Database().insert('groupinterface', row)

                for interface in group_interfaces:
                    ifx = {}
                    ifx['networkid'] = interface['networkid']
                    ifx['interface'] = interface['interface']
                    ifx['options'] = interface['options'] or ""
                    ifx['groupid'] = new_group_id
                    row = Helper().make_rows(ifx)
                    Database().insert('groupinterface', row)

            else:
                response = {'message': 'Bad Request; Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def delete_group(self, name=None):
        """This method will delete a group."""
        group = Database().get_record(None, 'group', f' WHERE `name` = "{name}"')
        if group:
            Database().delete_row('group', [{"column": "name", "value": name}])
            Database().delete_row('groupinterface', [{"column": "groupid", "value": group[0]['id']}])
            Database().delete_row('groupsecrets', [{"column": "groupid", "value": group[0]['id']}])
            response = {'message': f'Group {name} with all its interfaces removed'}
            access_code = 204
        else:
            response = {'message': f'Group {name} not present in database'}
            access_code = 404
        return dumps(response), access_code
