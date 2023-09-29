#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Node Class, to filter and make data set for nodes.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from base64 import b64decode, b64encode
from json import dumps
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
        self.plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIR"]


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
        bmcsetups = Database().get_record(None, 'bmcsetup', None)
        group = Helper().convert_list_to_dict(groups, 'id')
        osimage = Helper().convert_list_to_dict(osimages, 'id')
        switch = Helper().convert_list_to_dict(switches, 'id')
        bmcsetup = Helper().convert_list_to_dict(bmcsetups, 'id')
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
                'localinstall': False,
                'bootmenu': False,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF'
            }
            for node in nodes:
                node_name = node['name']
                nodeid = node['id']
                groupid = {}
                if 'groupid' in node and node['groupid'] in group:
                    node['group'] = group[node['groupid']]['name']
                    groupid = node['groupid']
                    if node['osimageid']:
                        node['osimage'] = '!!Invalid!!'
                        if node['osimageid'] in osimage:
                            node['osimage'] = osimage[node['osimageid']]['name'] or None
                    elif 'osimageid' in group[groupid] and group[groupid]['osimageid'] in osimage:
                        node['osimage'] = osimage[group[groupid]['osimageid']]['name'] or None
                    else:
                        node['osimage'] = None
                    if node['bmcsetupid']:
                        node['bmcsetup'] = '!!Invalid!!'
                        if node['bmcsetupid'] in bmcsetup:
                            node['bmcsetup'] = bmcsetup[node['bmcsetupid']]['name'] or None
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
                    if groupid and key in group[groupid] and isinstance(value, bool):
                        group[groupid][key] = str(Helper().make_bool(group[groupid][key]))
                    if cluster and key in cluster[0] and ((not group) or (not groupid) or (not key in group[groupid]) or (not group[groupid][key])) and not node[key]:
                        node[key] = cluster[0][key] or value
                    else:
                        if groupid and key in group[groupid] and not node[key]:
                            node[key] = group[groupid][key] or value
                        else:
                            if isinstance(value, bool):
                                node[key] = str(Helper().make_bool(node[key]))
                            node[key] = node[key] or value
                # -------------
                node['switch'] = None
                if node['switchid']:
                    node['switch'] = '!!Invalid!!'
                    if node['switchid'] in switch:
                        node['switch'] = switch[node['switchid']]['name'] or None
                node['tpm_present'] = False
                if node['tpm_uuid'] or node['tpm_sha256'] or node['tpm_pubkey']:
                    node['tpm_present'] = True
                del node['id']
                del node['bmcsetupid']
                del node['groupid']
                del node['osimageid']
                del node['switchid']

                node['status'], *_ = Monitor().installer_state(node['status'])

                node['bootmenu'] = Helper().make_bool(node['bootmenu'])
                node['localinstall'] = Helper().make_bool(node['localinstall'])
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
                        'nodeinterface.macaddress',
                        'network.name as network',
                        'nodeinterface.options'
                    ],
                    ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
                )
                if node_interface:
                    node['interfaces'] = []
                    for interface in node_interface:
                        interface_name, *_ = (node['provision_interface'].split(' ') + [None])
                        # we skim off parts that we added for clarity in above section
                        # (e.g. (default)). also works if there's no additional info
                        if interface['interface'] == interface_name and interface['network']:
                            # if it is my prov interface then it will get that domain as a FQDN.
                            node['hostname'] = node['name'] + '.' + interface['network']
                        if not interface['options']:
                            del interface['options']
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
            self.logger.info('Provided list of all nodes.')
            status = True
        else:
            self.logger.error('No nodes available.')
            response = 'No nodes available'
        return status, response


    def get_node(self, cli=None, name=None):
        """
        This method will return requested node in detailed format.
        """
        status = False
        nodes = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        all_nodes = Database().get_record_join(
            [
                'node.*',
                'group.name AS group',
                'osimage.name AS group_osimage',
                'group.osimagetagid AS group_osimagetagid',
                'group.setupbmc AS group_setupbmc',
                'group.bmcsetupid AS group_bmcsetupid',
                'group.prescript AS group_prescript',
                'group.partscript AS group_partscript',
                'group.postscript AS group_postscript',
                'group.netboot AS group_netboot',
                'group.localinstall AS group_localinstall',
                'group.bootmenu AS group_bootmenu',
                'group.provision_method AS group_provision_method',
                'group.provision_fallback AS group_provision_fallback',
                'group.provision_interface AS group_provision_interface'
            ],
            ['group.id=node.groupid','osimage.id=group.osimageid'],
            f"node.name='{name}'"
        )
        if all_nodes and nodes:
            nodes[0].update(all_nodes[0])
        if nodes:
            node = nodes[0]
            response = {'config': {'node': {} }}
            nodename = node['name']
            nodeid = node['id']
            if node['bmcsetupid']:
                node['bmcsetup'] = Database().name_by_id(
                    'bmcsetup',
                    node['bmcsetupid']
                ) or '!!Invalid!!'
            elif 'group_bmcsetupid' in node and node['group_bmcsetupid']:
                if cli:
                    node['bmcsetup'] = Database().name_by_id('bmcsetup', node['group_bmcsetupid']) + f" ({node['group']})"
                else:
                    node['bmcsetup'] = Database().name_by_id('bmcsetup', node['group_bmcsetupid'])
            if 'group_bmcsetupid' in node:
                del node['group_bmcsetupid']
            #---
            if node['osimageid']:
                node['osimage'] = Database().name_by_id('osimage', node['osimageid']) or '!!Invalid!!'
            elif 'group_osimage' in node and node['group_osimage']:
                if cli:
                    node['osimage'] = node['group_osimage']+f" ({node['group']})"
                else:
                    node['osimage'] = node['group_osimage']
            if 'group_osimage' in node:
                del node['group_osimage']
            #---
            if node['osimagetagid']:
                node['osimagetag'] = Database().name_by_id('osimagetag', node['osimagetagid']) or 'default'
            elif 'group_osimagetagid' in node and node['group_osimagetagid']:
                node['osimagetag'] = Database().name_by_id('osimagetag', node['group_osimagetagid']) or 'default'
                if cli:
                    node['osimagetag'] = node['osimagetag']+f" ({node['group']})"
            else:
                node['osimagetag'] = 'default'
            if 'osimagetagid' in node:
                del node['osimagetagid']
            if 'group_osimagetagid' in node:
                del node['group_osimagetagid']
            #---
            node['switch'] = None
            if node['switchid']:
                node['switch'] = Database().name_by_id('switch', node['switchid'])
            #---
            if not node['groupid']:
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
                'localinstall': False,
                'bootmenu': False,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF'
            }
            for key, value in items.items():
                if 'cluster_'+key in node and isinstance(value, bool):
                    node['cluster_'+key] = str(Helper().make_bool(node['cluster_'+key]))
                if 'group_'+key in node and isinstance(value, bool):
                    node['group_'+key] = str(Helper().make_bool(node['group_'+key]))
                if 'cluster_'+key in node and node['cluster_'+key] and ((not 'group_'+key in node) or (not node['group_'+key])) and not node[key]:
                    if cli:
                        node['cluster_'+key] += " (cluster)"
                        node[key] = node[key] or node['cluster_'+key] or str(value+' (default)')
                    else:
                        node[key] = node[key] or node['cluster_'+key] or str(value)
                else:
                    if 'group_'+key in node and node['group_'+key] and not node[key]:
                        if cli:
                            node['group_'+key] += f" ({node['group']})"
                            node[key] = node[key] or node['group_'+key] or str(value+' (default)')
                        else:
                            node[key] = node[key] or node['group_'+key] or str(value)
                    else:
                        if isinstance(value, bool):
                            node[key] = str(Helper().make_bool(node[key]))
                        if cli:
                            node[key] = node[key] or str(value)+' (default)'
                        else:
                            node[key] = node[key] or str(value)
                if 'group_'+key in node:
                    del node['group_'+key]
                if 'cluster_'+key in node:
                    del node['cluster_'+key]
            # same as above but now specifically base64
            if cli:
                b64items = {'prescript': '<empty>', 'partscript': '<empty>', 'postscript': '<empty>'}
            else:
                b64items = {'prescript': '', 'partscript': '', 'postscript': ''}
            try:
                for key, value in b64items.items():
                    if 'group_'+key in node and node['group_'+key] and not node[key]:
                        data = b64decode(node['group_'+key])
                        data = data.decode("ascii")
                        if cli:
                            data = f"({node['group']}) {data}"
                        group_data = b64encode(data.encode())
                        group_data = group_data.decode("ascii")
                        node[key] = node[key] or group_data
                    else:
                        if cli:
                            default_str = str(value+' (default)')
                        else:
                            default_str = str(value)
                        default_data = b64encode(default_str.encode())
                        default_data = default_data.decode("ascii")
                        node[key] = node[key] or default_data
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
            node['status'], *_ = Monitor().installer_state(node['status'])
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
                    'nodeinterface.macaddress',
                    'network.name as network',
                    'nodeinterface.options'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            if node_interface:
                for interface in node_interface:
                    interface_name, *_ = (node['provision_interface'].split(' ') + [None])
                    # we skim off parts that we added for clarity in above section
                    # (e.g. (default)). also works if there's no additional info
                    if interface['interface'] == interface_name and interface['network']:
                        # if it is my prov interface then it will get that domain as a FQDN.
                        node['hostname'] = nodename + '.' + interface['network']
                    if not interface['options']:
                        del interface['options']
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
            self.logger.info(f'Provided details for node {name}.')
            status = True
        else:
            self.logger.error(f'Node {name} is not available.')
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
            # 'localinstall': False,
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
            if node:
                nodeid = node[0]['id']
                if 'newnodename' in data: # is mentioned as newhostname in design documents!
                    nodename_new = data['newnodename']
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
                    return status, 'newnodename is only allowed while update, rename or clone a node'
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
            checks = {'bmcsetup': False, 'group': True, 'osimage': False, 'switch': False}
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
                        osimagetagids = Database().get_record_join(['osimagetag.id'],['osimagetag.osimageid=group.osimageid','group.id=node.groupid'],[f"node.name='{name}'",f"osimagetag.name='{osimagetag}'"])
                    if osimagetagids:
                        data['osimagetagid'] = osimagetagids[0]['id']
                    else:
                        status = False
                        return status, f'Unknown tag or osimage and tag not related'

            node_columns = Database().get_columns('node')
            columns_check = Helper().compare_list(data, node_columns)
            if columns_check:
                if update:
                    where = [{"column": "id", "value": nodeid}]
                    row = Helper().make_rows(data)
                    Database().update('node', row, where)
                    response = f'Node {name} updated successfully'
                    status = True
                    if node and len(node)>0 and 'groupid' in node[0] and 'groupid' not in data:
                        data['groupid'] = node[0]['groupid']
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
                    Interface().update_node_group_interface(nodeid=nodeid, group=data['groupid'])
                    """
                        # ----> GROUP interface. WIP. pending. should work but i keep it WIP
                        group_interfaces = Database().get_record_join(
                            [
                                'groupinterface.interface',
                                'network.name as network',
                                'groupinterface.options'
                            ],
                            ['network.id=groupinterface.networkid'],
                            [f"groupinterface.groupid={data['groupid']}"]
                        )
                        if group_interfaces:
                            for group_interface in group_interfaces:
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
                    """

                if interfaces:
                    result, message = Interface().change_node_interface(nodeid=nodeid, data=interfaces)
                    if result is False:
                        status = False
                        return status, f'{message}'

                # For now i have the below two disabled. it's testing. -Antoine aug 8 2023
                #Service().queue('dhcp', 'restart')
                #Service().queue('dns', 'restart')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_update__')
                Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_update__')

                # ---- we call the node plugin - maybe someone wants to run something after create/update?
                ret, enclosed_node_details = self.get_node(cli=False, name=name)
                node_details=None
                if ret is True:
                    if 'config' in enclosed_node_details.keys():
                        if 'node' in enclosed_node_details['config'].keys():
                            if name in enclosed_node_details['config']['node']:
                                node_details=enclosed_node_details['config']['node'][name]
                    if node_details:
                        node_plugins = Helper().plugin_finder(f'{self.plugins_path}/node')
                        NodePlugin=Helper().plugin_load(node_plugins,'node','default')
                        try:
                            if create:
                                NodePlugin().postcreate(name=name, group=node_details['group'])
                            elif update:
                                NodePlugin().postupdate(name=name, group=node_details['group'])
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
                node_interfaces = Database().get_record_join(
                    [
                        'nodeinterface.interface',
                        'ipaddress.ipaddress',
                        'nodeinterface.macaddress',
                        'network.name as network',
                        'nodeinterface.options'
                    ],
                    ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
                )
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
                        macaddress, network, options = None, None, None
                        if 'macaddress' in interface.keys():
                            macaddress = interface['macaddress']
                        if 'options' in interface.keys():
                            options = interface['options']
                        result, message = Config().node_interface_config(
                            new_nodeid,
                            interface_name,
                            macaddress,
                            options
                        )
                        if result and 'ipaddress' in interface.keys():
                            ipaddress = interface['ipaddress']
                            if 'network' in interface.keys():
                                network = interface['network']
                            result, message = Config().node_interface_ipaddress_config(
                                new_nodeid,
                                interface_name,
                                ipaddress,
                                network
                            )
                        if result is False:
                            status=False
                            return status, f'{message}'

                for node_interface in node_interfaces:
                    interface_name = node_interface['interface']
                    interface_options = node_interface['options']
                    result, message = Config().node_interface_config(
                        new_nodeid,
                        interface_name,
                        None,
                        interface_options
                    )
                    if result and 'ipaddress' in node_interface.keys():
                        if 'network' in node_interface.keys():
                            networkname = node_interface['network']
                            ips = Config().get_all_occupied_ips_from_network(networkname)
                            where = f' WHERE `name` = "{networkname}"'
                            network = Database().get_record(None, 'network', where)
                            if network:
                                ret, avail = 0, None
                                max_count = 5
                                # we try to ping for X ips, if none of these are free, something
                                # else is going on (read: rogue devices)....
                                while(max_count>0 and ret!=1):
                                    avail = Helper().get_available_ip(
                                        network[0]['network'],
                                        network[0]['subnet'],
                                        ips
                                    )
                                    ips.append(avail)
                                    _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                    max_count -= 1

                                if avail:
                                    result, message = Config().node_interface_ipaddress_config(
                                        new_nodeid,
                                        interface_name,
                                        avail,
                                        networkname
                                    )
                                    if result is False:
                                        status=False
                                        return status, f'{message}'
                # Service().queue('dhcp','restart')
                # do we need dhcp restart? MAC is wiped on new NIC so no real need i guess. pending
                #Service().queue('dns','restart')
            	#Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_clone__')
                Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_clone__')
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_node(self, name=None):
        """
        This method will delete a node.
        """
        status=False
        response="Internal error"
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            nodeid = node[0]['id']
            Database().delete_row('node', [{"column": "name", "value": name}])
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
            # for now i have disabled the below two lines for testing purposes. Antoine Aug 8 2023
            #Service().queue('dns', 'restart')
            #Service().queue('dhcp', 'restart')
            # below might look redundant but is added to prevent a possible race condition
            # when many nodes are added in a loop.
            # the below tasks ensures that even the last node will be included in dhcp/dns
            Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_delete__')
            Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_delete__')
            response = f'Node {name} with all its interfaces removed'
            status=True
        else:
            response = f'Node {name} not present in database'
            status=False
        return status, response
