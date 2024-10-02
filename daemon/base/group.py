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
from concurrent.futures import ThreadPoolExecutor
from utils.database import Database
from utils.log import Log
from utils.config import Config
from utils.queue import Queue
from utils.helper import Helper
from common.constant import CONSTANT


class Group():
    """
    This class is responsible for all operations on groups.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]


    def get_all_group(self):
        """
        This method will return all the groups in detailed format.
        """
        groups = Database().get_record(None, 'group', None)
        if groups:
            response = {'config': {'group': {} }}
            for group in groups:
                name = group['name']
                group_id = group['id']
                group_interface = Database().get_record_join(
                    ['groupinterface.interface','network.name as network',
                     'groupinterface.vlanid', 'groupinterface.options'],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{group_id}'"]
                )
                if group_interface:
                    group['interfaces'] = []
                    for interface in group_interface:
                        if not interface['options']:
                            del interface['options']
                        if not interface['vlanid']:
                            del interface['vlanid']
                        group['interfaces'].append(interface)
                del group['id']
                group['setupbmc'] = Helper().make_bool(group['setupbmc'])
                group['netboot'] = Helper().make_bool(group['netboot'])
                group['bootmenu'] = Helper().make_bool(group['bootmenu'])
                group['osimage'] = Database().name_by_id('osimage', group['osimageid'])
                del group['osimageid']
                if group['bmcsetupid']:
                    group['bmcsetupname'] = Database().name_by_id('bmcsetup', group['bmcsetupid'])
                del group['bmcsetupid']
                response['config']['group'][name] = group
        else:
            self.logger.error('No group is available.')
            response = 'No group is available'
            return False, response
        return True,response


    def get_group(self, name=None):
        """
        This method will return requested group in detailed format.
        """
        # things we have to set for a group
        items = {
            # 'prescript': '<empty>',
            # 'partscript': '<empty>',
            # 'postscript': '<empty>',
            'setupbmc':False,
            'netboot':False,
            'bootmenu':False,
            'provision_interface':'BOOTIF',
            'provision_method': 'torrent',
            'provision_fallback': 'http'
        }
        # same as above but now specifically base64
        b64items = {'prescript': '', 'partscript': '', 'postscript': ''}
        cluster = Database().get_record(None, 'cluster', None)
        groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if groups:
            response = {'config': {'group': {} }}
            group = groups[0]
            group_id = group['id']
            group_interface = Database().get_record_join(
                [
                    'groupinterface.interface',
                    'network.name as network',
                    'groupinterface.vlanid',
                    'groupinterface.options'
                ],
                ['network.id=groupinterface.networkid'],
                [f"groupid = '{group_id}'"]
            )
            if group_interface:
                group['interfaces'] = []
                for interface in group_interface:
                    if not interface['options']:
                        del interface['options']
                    if not interface['vlanid']:
                        del interface['vlanid']
                    group['interfaces'].append(interface)
            del group['id']
            for key, value in items.items():
                if key in cluster[0] and ((not key in group) or (not group[key])):
                    if isinstance(value, bool):
                        cluster[0][key] = str(Helper().make_bool(cluster[0][key]))
                    group[key] = str(cluster[0][key])
                    group[key+'_source'] = 'cluster'
                elif key in group and group[key]:
                    if isinstance(value, bool):
                        group[key] = str(Helper().make_bool(group[key]))
                    group[key+'_source'] = 'group'
                    group[key] = group[key] or str(value)
                else:
                    group[key] = str(value)
                    group[key+'_source'] = 'default'
            try:
                for key, value in b64items.items():
                    default_str = str(value)
                    default_data = b64encode(default_str.encode())
                    default_data = default_data.decode("ascii")
                    if key in group and group[key]:
                        group[key] = group[key] or default_data
                        group[key+'_source'] = 'group'
                    else:
                        group[key] = default_data
                        group[key+'_source'] = 'default'
            except Exception as exp:
                self.logger.error(f"{exp}")

            if group['osimageid']:
                osimage = Database().get_record(None, 'osimage', f" WHERE id = '{group['osimageid']}'")
                if osimage:
                    group['osimage'] = osimage[0]['name']
                    if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                        group['provision_method'] = 'kickstart'
                        group['provision_method_source'] = 'osimage'
                        group['provision_fallback'] = None
                        group['provision_fallback_source'] = 'osimage'
                else:    
                    group['osimage'] = Database().name_by_id('osimage', group['osimageid'])
            del group['osimageid']
            group['bmcsetupname'] = None
            if group['bmcsetupid']:
                group['bmcsetupname'] = Database().name_by_id('bmcsetup', group['bmcsetupid'])
            del group['bmcsetupid']
            # ---
            if group['osimagetagid']:
                group['osimagetag'] = Database().name_by_id('osimagetag', group['osimagetagid']) or 'default'
            else:
                group['osimagetag'] = 'default'
            del group['osimagetagid']
            group['osimage_source'] = 'group'
            group['bmcsetupname_source'] = 'group'
            group['osimagetag_source'] = 'group'
            if group['osimagetag'] == 'default':
                group['osimagetag_source'] = 'default'
            # ---
            response['config']['group'][name] = group
            self.logger.info(f'Returned Group {name} with Details.')
        else:
            self.logger.error('No group is available.')
            response = 'No group is available'
            return False,response
        return True,response


    def get_group_member(self, name=None):
        """
        This method will return all the list of all the member node names for a group.
        """
        status=False
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
                status=True
            else:
                self.logger.error(f'Group {name} is not have any member node.')
                response = f'Group {name} is not have any member node'
                status=False
        else:
            self.logger.error(f'Group {name} is not available.')
            response = f'Group {name} is not available'
            status=False
        return status, response


    def update_group(self, name=None, request_data=None):
        """
        This method will create or update a group.
        """
        data = {}
        status=False
        response="Internal error"
        # things we have to set for a group
        items = {
            'prescript': '',
            'partscript': 'bW91bnQgLXQgdG1wZnMgdG1wZnMgL3N5c3Jvb3QK',
            'postscript': 'ZWNobyAndG1wZnMgLyB0bXBmcyBkZWZhdWx0cyAwIDAnID4+IC9zeXNyb290L2V0Yy9mc3RhYgo=',
            'setupbmc': False,
            'netboot': True,
            'bootmenu': False,
            'provision_interface': 'BOOTIF'
        }
        create, update = False, False
        if request_data:
            data = request_data['config']['group'][name]
            oldgroupname = None
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                group_id = group[0]['id']
                if 'newgroupname' in data:
                    newgroupname = data['newgroupname']
                    oldgroupname = name
                    where = f' WHERE `name` = "{newgroupname}"'
                    check_group = Database().get_record(None, 'group', where)
                    if check_group:
                        status=False
                        return status, f'{newgroupname} Already present in database'
                    else:
                        data['name'] = data['newgroupname']
                        del data['newgroupname']
                update = True
            else:
                if 'newgroupname' in data:
                    status=False
                    return status, 'Invalid request: newgroupname is not allowed while creating a new group'
                if 'interfaces' not in data:
                    controller = Database().get_record_join(
                        ['network.name as network'],
                        ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                        ['tableref="controller"', 'controller.beacon=1']
                    )
                    data['interfaces']=[]
                    if controller:
                        data['interfaces'].append(
                        {
                            'interface': 'BOOTIF',
                            'network': controller[0]['network']
                        })
                create = True

            # we reset to make sure we don't add something that won't work
            if 'osimage' in data:
                data['osimagetagid'] = "default"

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

            if 'bmcsetupname' in data:
                bmcsetupname = data['bmcsetupname']
                data['bmcsetupid'] = Database().id_by_name('bmcsetup', data['bmcsetupname'])
                if data['bmcsetupid']:
                    del data['bmcsetupname']
                else:
                    status=False
                    return status, f'BMC Setup {bmcsetupname} does not exist'
            if 'osimage' in data:
                osimage = data['osimage']
                data['osimageid'] = Database().id_by_name('osimage', osimage)
                if data['osimageid']:
                    del data['osimage']
                else:
                    status=False
                    return status, f'OSimage {osimage} does not exist'

            new_interface = None
            if 'interfaces' in data:
                new_interface = data['interfaces']
                del data['interfaces']

            if 'osimagetag' in data:
                osimagetag = data['osimagetag']
                del data['osimagetag']
                if osimagetag == "":
                    data['osimagetagid'] = ""
                else:
                    osimagetagids = None
                    if 'osimageid' in data:
                        osimagetagids = Database().get_record(None, 'osimagetag', f" WHERE osimageid = '{data['osimageid']}' AND name = '{osimagetag}'")
                    elif group and 'osimageid' in group[0]:
                        osimagetagids = Database().get_record(None, 'osimagetag', f" WHERE osimageid = '{group[0]['osimageid']}' AND name = '{osimagetag}'")
                    if osimagetagids:
                        data['osimagetagid'] = osimagetagids[0]['id']
                    else:
                        status = False
                        return status, 'Unknown tag, or osimage and tag not related'

            if 'roles' in data:
                if len(data['roles']) > 0:
                    temp = data['roles']
                    temp = temp.replace(' ',',')
                    data['roles'] = temp.replace(',,',',')
                else:
                    data['roles'] = None
            if 'scripts' in data:
                if len(data['scripts']) > 0:
                    temp = data['scripts']
                    temp = temp.replace(' ',',')
                    data['scripts'] = temp.replace(',,',',')
                else:
                    data['scripts'] = None

            group_columns = Database().get_columns('group')
            column_check = Helper().compare_list(data, group_columns)
            if column_check:
                if update:
                    where = [{"column": "id", "value": group_id}]
                    row = Helper().make_rows(data)
                    Database().update('group', row, where)
                    response = f'Group {name} updated successfully'
                    status=True
                if create:
                    data['name'] = name
                    row = Helper().make_rows(data)
                    group_id = Database().insert('group', row)
                    response = f'Group {name} created successfully'
                    status=True
                if new_interface:
                    for ifx in new_interface:
                        if not 'interface' in ifx:
                            status=False
                            return status, 'Interface name is required for this operation'
                        interface_name = ifx['interface']
                        network = None
                        if not 'network' in ifx:
                            nwk=Database().get_record_join(
                                ['network.name as network', 'network.id as networkid'],
                                [
                                    'network.id=groupinterface.networkid',
                                    'groupinterface.groupid=group.id'
                                ],
                                [
                                    f"`group`.name='{name}'",
                                    f"groupinterface.interface='{interface_name}'"
                                ]
                            )
                            if nwk and 'networkid' in nwk[0]:
                                network=nwk[0]['networkid']
                        else:
                            network = Database().id_by_name('network', ifx['network'])
                            del ifx['network']
                        if network is None:
                            status=False
                            return status, 'Network not provided or does not exist'
                        else:
                            ifx['networkid'] = network
                            ifx['groupid'] = group_id
                        group_clause = f'groupid = "{group_id}"'
                        # network_clause = f'networkid = "{network}"'
                        interface_clause = f'interface = "{interface_name}"'
                        where = f' WHERE {group_clause} AND {interface_clause}'
                        # where += f' AND {interface_clause}'
                        check_interface = Database().get_record(None, 'groupinterface', where)
                        result, queue_id = None, None
                        if not check_interface:
                            row = Helper().make_rows(ifx)
                            result = Database().insert('groupinterface', row)
                            self.logger.info(f'Interface created => {result} .')
                            queue_id, _ = Queue().add_task_to_queue(
                                task='add_interface_to_group_nodes',
                                param=f'{name}:{interface_name}',
                                subsystem='group_interface'
                            )
                        else: # we update only
                            row = Helper().make_rows(ifx)
                            where = [
                                {"column": "groupid", "value": group_id},
                                {"column": "interface", "value": interface_name}
                            ]
                            result = Database().update('groupinterface', row, where)
                            self.logger.info(f'Interface updated => {result} .')
                            queue_id, _ = Queue().add_task_to_queue(
                                task='update_interface_for_group_nodes',
                                param=f'{name}:{interface_name}',
                                subsystem='group_interface'
                            )
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

                # ---- we call the group plugin - maybe someone wants to run something after create/update?
                nodes_in_group = []
                group_details=Database().get_record_join(['node.name AS nodename'],['node.groupid=group.id'],[f"`group`.name='{name}'"])
                if group_details:
                    for group_detail in group_details:
                        nodes_in_group.append(group_detail['nodename'])
                group_plugins = Helper().plugin_finder(f'{self.plugins_path}/group')
                group_plugin=Helper().plugin_load(group_plugins,'group','default')
                try:
                    if oldgroupname and newgroupname:
                        group_plugin().rename(name=oldgroupname, newname=newgroupname)
                    elif create:
                        group_plugin().postcreate(name=name, nodes=nodes_in_group)
                    elif update:
                        group_plugin().postupdate(name=name, nodes=nodes_in_group)
                except Exception as exp:
                    self.logger.error(f"{exp}")

            else:
                status=False
                response = 'Invalid request: Columns are incorrect'
        else:
            status=False
            response = 'Invalid request: Did not receive data'
        return status, response


    def clone_group(self, name=None, request_data=None):
        """
        This method will clone a group.
        """
        data = {}
        status=False
        response="Internal error"
        # things we have to set for a group
        items = {
            'prescript': '',
            'partscript': '',
            'postscript': '',
            'setupbmc': False,
            'netboot': True,
            'bootmenu': False,
        }
        if request_data:
            newgroupname = None
            data = request_data['config']['group'][name]
            grp = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if grp:
                group_id = grp[0]['id']
                if 'newgroupname' in data:
                    newgroupname = data['newgroupname']
                    where = f' WHERE `name` = "{newgroupname}"'
                    check_group = Database().get_record(None, 'group', where)
                    if check_group:
                        status=False
                        return status, f'{newgroupname} Already present in database'
                    data['name'] = data['newgroupname']
                    del data['newgroupname']
                else:
                    status=False
                    return status, 'Destination group name not supplied'
            else:
                status=False,
                return status, f'Source group {name} does not exist'

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
                    status=False
                    return status, f'BMC Setup {bmcsetupname} does not exist'
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
                    status=False
                    return status, f'Group {newgroupname} is not created due to possible property clash'
                # response = f'Group {name} created successfully'
                response = f'Group {name} cloned as {newgroupname} successfully'
                status=True
                group_interfaces = Database().get_record_join(
                    [
                        'groupinterface.interface',
                        'network.name as network',
                        'network.id as networkid',
                        'groupinterface.options'
                    ],
                    ['network.id=groupinterface.networkid'],
                    [f"groupid = '{group_id}'"]
                )

                # ------ secrets ------
                secrets = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{group_id}"')
                for secret in secrets:
                    del secret['id']
                    secret['groupid'] = new_group_id
                    row = Helper().make_rows(secret)
                    result = Database().insert('groupsecrets', row)
                    if not result:
                        self.delete_group(new_group_id)
                        status=False
                        return status, f'Secrets copy for {newgroupname} failed'

                # ------ interfaces -------
                if new_interface:
                    for ifx in new_interface:
                        interface_name = ifx['interface']
                        index = 0
                        for grp_ifx in group_interfaces:
                            # delete interfaces we already have
                            if interface_name == grp_ifx['interface']:
                                del group_interfaces[index]
                            index += 1
                    for ifx in new_interface:
                        interface_name = ifx['interface']
                        if 'network' not in ifx:
                            status=False
                            response=f'Network not specified for interface {interface_name}'
                            break
                        network = Database().id_by_name('network', ifx['network'])
                        if network is None:
                            status=False
                            response=f'Network {network} does not exist'
                            break
                        else:
                            ifx['networkid'] = network
                            if 'options' in ifx:
                                ifx['options'] = ifx['options'] or ""
                            ifx['groupid'] = new_group_id
                            del ifx['network']
                        row = Helper().make_rows(ifx)
                        Database().insert('groupinterface', row)

                if status is False:
                    # rollback
                    self.delete_group(new_group_id)
                    return status, response

                for ifx in group_interfaces:
                    ifx['groupid'] = new_group_id
                    del ifx['network']
                    row = Helper().make_rows(ifx)
                    Database().insert('groupinterface', row)

                # ---- we call the group plugin - maybe someone wants to run something after clone?
                nodes_in_group = []
                group_details=Database().get_record_join(['node.name AS nodename'],['node.groupid=group.id'],[f"`group`.name='{newgroupname}'"])
                if group_details:
                    for group_detail in group_details:
                        nodes_in_group.append(group_detail['nodename'])
                group_plugins = Helper().plugin_finder(f'{self.plugins_path}/group')
                group_plugin=Helper().plugin_load(group_plugins,'group','default')
                try:
                    group_plugin().postcreate(name=newgroupname, nodes=nodes_in_group)
                except Exception as exp:
                    self.logger.error(f"{exp}")
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_group_by_name(self, name=None):
        """
        This method will delete a group by name.
        """
        status=False
        response=f'Group {name} not present in database'
        where = f' WHERE `name` = "{name}"'
        group = Database().get_record(None, 'group', where)
        if group:
            status, response=self.delete_group(group[0]['id'])
        return status, response


    def delete_group(self, groupid=None):
        """
        This method will delete a group.
        """
        status=False
        group = Database().get_record(None, 'group', f'WHERE `id`="{groupid}"')
        if group:
            name=group[0]['name']
            inuse = Database().get_record(None, 'node', f'WHERE `groupid`="{groupid}"')
            if inuse:
                inuseby=[]
                while len(inuse) > 0 and len(inuseby) < 11:
                    node=inuse.pop(0)
                    inuseby.append(node['name'])
                response = f"group {name} currently in use by "+', '.join(inuseby)+" ..."
                return False, response
            where = [{"column": "id", "value": groupid}]
            Database().delete_row('group', where)
            where = [{"column": "groupid", "value": group[0]['id']}]
            Database().delete_row('groupinterface', where)
            Database().delete_row('groupsecrets', where)
            response = f'Group {name} removed'
            status=True
            # ---- we call the group plugin - maybe someone wants to run something after delete?
            group_plugins = Helper().plugin_finder(f'{self.plugins_path}/group')
            group_plugin=Helper().plugin_load(group_plugins,'group','default')
            try:
                group_plugin().delete(name=name)
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            response = 'Group not present in database'
            status=False
        return status, response
