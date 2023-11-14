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
This file is the entry point for provisioning
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


import datetime
import jinja2
import jwt
#from flask import abort
from base64 import b64decode, b64encode
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.service import Service
from utils.config import Config
from common.constant import CONSTANT
from base.node import Node

try:
    from plugins.boot.detection.switchport import Plugin as DetectionPlugin
except ImportError as import_error:
    LOGGER = Log.get_logger()
    LOGGER.error(f"Problems encountered while loading detection plugin: {import_error}")

class Boot():
    """
    This class is responsible to provide all boot templates.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIR"]
        self.boot_plugins = Helper().plugin_finder(f'{plugins_path}/boot')
        self.osimage_plugins = Helper().plugin_finder(f'{plugins_path}/osimage')
        # self.detection_plugins = Helper().plugin_finder(f'{plugins_path}/detection')
        # self.DetectionPlugin=Helper().plugin_load(self.detection_plugins,'detection','switchport')


    def default(self):
        """
        This method will provide a default ipxe template.
        """
        status=False
        template = 'templ_boot_ipxe.cfg'
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        controller = Database().get_record_join(
            ['controller.*','ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"','controller.hostname="controller"']
        )
        if controller:
            ipaddress = controller[0]['ipaddress']
            serverport = controller[0]['serverport']
            protocol = CONSTANT['API']['PROTOCOL']
            verify_certificate = CONSTANT['API']['VERIFY_CERTIFICATE']
            webserver_port = serverport
            webserver_protocol = protocol
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    webserver_port = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    webserver_protocol = CONSTANT['WEBSERVER']['PROTOCOL']

            nodes, available_nodes = [], []
            all_nodes = Database().get_record(None, 'node')
            most_nodes = Database().get_record_join(
                ['node.name', 'nodeinterface.macaddress'],
                ['nodeinterface.nodeid=node.id'],
                ["nodeinterface.interface='BOOTIF'"]
            )  # BOOTIF is not entirely true but for now it will do. pending
            all_nodes = most_nodes + all_nodes
            checked = []
            if all_nodes:
                for node in all_nodes:
                    if node['name'] not in checked:
                        checked.append(node['name'])
                        nodes.append(node['name'])
                        if (not 'macaddress' in node) or (not node['macaddress']):
                            available_nodes.append(node['name'])

            groups = []
            all_groups = Database().get_record_join(['group.name'], ['osimage.id=group.osimageid'])
            if all_groups:
                for group in all_groups:
                    groups.append(group['name'])
            status=True
        else:
            self.logger.error(f"configuration error: No controller available or missing network for controller")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            ipaddress, serverport = '', ''
            status=False
        self.logger.info(f'Boot API serving the {template}')
        response = {
            'template': template,
            'LUNA_CONTROLLER': ipaddress,
            'LUNA_API_PORT': serverport,
            'WEBSERVER_PORT': webserver_port,
            'LUNA_API_PROTOCOL': protocol,
            'WEBSERVER_PROTOCOL': webserver_protocol,
            'VERIFY_CERTIFICATE': verify_certificate,
            'NODES': nodes,
            'AVAILABLE_NODES': available_nodes,
            'GROUPS': groups
        }
        return status, response


    def boot_short(self):
        """
        This method will provide a boot short ipxe template.
        """
        status=False
        template = 'templ_boot_ipxe_short.cfg'
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            ipaddress = controller[0]['ipaddress']
            serverport = controller[0]['serverport']
            protocol = CONSTANT['API']['PROTOCOL']
            verify_certificate = CONSTANT['API']['VERIFY_CERTIFICATE']
            webserver_protocol = protocol
            webserver_port = serverport
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    webserver_port = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    webserver_protocol = CONSTANT['WEBSERVER']['PROTOCOL']
            status=True
        else:
            self.logger.error(f"configuration error: No controller available or missing network for controller")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            ipaddress, serverport = '', ''
            status=False
        self.logger.info(f'Boot API serving the {template}')
        response = {
            'template': template,
            'LUNA_CONTROLLER': ipaddress,
            'LUNA_API_PORT': serverport,
            'WEBSERVER_PORT': webserver_port,
            'LUNA_API_PROTOCOL': protocol,
            'VERIFY_CERTIFICATE': verify_certificate,
            'WEBSERVER_PROTOCOL': webserver_protocol
        }
        return status, response


    def boot_disk(self):
        """
        This method will provide a boot disk ipxe template.
        """
        status=False
        template = 'templ_boot_disk.cfg'
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            ipaddress = controller[0]['ipaddress']
            serverport = controller[0]['serverport']
            status=True
        else:
            self.logger.error(f"configuration error: No controller available or missing network for controller")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            ipaddress, serverport = '', ''
            status=False
        self.logger.info(f'Boot API serving the {template}')
        response = {'template': template, 'LUNA_CONTROLLER': ipaddress, 'LUNA_API_PORT': serverport}
        return status, response


    def discover_mac(self, mac=None):
        """
        This method will provide a node boot ipxe template, but search for mac address first.
        """
        status=False
        template = 'templ_nodeboot.cfg'
        data = {
            'template'      : template,
            'mac'           : mac,
            'nodeid'        : None,
            'osimageid'     : None,
            'ipaddress'     : None,
            'network'       : None,
            'gateway'       : None,
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['verify_certificate'] = CONSTANT['API']['VERIFY_CERTIFICATE']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        if mac:
            mac = mac.lower()
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress','network.name as network'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            data['ipaddress'] = controller[0]['ipaddress']
            data['network'] = controller[0]['network']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")
        nodeinterface = Database().get_record_join(
            ['nodeinterface.nodeid', 'nodeinterface.interface', 'ipaddress.ipaddress',
            'network.name as network', 'network.network as networkip', 'network.subnet', 'network.gateway'],
            ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
        )
        if nodeinterface:
            data['nodeid'] = nodeinterface[0]['nodeid']
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
            if nodeinterface[0]['network'] == data['network']: # node on default network
                data['gateway'] = ''
            else:
                data['gateway'] = nodeinterface[0]['gateway'] or ''
        else:
          # --------------------- port detection ----------------------------------
            try:
                result = DetectionPlugin().find(macaddress=mac)
                if (isinstance(result, bool) and result is True) or (isinstance(result, tuple) and result[0] is True and len(result)>2):
                    switch = result[1]
                    port = result[2]
                    self.logger.info(f"detected {mac} on: [{switch}] : [{port}]")
                    detect_node = Database().get_record_join(
                        ['node.*'],
                        ['switch.id=node.switchid'],
                        [f'switch.name="{switch}"', f'node.switchport = "{port}"']
                    )
                    if detect_node:
                        row = [{"column": "macaddress", "value": mac}]
                        where = [
                            {"column": "nodeid", "value": detect_node[0]["id"]},
                            {"column": "interface", "value": "BOOTIF"}
                            ]
                        Database().update('nodeinterface', row, where)
                        nodeinterface = Database().get_record_join(
                            ['nodeinterface.nodeid', 'nodeinterface.interface',
                             'ipaddress.ipaddress', 'network.name as network', 'network.gateway',
                             'network.network as networkip', 'network.subnet'],
                            [
                                'network.id=ipaddress.networkid',
                                'ipaddress.tablerefid=nodeinterface.id'
                            ],
                            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
                        )
                        if nodeinterface:
                            data['nodeid'] = nodeinterface[0]['nodeid']
                            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                            if nodeinterface[0]['network'] == data['network']: # node on default network
                                data['gateway'] = ''
                            else:
                                data['gateway'] = nodeinterface[0]['gateway'] or ''
                            Service().queue('dhcp', 'restart')
            except Exception as exp:
                self.logger.info(f"port detection call in boot returned: {exp}")
            # ------------- port detection was not successfull, lets try a last resort -----------------
            # ------------------ "don't nag give me the next node" detection ---------------------------
            if not data['nodeid']:
                createnode_ondemand, nextnode_discover = None, None
                cluster = Database().get_record(None, 'cluster')
                if cluster:
                    if 'createnode_ondemand' in cluster[0]:
                        createnode_ondemand=Helper().bool_revert(cluster[0]['createnode_ondemand'])
                    if 'nextnode_discover' in cluster[0]:
                        nextnode_discover=Helper().bool_revert(cluster[0]['nextnode_discover'])
                if nextnode_discover:
                    # then we fetch a list of all nodes that we have, with or without interface config
                    list1 = Database().get_record_join(
                        ['node.*', 'group.name as groupname', 'group.provision_interface as group_provision_interface',
                        'nodeinterface.interface', 'nodeinterface.macaddress'],
                        ['nodeinterface.nodeid=node.id','group.id=node.groupid']
                    )
                    list2 = Database().get_record_join(
                        ['node.*', 'group.name as groupname'],
                        ['group.id=node.groupid']
                    )
                    node_list = list1 + list2

                    checked = []
                    if node_list:
                        # we already have some nodes in the list. let's see if we can re-use
                        for node in node_list:
                            if node['name'] not in checked:
                                checked.append(node['name'])
                                if 'interface' in node and 'macaddress' in node and not node['macaddress']:
                                    # mac is empty. candidate!
                                    provision_interface = node['provision_interface'] or node['group_provision_interface'] or 'BOOTIF'
                                    result, _ = Config().node_interface_config(
                                        node['id'],
                                        provision_interface,
                                        mac
                                    )
                                    break

                        nodeinterface = Database().get_record_join(
                            ['nodeinterface.nodeid', 'nodeinterface.interface',
                             'ipaddress.ipaddress', 'network.name as network', 'network.gateway',
                             'network.network as networkip', 'network.subnet'],
                            ['network.id=ipaddress.networkid',
                             'ipaddress.tablerefid=nodeinterface.id'],
                            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
                        )
                        if nodeinterface:
                            data['nodeid'] = nodeinterface[0]['nodeid']
                            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                            if nodeinterface[0]['network'] == data['network']: # node on default network
                                data['gateway'] = ''
                            else:
                                data['gateway'] = nodeinterface[0]['gateway'] or ''
                            Service().queue('dhcp', 'restart')
        # -----------------------------------------------------------------------
        if data['nodeid']:
            node = Database().get_record_join(
                ['node.*','group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid'],
                ['group.id=node.groupid'],
                [f'node.id={data["nodeid"]}']
            )
            if node:
                data['osimagetagid'] = node[0]['osimagetagid'] or node[0]['grouposimagetagid'] or 'default'
                data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
                data['nodename'] = node[0]['name']
                # data['nodehostname'] = node[0]['hostname']
                data['nodehostname'] = node[0]['name'] # + fqdn - pending
                data['nodeservice'] = node[0]['service']
        if data['osimageid']:
            osimage = None
            data['kerneloptions']=""
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']
                if ('kerneloptions' in osimage[0]) and (osimage[0]['kerneloptions']):
                    data['kerneloptions'] = osimage[0]['kerneloptions']
                    regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
                    if regex.match(data['kerneloptions']):
                        data = b64decode(data['kerneloptions'])
                        data['kerneloptions'] = data.decode("ascii")
                    data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if None not in data.values():
            status=True
            Helper().update_node_state(data["nodeid"], "installer.discovery")
            # reintroduced below section as if we serve files through
            # e.g. nginx, we won't update anything
            row = [{"column": "status", "value": "installer.discovery"}]
            where = [{"column": "id", "value": data['nodeid']}]
            Database().update('node', row, where)
        else:
            for key, value in data.items():
                if value is None:
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this mac address.')
            status=False
            return status, "No config available"
            #self.logger.info(f'template mac search data: {data}')
        self.logger.info(f'Boot API serving the {template}')
        return status, data


    def discover_group_mac(self, groupname=None, mac=None):
        """
        This method will provide a node boot ipxe template, but search for first available
        node in the chosen group.
        """
        status=False
        template = 'templ_nodeboot.cfg'
        data = {
            'template'      : template,
            'mac'           : mac,
            'nodeid'        : None,
            'osimageid'     : None,
            'ipaddress'     : None,
            'network'       : None,
            'gateway'       : None,
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['verify_certificate'] = CONSTANT['API']['VERIFY_CERTIFICATE']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        if mac:
            mac = mac.lower()
        network, createnode_ondemand = None, None # used below

        # get controller and cluster info
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress', 'network.name as network'],
            ['ipaddress.tablerefid=controller.id', 'network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            data['network'] = controller[0]['network']
            data['ipaddress'] = controller[0]['ipaddress']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
            where = f" WHERE id='{controller[0]['clusterid']}'"
            cluster = Database().get_record(None, 'cluster', where)
            if cluster and 'createnode_ondemand' in cluster[0]:
                createnode_ondemand=Helper().bool_revert(cluster[0]['createnode_ondemand'])
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")
        # clear mac if it already exists. let's check
        nodeinterface_check = Database().get_record_join(
            ['nodeinterface.nodeid as nodeid', 'nodeinterface.interface'],
            ['nodeinterface.nodeid=node.id'],
            [f'nodeinterface.macaddress="{mac}"']
        )
        if nodeinterface_check:
            # this means there is already a node with this mac.
            # though we shouldn't, we will remove the other node's MAC so we can proceed
            self.logger.warning(f"node with id {nodeinterface_check[0]['nodeid']} will have its MAC cleared and this <to be declared>-node will use MAC {mac}")
            row = [{"column": "macaddress", "value": ""}]
            where = [{"column": "macaddress", "value": mac}]
            Database().update('nodeinterface', row, where)

        # then we fetch a list of all nodes that we have, with or without interface config
        list1 = Database().get_record_join(
            ['node.*', 'group.name as groupname', 'group.provision_interface',
            'nodeinterface.interface', 'nodeinterface.macaddress'],
            ['nodeinterface.nodeid=node.id','group.id=node.groupid']
        )
        list2 = Database().get_record_join(
            ['node.*', 'group.name as groupname'],
            ['group.id=node.groupid']
        )
        node_list = list1 + list2

        # general group info and details. needed below
        group_details = Database().get_record(None,'group',f" WHERE name='{groupname}'")
        provision_interface = 'BOOTIF'
        if group_details and 'provision_interface' in group_details[0] and group_details[0]['provision_interface']:
            provision_interface = str(group_details[0]['provision_interface'])

        # first we generate a list of taken ips. we might need it later
        ips = []
        if data['network']:
            network = Database().get_record_join(
                ['ipaddress.ipaddress', 'network.network', 'network.subnet'],
                ['network.id=ipaddress.networkid'],
                [f"network.name='{data['network']}'"]
            )
            if network:
                for network_ip in network:
                    ips.append(network_ip['ipaddress'])

        hostname = None # we use it further down below.
        checked = []
        example_node = None
        new_nodename = None
        if (not node_list) or (createnode_ondemand is True):
            # we have no spare or free nodes in here -or- we create one on demand.
            if list2:
                # we fetch the node with highest 'number' - sort
                names = []
                for node in list2:
                    names.append(node['name'])
                names.sort(reverse=True)
                example_node = names[0]
                ename = example_node.rstrip('0123456789')
                # this assumes a convention like <name><number> as node name
                enumber = example_node[len(ename):]
                if ename and enumber:
                    new_enumber = str(int(enumber) + 1)
                    new_enumber = new_enumber.zfill(len(enumber))
                    new_nodename = f"{ename}{new_enumber}"
                elif ename:
                    new_enumber = '001'
                    new_nodename = f"{ename}{new_enumber}"
                else:
                    # we have to create a name ourselves
                    new_nodename = f"{groupname}001"
            else:
                # we have to create a name ourselves
                new_nodename = f"{groupname}001"
            self.logger.info(f"Group boot intelligence: we came up with the following node name: [{new_nodename}]")
            if group_details:
                # Antoine aug 15 2023
                ret,message = None, None
                if new_nodename:
                    if example_node:
                        newnodedata = {'config': {'node': {example_node: {}}}}
                        newnodedata['config']['node'][example_node]['newnodename'] = new_nodename
                        newnodedata['config']['node'][example_node]['name'] = example_node
                        newnodedata['config']['node'][example_node]['group'] = groupname # groupname is given through API call
                        ret, message = Node().clone_node(example_node,newnodedata)
                        self.logger.info(f"Group select boot: Cloning {example_node} to {new_nodename}: ret = [{ret}], message = [{message}]")
                    else:
                        newnodedata = {'config': {'node': {new_nodename: {}}}}
                        newnodedata['config']['node'][new_nodename]['name'] = new_nodename
                        newnodedata['config']['node'][new_nodename]['group'] = groupname # groupname is given through API call
                        ret, message = Node().update(new_nodename,newnodedata)
                        self.logger.info(f"Group select boot: Creating {new_nodename}: ret = [{ret}], message = [{message}]")
                    if ret is True:
                        hostname = new_nodename
                        nodeid = Database().id_by_name('node', new_nodename)
                        ret, _ = Config().node_interface_config(nodeid, provision_interface, mac)
        else:
            # we already have some nodes in the list. let's see if we can re-use
            for node in node_list:
                if node['name'] not in checked:
                    checked.append(node['name'])
                    if 'interface' in node and 'macaddress' in node and not node['macaddress']:
                        # mac is empty. candidate!
                        hostname = node['name']
                        result, _ = Config().node_interface_config(
                            node['id'],
                            provision_interface,
                            mac
                        )
                        break

#                    Below section commented out as it not really up to use to create interface
#                    for nodes if they are not configured. We better just use what's valid and ok
#                    We could also ditch list2 from above if we want - Antoine
#
#                    elif not 'interface' in node and data['network']:
#                        # node is there but no interface. we'll take it!
#                        hostname = node['name']
#                        # we need to pick the current network in a smart way. we assume
#                        # the default network where controller is in as well
#                        avail_ip = Helper().get_available_ip(
#                            network[0]['network'],
#                            network[0]['subnet'],
#                            ips
#                        )
#                        result, _ = Config().node_interface_config(
#                            node['id'],
#                            provision_interface,
#                            mac
#                        )
#                        if result:
#                            result, _ = Config().node_interface_ipaddress_config(
#                                node['id'],
#                                provision_interface,
#                                avail_ip,
#                                data['network']
#                            )
#                            Service().queue('dns','restart')
#                        break

        if not hostname:
            # we bail out because we could not re-use a node or create one.
            # something above did not work out.
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this group.')
            status = False
            return status, 'No Node is available for this group'

        # we update the groupid of the node. this is actually only really
        # needed if we re-use a node (unassigned)
        if group_details:
            row = [{"column": "groupid", "value": group_details[0]['id']}]
            where = [{"column": "name", "value": hostname}]
            Database().update('node', row, where)

        # below here is almost identical to a manual node selection boot -----------------

        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid'],
            ['group.id=node.groupid'],
            [f'node.name="{hostname}"']
        )
        if node:
            data['osimagetagid'] = node[0]['osimagetagid'] or node[0]['grouposimagetagid'] or 'default'
            data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
            data['nodename'] = node[0]['name']
            # data['nodehostname'] = node[0]['hostname']
            data['nodehostname'] = node[0]['name'] # + fqdn ?
            data['nodeservice'] = node[0]['service']
            data['nodeid'] = node[0]['id']

        if data['nodeid']:
            Service().queue('dhcp','restart')
            nodeinterface = Database().get_record_join(
                [
                    'nodeinterface.nodeid',
                    'nodeinterface.interface',
                    'nodeinterface.macaddress',
                    'ipaddress.ipaddress',
                    'network.name as network',
                    'network.network as networkip',
                    'network.subnet',
                    'network.gateway'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{data['nodeid']}'",
                    f'nodeinterface.macaddress="{mac}"'
                ]
            )
            if nodeinterface:
                data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                if nodeinterface[0]['network'] == data['network']: # node on default network
                    data['gateway'] = ''
                else:
                    data['gateway'] = nodeinterface[0]['gateway'] or ''
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = None
            data['kerneloptions']=""
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']
                if ('kerneloptions' in osimage[0]) and (osimage[0]['kerneloptions']):
                    data['kerneloptions'] = osimage[0]['kerneloptions']
                    regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
                    if regex.match(data['kerneloptions']):
                        data = b64decode(data['kerneloptions'])
                        data['kerneloptions'] = data.decode("ascii")
                    data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if None not in data.values():
            status=True
            Helper().update_node_state(data["nodeid"], "installer.discovery")
            # reintroduced below section as if we serve files through e.g. nginx, we won't update
            row = [{"column": "status", "value": "installer.discovery"}]
            where = [{"column": "id", "value": data['nodeid']}]
            Database().update('node', row, where)
        else:
            for key, value in data.items():
                if value is None:
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this mac address.')
            status=False
        self.logger.info(f'Boot API serving the {template}')
        return status, data


    def discover_hostname_mac(self, hostname=None, mac=None):
        """
        This method will provide a node boot ipxe template, but search for hostname.
        """
        status=False
        template = 'templ_nodeboot.cfg'
        data = {
            'template'      : template,
            'mac'           : mac,
            'nodeid'        : None,
            'osimageid'     : None,
            'ipaddress'     : None,
            'network'       : None,
            'gateway'       : None,
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['verify_certificate'] = CONSTANT['API']['VERIFY_CERTIFICATE']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        # Antoine
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress', 'network.name as network'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"','controller.hostname="controller"']
        )
        if controller:
            data['network'] = controller[0]['network']
            data['ipaddress'] = controller[0]['ipaddress']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")

        # we probably have to cut the fqdn off of hostname?
        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid'],
            ['group.id=node.groupid'],
            [f'node.name="{hostname}"']
        )
        if node:
            data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
            data['osimagetagid'] = node[0]['osimagetagid'] or node[0]['grouposimagetagid'] or 'default'
            data['nodename'] = node[0]['name']
            # data['nodehostname'] = node[0]['hostname']
            data['nodehostname'] = node[0]['name'] # + fqdn ?
            data['nodeservice'] = node[0]['service']
            data['nodeid'] = node[0]['id']
        if data['nodeid']:
            we_need_dhcpd_restart = False
            nodeinterface_check = Database().get_record_join(
                ['nodeinterface.nodeid as nodeid', 'nodeinterface.interface'],
                ['nodeinterface.nodeid=node.id'],
                [f'nodeinterface.macaddress="{mac}"']
            )
            if nodeinterface_check:
                # There is already a node with this mac. let's first check if it's our own.
                if nodeinterface_check[0]['nodeid'] != data['nodeid']:
                    # we are NOT !!! though we shouldn't, we will remove the other node's
                    # MAC and assign this mac to us.
                    # note to other developers: We hard assign a node's IP address
                    # (hard config inside image/node) we must be careful - Antoine
                    message = f"Node with id {nodeinterface_check[0]['nodeid']} "
                    message += f"will have its MAC cleared and node {hostname} with "
                    message += f"id {data['nodeid']} will use MAC {mac}"
                    self.logger.warning(message)
                    row = [{"column": "macaddress", "value": ""}]
                    where = [
                        {"column": "nodeid", "value": nodeinterface_check[0]['nodeid']},
                        {"column": "interface", "value": nodeinterface_check[0]['interface']}
                    ]
                    Database().update('nodeinterface', row, where)
                    row = [{"column": "macaddress", "value": mac}]
                    where = [
                        {"column": "nodeid", "value": data["nodeid"]},
                        {"column": "interface", "value": "BOOTIF"}
                    ]
                    Database().update('nodeinterface', row, where)
                    we_need_dhcpd_restart = True
            else:
                # we do not have anyone with this mac yet. we can safely move ahead.
                # BIG NOTE!: This is being done without token! By itself not a threat
                # but some someone could mess up node/interface configs.
                # The alternative would be to use IP from dhcp pool and set MAC after
                # the node has a token. This again will break things where a node is
                # using dhcp as bootproto. e.g. a manual override inside an image. -Antoine
                row = [{"column": "macaddress", "value": mac}]
                where = [
                    {"column": "nodeid", "value": data["nodeid"]},
                    {"column": "interface", "value": "BOOTIF"}
                ]
                Database().update('nodeinterface', row, where)
                we_need_dhcpd_restart = True

            if we_need_dhcpd_restart is True:
                Service().queue('dhcp', 'restart')
            nodeinterface = Database().get_record_join(
                [
                    'nodeinterface.nodeid',
                    'nodeinterface.interface',
                    'nodeinterface.macaddress',
                    'ipaddress.ipaddress',
                    'network.name as network',
                    'network.network as networkip',
                    'network.subnet',
                    'network.gateway'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{data['nodeid']}'",
                    f'nodeinterface.macaddress="{mac}"'
                ]
            )
            if nodeinterface:
                data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                if nodeinterface[0]['network'] == data['network']: # node on default network
                    data['gateway'] = ''
                else:
                    data['gateway'] = nodeinterface[0]['gateway'] or ''
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = None
            data['kerneloptions']=""
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']
                if ('kerneloptions' in osimage[0]) and (osimage[0]['kerneloptions']):
                    data['kerneloptions'] = osimage[0]['kerneloptions']
                    regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
                    if regex.match(data['kerneloptions']):
                        data = b64decode(data['kerneloptions'])
                        data['kerneloptions'] = data.decode("ascii")
                    data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if None not in data.values():
            status=True
            Helper().update_node_state(data["nodeid"], "installer.discovery")
            # reintroduced below section as if we serve files through e.g. nginx, we won't update
            row = [{"column": "status", "value": "installer.discovery"}]
            where = [{"column": "id", "value": data['nodeid']}]
            Database().update('node', row, where)
        else:
            for key, value in data.items():
                if value is None:
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this mac address.')
            status=False
            return status, "No config available"
        self.logger.info(f'Boot API serving the {template}')
        return status, data


    def install(self, node=None):
        """
        This method will provide a install ipxe template for a node.
        """
        status=False
        template = 'templ_install.cfg'
        data = {
            'template'              : template,
            'nodeid'                : None,
            'group'                 : None,
            'ipaddress'             : None,
            'serverport'            : None,
            'nodehostname'          : None,
            'osimagename'           : None,
            'imagefile'             : None,
            'selinux'               : None,
            'setupbmc'              : None,
            'localinstall'          : None,
            'unmanaged_bmc_users'   : None,
            'systemroot'            : None,
            'interfaces'            : {},
            'bmc'                   : {}
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['verify_certificate'] = CONSTANT['API']['VERIFY_CERTIFICATE']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'

        with open(template_path, 'r', encoding='utf-8') as file:
            template_data = file.read()

        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            data['selinux']      = Helper().bool_revert(cluster[0]['security'])
            data['cluster_provision_method']   = cluster[0]['provision_method']
            data['cluster_provision_fallback'] = cluster[0]['provision_fallback']
            data['name_server'] = cluster[0]['nameserver_ip']
            data['ntp_server']  = cluster[0]['ntp_server']
        # Antoine
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            data['ipaddress']   = controller[0]['ipaddress']
            data['serverport']  = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")
        
        items = {
            'setupbmc': False,
            'netboot': False,
            'localinstall': False,
            'bootmenu': False,
            'unmanaged_bmc_users': 'skip',
        }
        ret, enclosed_node_details = Node().get_node(cli=False, name=node)
        node_details=None
        if ret is True:
            if 'config' in enclosed_node_details.keys():
                if 'node' in enclosed_node_details['config'].keys():
                    if node in enclosed_node_details['config']['node']:
                        node_details=enclosed_node_details['config']['node'][node]
            if not node_details:
                status = False
                return status, "i received data back internally that i could not parse"
            self.logger.debug(f"DEBUG: {node_details}")
            for item in ['provision_method','provision_fallback','prescript','partscript','postscript',
                         'netboot','localinstall','bootmenu','provision_interface','unmanaged_bmc_users',
                         'name','setupbmc','bmcsetup','group','osimage','osimagetag']:
                if item in items and isinstance(items[item], bool):
                    if node_details[item] is None or node_details[item] == 'None':
                        data[item]=False
                    else:
                        data[item] = Helper().make_bool(node_details[item])
                else:
                    data[item] = node_details[item]
            # though None is perfectly valid, the check below doesn't like it. - Antoine Aug 15 2023
            if data['unmanaged_bmc_users'] is None:
                data['unmanaged_bmc_users'] = items['unmanaged_bmc_users']
            data['nodeid'] = Database().id_by_name('node', node)             # we need this for node status update
            data['nodename']            = node_details['name']
            data['nodehostname']        = node_details['hostname']
        else:
            status = False
            return status, "This node does not seem to exist"

        if data['setupbmc'] is True and data['bmcsetup']:
            bmcsetup = Database().get_record(None, 'bmcsetup', " WHERE name = '"+data['bmcsetup']+"'")
            if bmcsetup:
                data['bmc'] = {}
                data['bmc']['userid'] = bmcsetup[0]['userid']
                data['bmc']['username'] = bmcsetup[0]['username']
                data['bmc']['password'] = bmcsetup[0]['password']
                data['bmc']['netchannel'] = bmcsetup[0]['netchannel']
                data['bmc']['mgmtchannel'] = bmcsetup[0]['mgmtchannel']
#                data['unmanaged_bmc_users'] = bmcsetup[0]['unmanaged_bmc_users'] # supposedly covered by Node().get_node
            else:
                data['setupbmc'] = False

        data['osrelease'] = 'default'
        data['distribution'] = 'redhat'
        if data['osimage']:
            osimage = None
            if data['osimagetag'] and data['osimagetag'] != 'default':
                osimage = Database().get_record_join(['osimage.*','osimagetag.imagefile'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.name="{data["osimagetag"]}"',f'osimage.name="{data["osimage"]}"'])
            else:
                osimage = Database().get_record(None, 'osimage', f" WHERE name = '{data['osimage']}'")
            if osimage:
                data['osimageid'] = osimage[0]['id']
                data['osimagename'] = osimage[0]['name']
                data['imagefile'] = osimage[0]['imagefile']
                data['distribution'] = osimage[0]['distribution'] or 'redhat'
                data['distribution'] = data['distribution'].lower()
                data['osrelease'] = osimage[0]['osrelease'] or 'default'

        if data['nodename']:
            nodeinterface = Database().get_record_join(
                [
                    'nodeinterface.nodeid',
                    'nodeinterface.interface',
                    'nodeinterface.macaddress',
                    'nodeinterface.options',
                    'ipaddress.ipaddress',
                    'network.name as network',
                    'network.network as networkip',
                    'network.subnet',
                    'network.gateway',
                    'network.gateway_metric',
                    'network.id as networkid',
                    'network.zone as zone',
                    'network.type as type'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id'],
                ['tableref="nodeinterface"', f"node.name='{data['nodename']}'"]
            )
            data['domain_search'] = ''
            domain_search = []
            if nodeinterface:
                for interface in nodeinterface:
                    node_nwk = f'{interface["ipaddress"]}/{interface["subnet"]}'
                    netmask = Helper().get_netmask(node_nwk)
                    if interface['interface'] == 'BMC':
                        # we configure bmc stuff here and no longer in template. big advantage is
                        # that we can have different networks/interface-names for different h/w,
                        # drivers, subnets, networks, etc
                        if 'bmc' in data:
                            data['bmc']['ipaddress'] = interface['ipaddress']
                            data['bmc']['netmask'] = netmask
                            data['bmc']['gateway'] = interface['gateway'] or '0.0.0.0'
                            # <---- not ipv6 compliant! pending
                    else:
                        # regular nic
                        data['interfaces'][interface['interface']] = {
                            'interface': interface['interface'],
                            'ipaddress': interface['ipaddress'],
                            'prefix': interface['subnet'],
                            'network': node_nwk,
                            'netmask': netmask,
                            'networkname': interface['network'],
                            'gateway': interface['gateway'],
                            'gateway_metric': interface['gateway_metric'] or "101",
                            'options': interface['options'] or "",
                            'zone': interface['zone'],
                            'type': interface['type'] or "ethernet"
                        }
                        domain_search.append(interface['network'])
                        if interface['interface'] == data['provision_interface'] and interface['network']:
                            # if it is my prov interface then it will get that domain as a FQDN.
                            data['nodehostname'] = data['nodename'] + '.' + interface['network']
                            domain_search.insert(0, interface['network'])
            if domain_search:
                data['domain_search'] = ','.join(domain_search)

        ## SYSTEMROOT
        osimage_plugin = Helper().plugin_load(self.osimage_plugins,'osimage/operations/image',data['distribution'],data['osrelease'])
        data['systemroot'] = str(osimage_plugin().systemroot or '/sysroot')

        ## FETCH CODE SEGMENT
        cluster_provision_methods = [data['provision_method'], data['provision_fallback']]

        for method in cluster_provision_methods:
            provision_plugin = Helper().plugin_load(self.boot_plugins, 'boot/provision', method)
            segment = str(provision_plugin().fetch)
            segment = f"function download_{method} {{\n{segment}\n}}\n## FETCH CODE SEGMENT"
            # self.logger.info(f"SEGMENT {method}:\n{segment}")
            template_data = template_data.replace("## FETCH CODE SEGMENT",segment)

        ## INTERFACE CODE SEGMENT
        network_plugin = Helper().plugin_load(
            self.boot_plugins,
            'boot/network',
            data['distribution'],
            data['osrelease']
        )
        segment = str(network_plugin().interface)
        template_data = template_data.replace("## INTERFACE CODE SEGMENT", segment)
        segment = str(network_plugin().hostname)
        template_data = template_data.replace("## HOSTNAME CODE SEGMENT", segment)
        segment = str(network_plugin().gateway)
        template_data = template_data.replace("## GATEWAY CODE SEGMENT", segment)
        segment = str(network_plugin().dns)
        template_data = template_data.replace("## DNS CODE SEGMENT", segment)
        segment = str(network_plugin().ntp)
        template_data = template_data.replace("## NTP CODE SEGMENT", segment)

        ## BMC CODE SEGMENT
        bmc_plugin = Helper().plugin_load(
            self.boot_plugins,
            'boot/bmc',
            [data['nodename'], data['group']]
        )
        segment = str(bmc_plugin().config)
        template_data = template_data.replace("## BMC CODE SEGMENT",segment)

        ## SCRIPT <PRE|PART|POST>SCRIPT CODE SEGMENT
        script_plugin = Helper().plugin_load(self.boot_plugins, 'boot/scripts',
                       [data['nodename'],data['group'],data['distribution']]
        )
        for script in ['prescript', 'partscript', 'postscript']:
            segment = ""
            match script:
                case 'prescript':
                    segment = str(script_plugin().prescript)
                case 'partscript':
                    segment = str(script_plugin().partscript)
                case 'postscript':
                    segment = str(script_plugin().postscript)
            template_data = template_data.replace(
                f"## SCRIPT {script.upper()} CODE SEGMENT",
                segment
            )

        if data['localinstall'] is True:
            ## SCRIPT LOCALINSTALL CODE SEGMENT
            localinstall_plugin = Helper().plugin_load(self.boot_plugins, 'boot/localinstall',
                       [data['nodename'],data['group'],data['distribution']]
            )
            segment = str(localinstall_plugin().grub)
            template_data = template_data.replace(
                f"## SCRIPT LOCALINSTALL CODE SEGMENT",
                segment
            )

        #self.logger.info(f"boot install data: [{data}]")
        if None not in data.values():
            status=True
            Helper().update_node_state(data["nodeid"], "installer.downloaded")
        else:
            for key, value in data.items():
                if value is None:
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this mac address.')
            status=False 

        data['template_data'] = template_data
        jwt_token = None
        try:
            api_key = CONSTANT['API']['SECRET_KEY']
            api_expiry = datetime.timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
            api_expiry = datetime.timedelta(minutes=int(60))
            expiry_time = datetime.datetime.utcnow() + api_expiry
            jwt_token = jwt.encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
        except Exception as exp:
            self.logger.info(f"Token creation error: {exp}")
        data['jwt_token'] = jwt_token
        return status, data
