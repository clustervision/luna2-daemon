#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#This code is part of the TrinityX software suite
#Copyright (C) 2023  ClusterVision Solutions b.v.
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>


"""
Node Class, to filter and make data set for nodes.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from base64 import b64decode, b64encode
from utils.database import Database
from utils.log import Log
from utils.config import Config
from utils.service import Service
from utils.queue import Queue
from utils.helper import Helper
from utils.monitor import Monitor
from base.interface import Interface
from common.constant import CONSTANT


class Node():
    """
    This class is responsible for all operations on node.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]


    def get_all_nodes(self):
        """
        This method will return all the nodes in detailed format.
        """
        status = False
        response = {}
        # TODO
        # we collect all needed info from all tables at once and use dicts to collect data/info
        # A join is not really suitable as there are too many permutations in where the below
        # is way more efficient. -Antoine
        nodes = Database().get_record(None, 'node', None)
        groups = Database().get_record(None, 'group', None)
        osimages = Database().get_record(None, 'osimage', None)
        switches = Database().get_record(None, 'switch', None)
        clouds = Database().get_record(None, 'cloud', None)
        bmcsetups = Database().get_record(None, 'bmcsetup', None)
        monitorings = Database().get_record(None, 'monitor', "WHERE tableref='node'")
        group = Helper().convert_list_to_dict(groups, 'id')
        osimage = Helper().convert_list_to_dict(osimages, 'id')
        switch = Helper().convert_list_to_dict(switches, 'id')
        cloud = Helper().convert_list_to_dict(clouds, 'id')
        bmcsetup = Helper().convert_list_to_dict(bmcsetups, 'id')
        monitoring = Helper().convert_list_to_dict(monitorings, 'tablerefid')
        cluster = Database().get_record(None, 'cluster', None)
        if nodes:
            response['config'] = {}
            response['config']['node'] = {}
            items = {
                'prescript': '<empty>',
                'partscript': '<empty>',
                'postscript': '<empty>',
                'setupbmc': False,
                'netboot': False,
                'bootmenu': False,
                'roles': None,
                'scripts': None,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF',
                'kerneloptions': None
            }
            for node in nodes:
                node_name = node['name']
                nodeid = node['id']
                groupid = None
                osimageid = None
                node['_override'] = False
                if 'groupid' in node and node['groupid'] in group:
                    node['group'] = group[node['groupid']]['name']
                    groupid = node['groupid']
                    if node['osimageid']:
                        node['osimage'] = '!!Invalid!!'
                        if node['osimageid'] in osimage:
                            node['osimage'] = osimage[node['osimageid']]['name'] or None
                            osimageid = node['osimageid']
                            node['_override'] = True
                    elif 'osimageid' in group[groupid] and group[groupid]['osimageid'] in osimage:
                        node['osimage'] = osimage[group[groupid]['osimageid']]['name'] or None
                        osimageid = group[groupid]['osimageid']
                    else:
                        node['osimage'] = None
                    if node['bmcsetupid']:
                        node['bmcsetup'] = '!!Invalid!!'
                        if node['bmcsetupid'] in bmcsetup:
                            node['bmcsetup'] = bmcsetup[node['bmcsetupid']]['name'] or None
                            node['_override'] = True
                    elif 'bmcsetupid' in group[groupid] and group[groupid]['bmcsetupid'] in bmcsetup:
                        node['bmcsetup'] = bmcsetup[group[groupid]['bmcsetupid']]['name'] or None
                    else:
                        node['bmcsetup'] = None
                else:
                    node['group'] = '!!Invalid!!'
                # -------------
                for key, value in items.items():
                    if cluster and key in cluster[0] and isinstance(value, bool):
                        cluster[0][key] = str(Helper().make_bool(cluster[0][key]))
                    if osimageid and key in osimage[osimageid] and isinstance(value, bool):
                        osimage[osimageid][key] = str(Helper().make_bool(osimage[osimageid][key]))
                    if groupid and key in group[groupid] and isinstance(value, bool):
                        group[groupid][key] = str(Helper().make_bool(group[groupid][key]))
                    if cluster and key in cluster[0] and ((not group) or (not groupid) or (not key in group[groupid]) or (not group[groupid][key])) and not node[key]:
                        node[key] = cluster[0][key] or value
                    else:
                        if osimageid and key in osimage[osimageid] and not node[key]:
                            node[key] = osimage[osimageid][key] or value
                        elif groupid and key in group[groupid] and not node[key]:
                            node[key] = group[groupid][key] or value
                        else:
                            if isinstance(value, bool):
                                node[key] = str(Helper().make_bool(node[key]))
                            node[key] = node[key] or value
                            node['_override'] = True
                # -------------
                node['switch'] = None
                if node['switchid']:
                    node['switch'] = '!!Invalid!!'
                    if node['switchid'] in switch:
                        node['switch'] = switch[node['switchid']]['name'] or None
                node['cloud'] = None
                if node['cloudid']:
                    node['cloud'] = '!!Invalid!!'
                    if node['cloudid'] in cloud:
                        node['cloud'] = cloud[node['cloudid']]['name'] or None
                node['tpm_present'] = False
                if node['tpm_uuid'] or node['tpm_sha256'] or node['tpm_pubkey']:
                    node['tpm_present'] = True

                node['status'] = None
                if node['id'] in monitoring.keys():
                    node['status'], *_ = Monitor().installer_state(monitoring[node['id']]['state'])

                del node['id']
                del node['bmcsetupid']
                del node['groupid']
                del node['osimageid']
                del node['switchid']
                del node['cloudid']

                node['bootmenu'] = Helper().make_bool(node['bootmenu'])
                node['netboot'] = Helper().make_bool(node['netboot'])
                node['service'] = Helper().make_bool(node['service'])
                node['setupbmc'] = Helper().make_bool(node['setupbmc'])
                node['hostname'] = node['name']
                node['interfaces']=[]
                all_node_interfaces_by_name = {}
                all_node_interfaces = Database().get_record(None, 'nodeinterface', f"WHERE nodeinterface.nodeid='{nodeid}'")
                if all_node_interfaces:
                    all_node_interfaces_by_name = Helper().convert_list_to_dict(all_node_interfaces, 'interface')
                node_interface = Database().get_record_join(
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
                    ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
                )
                if node_interface:
                    node['interfaces'] = []
                    for interface in node_interface:
                        interface_name, *_ = node['provision_interface'].split(' ') + [None]
                        # we skim off parts that we added for clarity in above section
                        # (e.g. (default)). also works if there's no additional info
                        if interface['interface'] == interface_name and interface['network']:
                            # if it is my prov interface then it will get that domain as a FQDN.
                            node['hostname'] = node['name'] + '.' + interface['network']
                        interface['dhcp'] = Helper().make_bool(interface['dhcp'])
                        for item in ['options','vlanid','vlan_parent','bond_mode','bond_slaves','ipaddress','ipaddress_ipv6']:
                            if not interface[item]:
                                del  interface[item]
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
                        node['interfaces'].append(interface)
                        if interface['interface'] in all_node_interfaces_by_name.keys():
                            del all_node_interfaces_by_name[interface['interface']]
                # for incomplete interfaces
                for empty_interface in all_node_interfaces_by_name.keys():
                    interface = all_node_interfaces_by_name[empty_interface]
                    del interface['id']
                    del interface['nodeid']
                    if not interface['options']:
                        del interface['options']
                    node['interfaces'].append(interface)

                response['config']['node'][node_name] = node
            status = True
        else:
            self.logger.error('No nodes available.')
            response = 'No nodes available'
        return status, response


    def get_node(self, name=None):
        """
        This method will return requested node in detailed format.
        """
        status = False
        nodes = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        all_nodes = Database().get_record_join(
            [
                'node.*',
                'group.name AS group',
                'group.osimageid AS group_osimageid',
                'group.osimagetagid AS group_osimagetagid',
                'group.setupbmc AS group_setupbmc',
                'group.bmcsetupid AS group_bmcsetupid',
                'group.prescript AS group_prescript',
                'group.partscript AS group_partscript',
                'group.postscript AS group_postscript',
                'group.netboot AS group_netboot',
                'group.bootmenu AS group_bootmenu',
                'group.roles AS group_roles',
                'group.scripts AS group_scripts',
                'group.provision_method AS group_provision_method',
                'group.provision_fallback AS group_provision_fallback',
                'group.provision_interface AS group_provision_interface',
                'group.kerneloptions AS group_kerneloptions'
            ],
            ['group.id=node.groupid'],
            f"node.name='{name}'"
        )
        if all_nodes and nodes:
            nodes[0].update(all_nodes[0])
        if nodes:
            node = nodes[0]
            response = {'config': {'node': {} }}
            nodename = node['name']
            nodeid = node['id']
            node['_override'] = False
            alt_source = {}
            if node['osimageid']:
                osimage = Database().get_record(None, 'osimage', f" WHERE id = '{node['osimageid']}'")
                if osimage:
                    node['osimage'] = osimage[0]['name']
                    node['osimage_kerneloptions'] = osimage[0]['kerneloptions']
                    if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                        node['provision_method'] = 'kickstart'
                        alt_source['provision_method'] = 'osimage'
                        node['provision_fallback'] = None
                        alt_source['provision_fallback'] = 'osimage'
                else:
                    node['osimage'] = '!!Invalid!!'
                #node['osimage'] = Database().name_by_id('osimage',node['osimageid']) or '!!Invalid!!'
                node['osimage_source'] = 'node'
                node['_override'] = True
            elif 'group_osimageid' in node and node['group_osimageid']:
                osimage = Database().get_record(None, 'osimage', f" WHERE id = '{node['group_osimageid']}'")
                if osimage:
                    node['osimage'] = osimage[0]['name']
                    node['osimage_kerneloptions'] = osimage[0]['kerneloptions']
                    if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                        node['provision_method'] = 'kickstart'
                        alt_source['provision_method'] = 'osimage'
                        node['provision_fallback'] = None
                        alt_source['provision_fallback'] = 'osimage'
                else:
                    node['osimage'] = '!!Invalid!!'
                node['osimage_source'] = 'group'
            else:
                node['osimage'] = None
            if 'group_osimageid' in node:
                del node['group_osimageid']
            #---
            if node['bmcsetupid']:
                node['bmcsetup'] = Database().name_by_id('bmcsetup',node['bmcsetupid']) or '!!Invalid!!'
                node['bmcsetup_source'] = 'node'
                node['_override'] = True
            elif 'group_bmcsetupid' in node and node['group_bmcsetupid']:
                node['bmcsetup'] = Database().name_by_id('bmcsetup', node['group_bmcsetupid']) or '!!Invalid!!'
                node['bmcsetup_source'] = 'group'
            else:
                node['bmcsetup'] = None
            if 'group_bmcsetupid' in node:
                del node['group_bmcsetupid']
            #---
            if node['osimagetagid']:
                node['osimagetag'] = Database().name_by_id('osimagetag', node['osimagetagid']) or 'default'
                node['osimagetag_source'] = 'node'
                node['_override'] = True
            elif 'group_osimagetagid' in node and node['group_osimagetagid']:
                node['osimagetag'] = Database().name_by_id('osimagetag', node['group_osimagetagid']) or 'default'
                node['osimagetag_source'] = 'group'
            else:
                node['osimagetag'] = 'default'
                node['osimagetag_source'] = 'default'
            if 'osimagetagid' in node:
                del node['osimagetagid']
            if 'group_osimagetagid' in node:
                del node['group_osimagetagid']
            #---
            node['switch'] = None
            if node['switchid']:
                node['switch'] = Database().name_by_id('switch', node['switchid'])
            node['cloud'] = None
            if node['cloudid']:
                node['cloud'] = Database().name_by_id('cloud', node['cloudid'])
            #---
            if not node['groupid']:
                node['group'] = '!!Invalid!!'
            elif not 'group' in node:
                node['group'] = '!!Invalid!!'

            cluster = Database().get_record(None, 'cluster', None)
            if cluster:
                node['cluster_provision_method'] = cluster[0]['provision_method']
                node['cluster_provision_fallback'] = cluster[0]['provision_fallback']

            # What's configured for the node, or the group, or a default fallback
            items = {
                # 'prescript': '<empty>',
                # 'partscript': '<empty>',
                # 'postscript': '<empty>',
                'setupbmc': False,
                'netboot': False,
                'bootmenu': False,
                'roles': None,
                'scripts': None,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF',
                'kerneloptions': None
            }
            for key, value in items.items():
                if 'cluster_'+key in node and isinstance(value, bool):
                    node['cluster_'+key] = str(Helper().make_bool(node['cluster_'+key]))
                if 'osimage_'+key in node and isinstance(value, bool):
                    node['osimage_'+key] = str(Helper().make_bool(node['osimage_'+key]))
                if 'group_'+key in node and isinstance(value, bool):
                    node['group_'+key] = str(Helper().make_bool(node['group_'+key]))
                if key in alt_source and alt_source[key] and key in node:
                    node[key+'_source'] = alt_source[key]
                elif 'cluster_'+key in node and node['cluster_'+key] and ((not 'group_'+key in node) or (not node['group_'+key])) and not node[key]:
                    node[key] = node['cluster_'+key] or str(value)
                    node[key+'_source'] = 'cluster'
                elif 'osimage_'+key in node and node['osimage_'+key] and not node[key]:
                    node[key] = node['osimage_'+key] or str(value)
                    node[key+'_source'] = 'osimage'
                elif 'group_'+key in node and node['group_'+key] and not node[key]:
                    node[key] = node['group_'+key] or str(value)
                    node[key+'_source'] = 'group'
                elif value is None and node[key] is None:
                    node[key+'_source'] = 'default'
                elif node[key]:
                    if isinstance(value, bool):
                        node[key] = str(Helper().make_bool(node[key]))
                    node[key+'_source'] = 'node'
                    node['_override'] = True
                else:
                    if isinstance(value, bool):
                        node[key] = str(Helper().make_bool(node[key]))
                    else:
                        node[key] = node[key] or str(value)
                    node[key+'_source'] = 'default'
                if 'osimage_'+key in node:
                    del node['osimage_'+key]
                if 'group_'+key in node:
                    del node['group_'+key]
                if 'cluster_'+key in node:
                    del node['cluster_'+key]
            # same as above but now specifically base64
            b64items = {'prescript': '', 'partscript': '', 'postscript': ''}
            try:
                for key, value in b64items.items():
                    if 'group_'+key in node and node['group_'+key] and not node[key]:
                        node[key] = node['group_'+key]
                        node[key+'_source'] = 'group'
                    elif node[key]:
                        node[key+'_source'] = 'node'
                        node['_override'] = True
                    else:
                        default_str = str(value)
                        default_data = b64encode(default_str.encode())
                        default_data = default_data.decode("ascii")
                        node[key] = default_data
                        node[key+'_source'] = 'default'
                    if 'group_'+key in node:
                        del node['group_'+key]
            except Exception as exp:
                self.logger.error(f"{exp}")

            for my_tpm in ['tpm_uuid','tpm_sha256','tpm_pubkey']:
                if not node[my_tpm]:
                    node[my_tpm]=None

            del node['id']
            del node['bmcsetupid']
            del node['groupid']
            del node['osimageid']
            del node['switchid']
            del node['cloudid']

            node['status'] = None
            monitoring = Database().get_record(None, 'monitor', f"WHERE tableref='node' AND tablerefid='{nodeid}'")
            if monitoring:
                node['status'], *_ = Monitor().installer_state(monitoring[0]['state'])
            node['service'] = Helper().make_bool(node['service'])
            node['setupbmc'] = Helper().make_bool(node['setupbmc'])
            node['hostname'] = nodename

            node['interfaces'] = []
            all_node_interfaces_by_name = {}
            all_node_interfaces = Database().get_record(None, 'nodeinterface', f"WHERE nodeinterface.nodeid='{nodeid}'")
            if all_node_interfaces:
                all_node_interfaces_by_name = Helper().convert_list_to_dict(all_node_interfaces, 'interface')
            node_interface = Database().get_record_join(
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
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            if node_interface:
                for interface in node_interface:
                    interface_name, *_ = node['provision_interface'].split(' ') + [None]
                    # we skim off parts that we added for clarity in above section
                    # (e.g. (default)). also works if there's no additional info
                    if interface['interface'] == interface_name and interface['network']:
                        # if it is my prov interface then it will get that domain as a FQDN.
                        node['hostname'] = nodename + '.' + interface['network']
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
                    node['interfaces'].append(interface)
                    if interface['interface'] in all_node_interfaces_by_name.keys():
                        del all_node_interfaces_by_name[interface['interface']]
            # for incomplete interfaces
            for empty_interface in all_node_interfaces_by_name.keys():
                interface = all_node_interfaces_by_name[empty_interface]
                del interface['id']
                del interface['nodeid']
                if not interface['options']:
                    del interface['options']
                node['interfaces'].append(interface)

            response['config']['node'][nodename] = node
            status = True
        else:
            response = f'Node {name} is not available'
        return status, response


    def update_node(self, name=None, request_data=None):
        """
        This method will return update requested node.
        """
        # status = False
        data = {}
        items = {
            # 'setupbmc': False,
            # 'netboot': False,
            # 'bootmenu': False,
            'service': False,
        }
        # minimal required items with defaults. we do inherit things from e.g. groups. but that's
        # real time and not here
        create, update = False, False
        status = False
        response = "Internal error"
        if request_data:
            data = request_data['config']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            oldnodename = None
            if node:
                nodeid = node[0]['id']
                if 'newnodename' in data: # is mentioned as newhostname in design documents!
                    nodename_new = data['newnodename']
                    oldnodename = name
                    where = f' WHERE `name` = "{nodename_new}"'
                    node_check = Database().get_record(None, 'node', where)
                    if node_check:
                        status = False
                        return status, f'{nodename_new} already present in database'
                    else:
                        data['name'] = data['newnodename']
                        del data['newnodename']
                update = True
            else:
                if 'newnodename' in data:
                    nodename_new = data['newnodename']
                    status = False
                    ret_msg = 'newnodename is only allowed while update, rename or clone a node'
                    return status, ret_msg
                create = True

            for key, value in items.items():
                if key in data:
                    data[key] = data[key] or value
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                elif create:
                    data[key] = value
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                if key in data and (not data[key]) and (key not in items):
                    del data[key]

            # we reset to make sure we don't assing something that won't work
            if 'osimage' in data:
                if data['osimage'] == "":
                    data['osimagetagid'] = ""
                else:
                    data['osimagetagid'] = "default"

            # True means: cannot be empty if supplied. False means: can only be empty or correct
            checks = {'bmcsetup': False, 'group': True, 'osimage': False, 'switch': False, 'cloud': False}
            for key, value in checks.items():
                if key in data:
                    check_name = data[key]
                    if data[key] == "" and value is False:
                        data[key+'id'] = ""
                    else:
                        data[key+'id'] = Database().id_by_name(key, check_name)
                        if not data[key+'id']:
                            status = False
                            return status, f'{key} {check_name} is not known or valid'
                    del data[key]

            interfaces = None
            if 'interfaces' in data:
                interfaces = data['interfaces']
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
                    elif node and 'osimageid' in node[0]:
                        osimagetagids = Database().get_record(None, 'osimagetag', f" WHERE osimageid = '{node[0]['osimageid']}' AND name = '{osimagetag}'")
                    else:
                        # there is a race condition where someone changes the group AND sets a tag at the same time. ... who will do such a thing?? - Antoine
                        osimagetagids = Database().get_record_join(['osimagetag.id'],['osimagetag.osimageid=group.osimageid','group.id=node.groupid'],[f"node.name='{name}'",f"osimagetag.name='{osimagetag}'"])
                    if osimagetagids:
                        data['osimagetagid'] = osimagetagids[0]['id']
                    else:
                        status = False
                        ret_msg = 'Unknown tag or osimage and tag not related'
                        return status, ret_msg

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

            node_columns = Database().get_columns('node')
            columns_check = Helper().compare_list(data, node_columns)
            if columns_check:
                if update:
                    where = [{"column": "id", "value": nodeid}]
                    row = Helper().make_rows(data)
                    Database().update('node', row, where)
                    response = f'Node {name} updated successfully'
                    status = True
                    if nodeid and 'groupid' in data and node and len(node)>0 and 'groupid' in node[0]:
                        Interface().update_node_group_interface(nodeid=nodeid, groupid=data['groupid'], oldgroupid=node[0]['groupid'])
                if create:
                    if 'groupid' not in data:
                        # ai, we DO need this for new nodes...... kind of.
                        # we agreed on this. pending?
                        status = False
                        return status, 'group name is required for new nodes'
                    data['name'] = name
                    row = Helper().make_rows(data)
                    nodeid = Database().insert('node', row)
                    response = f'Node {name} created successfully'
                    status = True

                    if nodeid and 'groupid' in data and data['groupid']:
                        Interface().update_node_group_interface(nodeid=nodeid, groupid=data['groupid'])

                if interfaces:
                    result, message = Interface().change_node_interface(nodeid=nodeid, data=interfaces)
                    if result is False:
                        status = False
                        return status, f'{message}'

                # For now i have the below two disabled. it's testing. -Antoine aug 8 2023
                #Service().queue('dhcp', 'restart')
                #Service().queue('dhcp6', 'restart')
                #Service().queue('dns', 'reload')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue(task='restart', param='dhcp', 
                                          subsystem='housekeeper', request_id='__node_update__')
                Queue().add_task_to_queue(task='restart', param='dhcp6', 
                                          subsystem='housekeeper', request_id='__node_update__')
                Queue().add_task_to_queue(task='reload', param='dns', 
                                          subsystem='housekeeper', request_id='__node_update__')

                # ---- we call the node plugin - maybe someone wants to run something after create/update?
                group_details = Database().get_record_join(['group.name'],
                                                           ['group.id=node.groupid'],
                                                           [f"node.name='{name}'"])
                all_nodes_data = Helper().nodes_and_groups()
                node_plugins = Helper().plugin_finder(f'{self.plugins_path}/hooks')
                node_plugin=Helper().plugin_load(node_plugins,'hooks/config','node')
                try:
                    if oldnodename and nodename_new:
                        node_plugin().rename(name=oldnodename, newname=nodename_new, all=all_nodes_data)
                    elif group_details:
                        if create:
                            node_plugin().postcreate(name=name, group=group_details[0]['name'], all=all_nodes_data)
                        elif update:
                            node_plugin().postupdate(name=name, group=group_details[0]['name'], all=all_nodes_data)
                except Exception as exp:
                    self.logger.error(f"{exp}")
            else:
                response = 'Invalid request: Columns are incorrect'
                status = False
        else:
            response = 'Invalid request: Did not receive data'
            status = False
        return status, response


    def clone_node(self, name=None, request_data=None):
        """This method will clone a node."""
        data = {}
        items = {'service': False}
        status=False
        response="Internal error"
        if request_data:
            if 'node' not in request_data['config'].keys():
                status=False
                return status, 'Bad Request'

            newnodename=None
            data = request_data['config']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if 'newnodename' in data:
                    newnodename = data['newnodename']
                    where = f' WHERE `name` = "{newnodename}"'
                    node_check = Database().get_record(None, 'node', where)
                    if node_check:
                        status=False
                        return status, f'{newnodename} already present in database'
                    else:
                        data['name'] = data['newnodename']
                        del data['newnodename']
                else:
                    status=False
                    return status, 'Destination node name not supplied'
            else:
                status=False
                return status, f'Source node {name} does not exist'

            del node[0]['id']
            del node[0]['status']
            for item in node[0]:
                if not item in data:  # we copy from another node unless we supply
                    data[item] = node[0][item]
                    if item in items and isinstance(items[item], bool):
                        data[item] = str(Helper().bool_to_string(data[item]))
                elif item in items:
                    data[item] = items[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().bool_to_string(data[item]))
                if (not data[item]) and (item not in items):
                    del data[item]

            # True means: cannot be empty if supplied. False means: can only be empty or correct
            checks = {'bmcsetup': False, 'group': True, 'osimage': False, 'switch': False}
            for key, value in checks.items():
                if key in data:
                    check_name = data[key]
                    if data[key] == "" and value is False:
                        data[key+'id']=""
                    else:
                        data[key+'id'] = Database().id_by_name(key, check_name)
                        if not data[key+'id']:
                            status=False
                            return status, f'{key} {check_name} is not known or valid'
                    del data[key]
            interfaces = None
            if 'interfaces' in data:
                interfaces = data['interfaces']
                del data['interfaces']
            node_columns = Database().get_columns('node')
            columns_check = Helper().compare_list(data, node_columns)
            if columns_check:
                new_nodeid=None
                row = Helper().make_rows(data)
                new_nodeid = Database().insert('node', row)
                if not new_nodeid:
                    status=False
                    return status, f'Node {newnodename} is not created due to possible property clash'
                response = f'Node {newnodename} created successfully'
                status=True

                # ------ secrets ------
                secrets = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{nodeid}"')
                for secret in secrets:
                    del secret['id']
                    secret['nodeid'] = new_nodeid
                    row = Helper().make_rows(secret)
                    result = Database().insert('nodesecrets', row)
                    if not result:
                        self.delete_node(new_nodeid)
                        status=False
                        return status, f'Secrets copy for {newnodename} failed'

                # ------ interfaces -------
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
                        'nodeinterface.options'
                    ],
                    ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
                )
                # supplied by API
                if interfaces:
                    for interface in interfaces:
                        # Antoine
                        interface_name = interface['interface']
                        index = 0
                        for node_interface in node_interfaces:
                            # delete interfaces we overwrite
                            if interface_name == node_interface['interface']:
                                del node_interfaces[index]
                            index += 1
                        macaddress, networkname, options = None, None, None 
                        ipaddress, dhcp, set_dhcp, vlanid = None, None, False, None
                        vlan_parent, bond_mode, bond_slaves = None, None, None
                        if 'macaddress' in interface.keys():
                            macaddress = interface['macaddress']
                        if 'options' in interface.keys():
                            options = interface['options']
                        if 'network' in interface.keys():
                            networkname = interface['network']
                        if 'ipaddress' in interface.keys():
                            ipaddress = interface['ipaddress']
                        if 'vlanid' in interface.keys():
                            vlanid = interface['vlanid']
                        if 'vlan_parent' in interface.keys():
                            vlan_parent = interface['vlan_parent']
                        if 'bond_mode' in interface.keys():
                            bond_mode = interface['bond_mode']
                        if 'bond_slaves' in interface.keys():
                            bond_slaves = interface['bond_slaves']
                            bond_slaves = bond_slaves.replace(' ',',')
                            bond_slaves = bond_slaves.replace(',,',',')
                        if 'dhcp' in interface.keys():
                            dhcp = Helper().bool_to_string(interface['dhcp'])
                            set_dhcp = True
                        result, message = Config().node_interface_config(
                            new_nodeid,
                            interface_name,
                            macaddress,
                            vlanid,
                            vlan_parent,
                            bond_mode,
                            bond_slaves,
                            options
                        )
                        if result:
                            if networkname and not ipaddress:
                                where = f' WHERE `name` = "{networkname}"'
                                network = Database().get_record(None, 'network', where)
                                if network:
                                    if network[0]['dhcp'] and network[0]['dhcp_nodes_in_pool']:
                                        dhcp = 1 # forced!
                                        set_dhcp = True
                                    else:
                                        if network[0]['network']:
                                            ips = Config().get_all_occupied_ips_from_network(networkname)
                                            avail = Helper().get_available_ip(
                                                network[0]['network'],
                                                network[0]['subnet'],
                                                ips, ping=True
                                            )
                                            if avail:
                                                ipaddress = avail
                                        # IPv6 as alternative
                                        if network[0]['network_ipv6']:
                                            ips = Config().get_all_occupied_ips_from_network(networkname,'ipv6')
                                            avail = Helper().get_available_ip(
                                                network[0]['network_ipv6'],
                                                network[0]['subnet_ipv6'],
                                                ips, ping=True
                                            )
                                            if avail:
                                                ipaddress = avail

                            if networkname and set_dhcp:
                                result, message = Config().node_interface_dhcp_config(
                                    new_nodeid,
                                    interface_name,
                                    dhcp,
                                    networkname
                                )

                            if networkname and (ipaddress or dhcp):
                                if ipaddress:
                                    result, message = Config().node_interface_ipaddress_config(
                                        new_nodeid,
                                        interface_name,
                                        ipaddress,
                                        networkname
                                    )
                            else:
                                self.delete_node(new_nodeid)
                                status=False
                                return status, f"Interface {interface_name} creation failed. Network and/or ip address missing or incorrect"
                        if result is False:
                            self.delete_node(new_nodeid)
                            status=False
                            return status, f'{message}'

                # what we have in the database
                for node_interface in node_interfaces:
                    interface_name = node_interface['interface']
                    interface_vlanid = node_interface['vlanid']
                    interface_vlan_parent = node_interface['vlan_parent']
                    interface_bond_mode = node_interface['bond_mode']
                    interface_bond_slaves = node_interface['bond_slaves']
                    interface_options = node_interface['options']
                    interface_dhcp = node_interface['dhcp']
                    result, message = Config().node_interface_config(
                        new_nodeid,
                        interface_name,
                        None,
                        interface_vlanid,
                        interface_vlan_parent,
                        interface_bond_mode,
                        interface_bond_slaves,
                        interface_options
                    )
                    if result and 'ipaddress' in node_interface.keys():
                        if 'network' in node_interface.keys():
                            networkname = node_interface['network']
                            where = f' WHERE `name` = "{networkname}"'
                            network = Database().get_record(None, 'network', where)
                            if network:
                                if network[0]['dhcp'] and network[0]['dhcp_nodes_in_pool']:
                                    interface_dhcp = 1
                                else:
                                    if network[0]['network']:
                                        ips = Config().get_all_occupied_ips_from_network(networkname)
                                        avail = Helper().get_next_ip(node_interface['ipaddress'], ips, ping=True)
                                        if not avail:
                                            avail = Helper().get_available_ip(
                                                network[0]['network'],
                                                network[0]['subnet'],
                                                ips, ping=True
                                            )

                                        if avail:
                                            result, message = Config().node_interface_ipaddress_config(
                                                new_nodeid,
                                                interface_name,
                                                avail,
                                                networkname
                                            )
                                            if result is False:
                                                self.delete_node(new_nodeid)
                                                status=False
                                                return status, f'{message}'
                                    # IPv6
                                    if network[0]['network_ipv6']:
                                        ips = Config().get_all_occupied_ips_from_network(networkname,'ipv6')
                                        avail = Helper().get_next_ip(node_interface['ipaddress_ipv6'], ips, ping=True)
                                        if not avail:
                                            avail = Helper().get_available_ip(
                                                network[0]['network_ipv6'],
                                                network[0]['subnet_ipv6'],
                                                ips, ping=True
                                            )

                                        if avail:
                                            result, message = Config().node_interface_ipaddress_config(
                                                new_nodeid,
                                                interface_name,
                                                avail,
                                                networkname
                                            )
                                            if result is False:
                                                self.delete_node(new_nodeid)
                                                status=False
                                                return status, f'{message}'
                                # DHCP
                                if interface_dhcp:
                                    result, message = Config().node_interface_dhcp_config(
                                        new_nodeid,
                                        interface_name,
                                        interface_dhcp,
                                        networkname
                                    )
                                    if result is False:
                                        self.delete_node(new_nodeid)
                                        status=False
                                        return status, f'{message}'
                    if result is False:
                        status=False
                        self.delete_node(new_nodeid)
                        if isinstance(message, str):
                            return status, f'Interface {interface_name} creation failed: {message}'
                        return status, f'Interface {interface_name} creation failed'
                # Service().queue('dhcp','restart')
                # Service().queue('dhcp6','restart')
                # do we need dhcp restart? MAC is wiped on new NIC so no real need i guess. pending
                #Service().queue('dns','reload')
                #Queue().add_task_to_queue(task='restart', param='dhcp', 
                #                          subsystem='housekeeper', request_id='__node_clone__')
                #Queue().add_task_to_queue(task='restart', param='dhcp6', 
                #                          subsystem='housekeeper', request_id='__node_clone__')
                Queue().add_task_to_queue(task='reload', param='dns', 
                                          subsystem='housekeeper', request_id='__node_clone__')

                # ---- we call the node plugin - maybe someone wants to run something after clone?
                group_details = Database().get_record_join(['group.name'],
                                                           ['group.id=node.groupid'],
                                                           [f"node.name='{newnodename}'"])
                if group_details:
                    all_nodes_data = Helper().nodes_and_groups()
                    node_plugins = Helper().plugin_finder(f'{self.plugins_path}/hooks')
                    node_plugin=Helper().plugin_load(node_plugins,'hooks/config','node')
                    try:
                        node_plugin().postcreate(name=newnodename, group=group_details[0]['name'], all=all_nodes_data)
                    except Exception as exp:
                        self.logger.error(f"{exp}")
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_node_by_name(self, name=None):
        """
        This method will delete a node by name.
        """
        status=False
        response = f'Node {name} not present in database'
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            status, response=self.delete_node(node[0]['id'])
        return status, response


    def delete_node(self, nodeid=None):
        """
        This method will delete a node.
        """
        status=False
        response="Internal error"
        node = Database().get_record(None, 'node', f' WHERE `id` = "{nodeid}"')
        if node:
            name = node[0]['name']
            Database().delete_row('node', [{"column": "id", "value": nodeid}])
            ipaddress = Database().get_record_join(
                ['ipaddress.id'],
                ['ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"]
            )
            if ipaddress:
                for node_ip in ipaddress:
                    Database().delete_row('ipaddress', [{"column": "id", "value": node_ip['id']}])
            Database().delete_row('nodeinterface', [{"column": "nodeid", "value": nodeid}])
            Database().delete_row('nodesecrets', [{"column": "nodeid", "value": nodeid}])
            Database().delete_row('rackinventory', [{"column": "tablerefid", "value": nodeid},
                                                    {"column": "tableref", "value": "node"}])
            # for now i have disabled the below two lines for testing purposes. Antoine Aug 8 2023
            #Service().queue('dns', 'resload')
            #Service().queue('dhcp', 'restart')
            #Service().queue('dhcp6', 'restart')
            # below might look redundant but is added to prevent a possible race condition
            # when many nodes are added in a loop.
            # the below tasks ensures that even the last node will be included in dhcp/dns
            Queue().add_task_to_queue(task='restart', param='dhcp', 
                                      subsystem='housekeeper', request_id='__node_delete__')
            Queue().add_task_to_queue(task='restart', param='dhcp6', 
                                      subsystem='housekeeper', request_id='__node_delete__')
            Queue().add_task_to_queue(task='reload', param='dns', 
                                      subsystem='housekeeper', request_id='__node_delete__')
            response = f'Node {name} with all its interfaces removed'
            status=True
            # ---- we call the node plugin - maybe someone wants to run something after delete?
            all_nodes_data = Helper().nodes_and_groups()
            node_plugins = Helper().plugin_finder(f'{self.plugins_path}/hooks')
            node_plugin=Helper().plugin_load(node_plugins,'hooks/config','node')
            try:
                node_plugin().delete(name=name, all=all_nodes_data)
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            response = f'Node not present in database'
            status=False
        return status, response
