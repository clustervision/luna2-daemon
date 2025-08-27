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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


import datetime
import jinja2
import jwt
import re
from jinja2.filters import FILTERS
from time import sleep
#from flask import abort
from base64 import b64decode, b64encode
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.service import Service
from utils.config import Config
from base.node import Node
from utils.journal import Journal
from utils.ha import HA
from utils.controller import Controller
from utils.boot import Boot as UBoot
from base.monitor import Monitor


# -------------------- custom Jinja filter to handle instream filtering -----------------------
def jinja_b64decode(value):
    """
    quick and dirty b64decode filter for jinja
    """
    b64decoded = None
    try:
        b64decoded = b64decode(value)
    except:
        b64decoded = value
    # ---
    try:
        return b64decoded.decode("ascii")
    except:
        try:
            return b64decoded.decode("utf-8")
        except:
            return b64decoded

FILTERS["b64decode"] = jinja_b64decode
# ----------------------------------------------------------------------------------------------


try:
    PLUGIN_PATH = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
    DETECTION_PLUGINS = Helper().plugin_finder(f'{PLUGIN_PATH}/boot/detection')
    SwitchDetectionPlugin = Helper().plugin_load(DETECTION_PLUGINS,'boot/detection','switchport')
    CloudDetectionPlugin = Helper().plugin_load(DETECTION_PLUGINS,'boot/detection','cloud')
except Exception as exp:
    LOGGER = Log.get_logger()
    LOGGER.error(f"Problems encountered while pre-loading detection plugins: {exp}")

class Boot():
    """
    This class is responsible to provide all boot templates.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.b64regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
        self.plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.boot_plugins = Helper().plugin_finder(f'{self.plugins_path}/boot')
        self.osimage_plugins = Helper().plugin_finder(f'{self.plugins_path}/osimage')
        self.controller_object = Controller()
        self.all_controllers = self.controller_object.get_controllers()
        self.controller_name = None
        self.controller_ip = None
        self.controller_ipv6 = None
        self.controller_ipv4 = None
        self.controller_beaconip = None
        self.controller_serverport = None
        self.controller_network = None
        self.controller_clusterid = None
        self.hatrial = 25
        self.ha_object = HA()
        self.insync = self.ha_object.get_insync()
        self.hastate = self.ha_object.get_hastate()
        if self.hastate is True and self.insync is True:
            self.controller_name=self.ha_object.get_me()
        for host in self.all_controllers.keys():
            controller = self.all_controllers[host]
            if controller['beacon']:
                if not self.controller_name:
                    self.controller_name = host
                    self.controller_ip = controller['ipaddress_ipv6'] or controller['ipaddress']
                    self.controller_serverport = controller['serverport']
                self.controller_beaconip = controller['ipaddress_ipv6'] or controller['ipaddress']
            if host == self.controller_name:
                self.controller_ip = controller['ipaddress_ipv6'] or controller['ipaddress']
                self.controller_ipv4 = controller['ipaddress']
                self.controller_ipv6 = controller['ipaddress_ipv6']
                self.controller_serverport = controller['serverport']
                self.controller_network = controller['network']
                self.controller_clusterid = controller['clusterid']
        self.logger.debug(f"BOOT: self.controller_name = {self.controller_name}, self.controller_ip = {self.controller_ip}, self.controller_beaconip = {self.controller_beaconip}")
        # fallbacks
        if not self.controller_name:
            self.logger.warning("possible configuration error: No controller available or missing network for controller. using defaults")
            self.controller_name = 'controller'


    def wait_for_insync(self,trial=25):
        while self.insync is False and trial>0:
            self.insync = self.ha_object.get_insync()
            trial-=1
            sleep(2)

    def clear_existing_mac(self, macaddress, exclude_nodeid=None):
        # clear mac if it already exists.
        where=[f'nodeinterface.macaddress="{macaddress}"']
        if exclude_nodeid:
            where.append(f"nodeinterface.nodeid!='{exclude_nodeid}'")
        nodeinterface_check = Database().get_record_join(
            ['nodeinterface.nodeid as nodeid', 'nodeinterface.interface'],
            ['nodeinterface.nodeid=node.id'],
            where
        )
        if nodeinterface_check:
            result = True
            for db_node in nodeinterface_check:
                self.logger.warning(f"node with id {db_node['nodeid']} will have its MAC {macaddress} cleared")
                if self.hastate is True:
                    self.wait_for_insync(self.hatrial)
                    payload = [{'interface': db_node['interface'], 'macaddress': ""}]
                    result, _ = Journal().add_request(function="Interface.change_node_interface",object=db_node['nodeid'],payload=payload)
                if result is True:
                    result, _ = Config().node_interface_config(
                        nodeid=db_node['nodeid'],
                        interface_name=db_node['interface'],
                        macaddress=""
                    )
            return result
        return True

    def find_next_suitable_node(self, groupname=None, nextnode=False, makeupname=False, macashost=False, mac=None):
        # then we fetch a list of all nodes that we have, with or without interface config
        example_node = None
        new_nodename = None
        example_node = None
        provision_interface = 'BOOTIF'

        # old/default behavior is to not be creative when we not do nextnode,
        # though some may say, i want to be creative while not looking up unused nodes,
        # but this would break legacy where createnode_ondemand is set to True by default
        if not nextnode:
            self.logger.info(f"suitable node: Bailing out as nextnode is False")
            return None, None, None

        if makeupname and macashost and mac:
            new_nodename = mac.replace('-','')
            new_nodename = new_nodename.replace(':','')
            return new_nodename, example_node, provision_interface

        where = None
        if groupname:
            where = [f"groupname = '{groupname}'"]

        list1 = Database().get_record_join(
            ['node.*', 'group.name as groupname', 'group.provision_interface as group_provision_interface',
             'nodeinterface.interface', 'nodeinterface.macaddress'],
            ['nodeinterface.nodeid=node.id','group.id=node.groupid'],
            where
        )
        list2 = Database().get_record_join(
            ['node.*', 'group.name as groupname', 'group.provision_interface as group_provision_interface'],
            ['group.id=node.groupid'],
            where
        )
        node_list = list1 + list2

        if nextnode and node_list:
            # we already have some nodes in the list. let's see if we can re-use
            checked = []
            for node in node_list:
                if node['name'] not in checked:
                    checked.append(node['name'])
                    if 'interface' in node and 'macaddress' in node and not node['macaddress']:
                        # mac is empty. candidate!
                        new_nodename = node['name']
                        provision_interface = node['provision_interface'] or node['group_provision_interface'] or 'BOOTIF'
                        break
        if makeupname and not new_nodename:
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
                elif groupname:
                    # we have to create a name ourselves
                    new_nodename = f"{groupname}001"
            elif groupname:
                # we have to create a name ourselves
                new_nodename = f"{groupname}001"
        return new_nodename, example_node, provision_interface


    def default(self):
        """
        This method will provide a default ipxe template.
        """
        status=False
        template = 'templ_boot_ipxe.cfg'
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "default boot template does not exist" }
            return False, faildata
        controller_ips=[]
        for controller in self.all_controllers.keys():
            if self.all_controllers[controller]['ipaddress_ipv6']:
                controller_ips.append(self.all_controllers[controller]['ipaddress_ipv6'])
            if self.all_controllers[controller]['ipaddress']:
                controller_ips.append(self.all_controllers[controller]['ipaddress'])
        if self.controller_name:
            protocol = CONSTANT['API']['PROTOCOL']
            verify_certificate = CONSTANT['API']['VERIFY_CERTIFICATE']
            webserver_port = self.controller_serverport
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
            self.logger.error(f"configuration error: No controller available or missing network for controller {self.controller_name}")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            status=False
        self.logger.info(f'Boot API serving {template}')
        response = {
            'template': template,
            'LUNA_LOGHOST': self.controller_beaconip,
            'LUNA_BEACON': self.controller_beaconip,
            'LUNA_CONTROLLER': self.controller_ip,
            'LUNA_CONTROLLERS': controller_ips,
            'LUNA_API_PORT': self.controller_serverport,
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
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "short boot template does not exist" }
            return False, faildata
        controller_ips=[]
        for controller in self.all_controllers.keys():
            if self.all_controllers[controller]['ipaddress_ipv6']:
                controller_ips.append(self.all_controllers[controller]['ipaddress_ipv6'])
            if self.all_controllers[controller]['ipaddress']:
                controller_ips.append(self.all_controllers[controller]['ipaddress'])
        if self.controller_name:
            protocol = CONSTANT['API']['PROTOCOL']
            verify_certificate = CONSTANT['API']['VERIFY_CERTIFICATE']
            webserver_port = self.controller_serverport
            webserver_protocol = protocol
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    webserver_port = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    webserver_protocol = CONSTANT['WEBSERVER']['PROTOCOL']
            status=True
        else:
            self.logger.error(f"configuration error: No controller available or missing network for controller {self.controller_name}")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            status=False
        self.logger.info(f'Boot API serving {template}')
        response = {
            'template': template,
            'LUNA_LOGHOST': self.controller_beaconip,
            'LUNA_BEACON': self.controller_beaconip,
            'LUNA_CONTROLLER': self.controller_ip,
            'LUNA_CONTROLLERS': controller_ips,
            'LUNA_API_PORT': self.controller_serverport,
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
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "disk boot template does not exist" }
            return False, faildata
        controller_ips=[]
        for controller in self.all_controllers.keys():
            if self.all_controllers[controller]['ipaddress_ipv6']:
                controller_ips.append(self.all_controllers[controller]['ipaddress_ipv6'])
            if self.all_controllers[controller]['ipaddress']:
                controller_ips.append(self.all_controllers[controller]['ipaddress'])
        if self.controller_name:
            protocol = CONSTANT['API']['PROTOCOL']
            verify_certificate = CONSTANT['API']['VERIFY_CERTIFICATE']
            webserver_port = self.controller_serverport
            webserver_protocol = protocol
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    webserver_port = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    webserver_protocol = CONSTANT['WEBSERVER']['PROTOCOL']
            status=True
        else:
            self.logger.error(f"configuration error: No controller available or missing network for controller {self.controller_name}")
            environment = jinja2.Environment()
            template = environment.from_string('No Controller is available.')
            status=False
        self.logger.info(f'Boot API serving {template}')
        response = {'template': template, 'LUNA_CONTROLLER': self.controller_ip,
                    'LUNA_CONTROLLERS': controller_ips,
                    'LUNA_API_PORT': self.controller_serverport,
                    'LUNA_BEACON': self.controller_beaconip}
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
            'loghost'       : self.controller_beaconip,
            'beacon'        : self.controller_beaconip,
            'protocol'      : CONSTANT['API']['PROTOCOL'],
            'verify_certificate': CONSTANT['API']['VERIFY_CERTIFICATE'],
            'webserver_protocol': CONSTANT['API']['PROTOCOL'],
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
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "node boot template does not exist" }
            return False, faildata
        if mac:
            mac = mac.lower()
        if self.controller_name:
            data['ipaddress'] = self.controller_ip
            data['network'] = self.controller_network
            data['serverport'] = self.controller_serverport
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        else:
            self.logger.warning("possible configuration error: No controller available or missing network for controller")
        nodeinterface = Database().get_record_join(
            ['nodeinterface.nodeid', 'nodeinterface.interface',
             'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp', 'network.dhcp as networkdhcp',
             'network.name as network', 'network.network as networkip', 'network.subnet', 'network.gateway',
             'network.network_ipv6 as networkip_ipv6', 'network.subnet_ipv6', 'network.gateway_ipv6'],
            ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
        )
        if nodeinterface:
            data['nodeid'] = nodeinterface[0]['nodeid']
            if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                data['nodeip'] = 'dhcp'
            elif nodeinterface[0]["ipaddress_ipv6"]:
                data['nodeip'] = f'{nodeinterface[0]["ipaddress_ipv6"]}/{nodeinterface[0]["subnet_ipv6"]}'
            else:
                data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
            if nodeinterface[0]["ipaddress_ipv6"]:
                data['gateway'] = nodeinterface[0]['gateway_ipv6'] or ''
            else:
                data['gateway'] = nodeinterface[0]['gateway'] or ''
        else:
          # --------------------- port detection ----------------------------------
            try:
                result = SwitchDetectionPlugin().find(macaddress=mac)
                if (isinstance(result, bool) and result is True) or (isinstance(result, tuple) and result[0] is True and len(result)>2):
                    switch = result[1]
                    port = result[2]
                    self.logger.info(f"detected {mac} on: [{switch}] + [{port}]")
                    detect_node = Database().get_record_join(
                        ['node.*'],
                        ['switch.id=node.switchid'],
                        [f'switch.name="{switch}"', f'node.switchport = "{port}"']
                    )
                    if detect_node:
                        self.logger.warning(f"Node {detect_node[0]['name']} with id {detect_node[0]['id']} on switch {switch} will use MAC {mac}")
                        result = True
                        provision_interface = 'BOOTIF'
                        if self.hastate is True:
                            self.wait_for_insync(self.hatrial)
                            payload = [{'interface': provision_interface, 'macaddress': mac}]
                            result, _ = Journal().add_request(function="Interface.change_node_interface",object=detect_node[0]['id'],payload=payload)
                        if result is True:
                            result, _ = Config().node_interface_config(
                                nodeid=detect_node[0]['id'],
                                interface_name=provision_interface,
                                macaddress=mac
                            )

                        nodeinterface = Database().get_record_join(
                            ['nodeinterface.nodeid', 'nodeinterface.interface',
                             'ipaddress.ipaddress', 'network.name as network', 'network.gateway',
                             'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp', 'network.gateway_ipv6',
                             'network.network_ipv6 as networkip_ipv6', 'network.dhcp as networkdhcp',
                             'network.network as networkip', 'network.subnet'],
                            ['network.id=ipaddress.networkid',
                             'ipaddress.tablerefid=nodeinterface.id'],
                            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
                        )
                        if nodeinterface:
                            data['nodeid'] = nodeinterface[0]['nodeid']
                            if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                                data['nodeip'] = 'dhcp'
                            elif nodeinterface[0]["ipaddress_ipv6"]:
                                data['nodeip'] = f'{nodeinterface[0]["ipaddress_ipv6"]}/{nodeinterface[0]["subnet_ipv6"]}'
                            else:
                                data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                            if nodeinterface[0]["ipaddress_ipv6"]:
                                data['gateway'] = nodeinterface[0]['gateway_ipv6'] or ''
                            else:
                                data['gateway'] = nodeinterface[0]['gateway'] or ''
                            Service().queue('dhcp', 'restart')
                            Service().queue('dhcp6','restart')
          # --------------------- cloud detection ----------------------------------
                else:
                    result = CloudDetectionPlugin().find(macaddress=mac)
                    if (isinstance(result, bool) and result is True) or (isinstance(result, tuple) and result[0] is True and len(result)>1):
                        cloud = result[1]
                        self.logger.debug(f"detected {mac} is seen in [{cloud}]")
                        possible_nodes = Database().get_record_join(
                            ['node.name', 'nodeinterface.nodeid', 'nodeinterface.interface',
                             'ipaddress.ipaddress', 'network.name as network', 'network.gateway',
                             'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp', 'network.gateway_ipv6',
                             'network.network_ipv6 as networkip_ipv6', 'network.dhcp as networkdhcp',
                             'network.network as networkip', 'network.subnet',
                             'nodeinterface.macaddress'],
                            ['node.id=nodeinterface.nodeid','network.id=ipaddress.networkid',
                             'ipaddress.tablerefid=nodeinterface.id','cloud.id=node.cloudid'],
                            ['tableref="nodeinterface"',f"cloud.name='{cloud}'",'nodeinterface.interface="BOOTIF"']
                        )
                        if possible_nodes:
                            result = True
                            for node in possible_nodes:
                                if not node['macaddress']:  # first candidate
                                    self.logger.info(f"Node {node['name']} with id {node['nodeid']} in cloud {cloud} will use MAC {mac}")
                                    provision_interface = 'BOOTIF'
                                    if self.hastate is True:
                                        self.wait_for_insync(self.hatrial)
                                        payload = [{'interface': provision_interface, 'macaddress': mac}]
                                        result, _ = Journal().add_request(function="Interface.change_node_interface",object=node['nodeid'],payload=payload)
                                    if result is True:
                                        result, _ = Config().node_interface_config(
                                            nodeid=node['nodeid'],
                                            interface_name=provision_interface,
                                            macaddress=mac
                                        )
                                    data['nodeid'] = node['nodeid']
                                    if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                                        data['nodeip'] = 'dhcp'
                                    elif node["ipaddress_ipv6"]:
                                        data['nodeip'] = f'{node["ipaddress_ipv6"]}/{node["subnet_ipv6"]}'
                                    else:
                                        data['nodeip'] = f'{node["ipaddress"]}/{node["subnet"]}'
                                    if node["ipaddress_ipv6"]:
                                        data['gateway'] = node['gateway_ipv6'] or ''
                                    else:
                                        data['gateway'] = node['gateway'] or ''
                                    Service().queue('dhcp', 'restart')
                                    Service().queue('dhcp6','restart')
                                    break

            except Exception as exp:
                self.logger.info(f"port detection/cloud call in boot returned: {exp}")
            # ----------- port/cloud detection was not successfull, lets try a last resort -------------
            # ------------------ "don't nag give me the next node" detection ---------------------------
            if not data['nodeid']:
                createnode_ondemand, nextnode_discover, createnode_macashost = None, None, None
                cluster = Database().get_record(None, 'cluster')
                if cluster:
                    if 'nextnode_discover' in cluster[0]:
                        nextnode_discover=Helper().make_bool(cluster[0]['nextnode_discover'])
                    if 'createnode_ondemand' in cluster[0]:
                        createnode_ondemand=Helper().make_bool(cluster[0]['createnode_ondemand'])
                    if 'createnode_macashost' in cluster[0]:
                        createnode_macashost=Helper().make_bool(cluster[0]['createnode_macashost'])
                if nextnode_discover:
                    self.logger.info(f"nextnode discover: we will try to see a good fit for {mac}")

                groupname, new_nodename = None, None
                group_details = Database().get_record(None,'group')
                if group_details and len(group_details) == 1:
                    groupname = group_details[0]['name']
                elif createnode_ondemand:
                    self.logger.warning(f"nextnode discover might fail as we have multiple groups and i don't know which is default")

                new_nodename, example_node, provision_interface = self.find_next_suitable_node(groupname=groupname, nextnode=nextnode_discover,
                                                                  makeupname=createnode_ondemand, macashost=createnode_macashost,
                                                                  mac=mac)

                if new_nodename:
                    self.logger.info(f"Node boot intelligence: we came up with the following node name: [{new_nodename}]")
                    # below is just in place to prevent double mac causing issues.
                    self.clear_existing_mac(macaddress=mac)

                    result, message = True, None
                    if example_node:
                        newnodedata = {'config': {'node': {example_node: {}}}}
                        newnodedata['config']['node'][example_node]['newnodename'] = new_nodename
                        newnodedata['config']['node'][example_node]['name'] = example_node
                        if groupname:
                            newnodedata['config']['node'][example_node]['group'] = groupname
                        if self.hastate is True:
                            self.wait_for_insync(self.hatrial)
                            result, message = Journal().add_request(function="Node.clone_node",object=example_node,payload=newnodedata)
                        if result is True:
                            result, message = Node().clone_node(example_node,newnodedata)
                        self.logger.info(f"Node select boot: Cloning {example_node} to {new_nodename}: result = [{result}], message = [{message}]")
                    else:
                        newnodedata = {'config': {'node': {new_nodename: {}}}}
                        newnodedata['config']['node'][new_nodename]['name'] = new_nodename
                        if groupname:
                            newnodedata['config']['node'][new_nodename]['group'] = groupname
                        if self.hastate is True:
                            self.wait_for_insync(self.hatrial)
                            result, message = Journal().add_request(function="Node.update_node",object=new_nodename,payload=newnodedata)
                        if result is True:
                            result, message = Node().update_node(new_nodename,newnodedata)
                        self.logger.info(f"Node select boot: Creating {new_nodename}: result = [{result}], message = [{message}]")
                    if result is True:
                        nodeid = Database().id_by_name('node', new_nodename)
                        if self.hastate is True:
                            self.wait_for_insync(self.hatrial)
                            payload = [{'interface': provision_interface, 'macaddress': mac}]
                            result, _ = Journal().add_request(function="Interface.change_node_interface",object=nodeid,payload=payload)
                        if result is True:
                            result, _ = Config().node_interface_config(nodeid=nodeid, interface_name=provision_interface, macaddress=mac)

                    nodeinterface = Database().get_record_join(
                        ['nodeinterface.nodeid', 'nodeinterface.interface', 'ipaddress.ipaddress_ipv6',
                         'ipaddress.ipaddress', 'ipaddress.dhcp', 'network.name as network', 'network.gateway',
                         'network.network as networkip', 'network.subnet', 'network.gateway_ipv6',
                         'network.network_ipv6 as networkip_ipv6', 'network.subnet_ipv6', 'network.dhcp as networkdhcp'],
                        ['network.id=ipaddress.networkid',
                         'ipaddress.tablerefid=nodeinterface.id'],
                        ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
                    )
                    if nodeinterface:
                        data['nodeid'] = nodeinterface[0]['nodeid']
                        if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                            data['nodeip'] = 'dhcp'
                        elif nodeinterface[0]["ipaddress_ipv6"]:
                            data['nodeip'] = f'{nodeinterface[0]["ipaddress_ipv6"]}/{nodeinterface[0]["subnet_ipv6"]}'
                        else:
                            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                        if nodeinterface[0]["ipaddress_ipv6"]:
                            data['gateway'] = nodeinterface[0]['gateway_ipv6'] or ''
                        else:
                            data['gateway'] = nodeinterface[0]['gateway'] or ''
                        Service().queue('dhcp', 'restart')
                        Service().queue('dhcp6','restart')
                elif nextnode_discover:
                    self.logger.info("Node boot intelligence couldn't find any suitable node")
        # -----------------------------------------------------------------------
        if not data['nodeid']:
            self.logger.info(f"node with macaddress {mac} wants to boot but we do not have any config")
            status=False
            return status, "No config available"

        data['kerneloptions']=""

        if data['nodeid']:
            node = Database().get_record_join(
                ['node.*','group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid',
                 'group.kerneloptions as groupkerneloptions','group.netboot as groupnetboot'],
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
                if node[0]['kerneloptions']:
                    data['kerneloptions']=node[0]['kerneloptions']
                elif node[0]['groupkerneloptions']:
                    data['kerneloptions']=node[0]['groupkerneloptions']
                if node[0]['netboot'] is not None:
                    data['netboot']=Helper().make_bool(node[0]['netboot'])
                elif node[0]['groupnetboot'] is not None:
                    data['netboot']=Helper().make_bool(node[0]['groupnetboot'])
                if self.b64regex.match(data['kerneloptions']):
                    ko_data = b64decode(data['kerneloptions'])
                    try:
                        data['kerneloptions'] = ko_data.decode("ascii")
                    except:
                        # apparently we were not base64! it can happen when a string seems like base64 but is not.
                        # is it safe to assume we can then just pass what's in the DB?
                        pass

        if data['osimageid']:
            osimage = None
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if UBoot().verify_bootpause(osimage[0]['name']):
                    self.logger.info(f"osimage {osimage[0]['name']} is currently being packed. Node will wait before booting")
                    data['cleartoboot']=None
                if osimage[0]['kernelfile']:
                    data['kernelfile'] = osimage[0]['kernelfile']
                if osimage[0]['initrdfile']:
                    data['initrdfile'] = osimage[0]['initrdfile']
                if osimage[0]['kerneloptions'] and not data['kerneloptions']:
                    if self.b64regex.match(osimage[0]['kerneloptions']):
                        ko_data = b64decode(osimage[0]['kerneloptions'])
                        try:
                            data['kerneloptions'] = ko_data.decode("ascii")
                        except:
                            # apparently we were not base64! it can happen when a string seems like base64 but is not.
                            # is it safe to assume we can then just pass what's in the DB?
                            data['kerneloptions'] = osimage[0]['kerneloptions']
                    else:
                        data['kerneloptions'] = osimage[0]['kerneloptions']

                # ------------ support for alternative provisioning ----------------

                if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                    template = 'templ_nodeboot_kickstart.cfg'
                    data['template'] = template
                    template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
                    check_template = Helper().check_jinja(template_path)
                    if not check_template:
                        environment = jinja2.Environment()
                        template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                        faildata = { template_data: template, message: "template for kickstart not defined or not existing" }
                        return False, faildata

                # ------------------------------------------------------------------

        if data['kerneloptions']:
            data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if data['nodeip'] and data['nodeip'] == 'dhcp':
            data['kerneloptions']+=' luna.bootproto=dhcp'

        if 'netboot' in data and data['netboot'] is False:
            template = 'templ_boot_disk.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                faildata = { template_data: template, message: "disk boot template does not exist" }
                return False, faildata
            data['template'] = template

        if None not in data.values():
            status=True
            # reintroduced below section as if we serve files through
            # e.g. nginx, we won't update anything
            state = {'monitor': {'status': {data['nodename']: {'state': "install.discovered"} } } }
            Monitor().update_nodestatus(data['nodename'], state)
        else:
            more_info = "No config available"
            for key, value in data.items():
                if value is None:
                    more_info = f"{key} has no value. Node {data['nodename']} cannot boot"
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
                    more_info=Helper().get_more_info(key)
                    if more_info:
                        self.logger.error(more_info)
                        break
            template = 'templ_boot_failed.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            status=False
            faildata = {
                'template'           : template,
                'message'            : more_info,
                'ipaddress'          : self.controller_ip,
                'webserver_protocol' : data['webserver_protocol'],
                'webserver_port'     : data['webserver_port']
            }
            return status, faildata
            #self.logger.info(f'template mac search data: {data}')
        self.logger.info(f'Boot API serving {template}')
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
            'loghost'       : self.controller_beaconip,
            'beacon'        : self.controller_beaconip,
            'protocol'      : CONSTANT['API']['PROTOCOL'],
            'verify_certificate': CONSTANT['API']['VERIFY_CERTIFICATE'],
            'webserver_protocol': CONSTANT['API']['PROTOCOL'],
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
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "node boot template does not exist" }
            return False, faildata
        if mac:
            mac = mac.lower()
        network, createnode_ondemand, createnode_macashost, nextnode_discover = None, None, None, None # used below

        if self.controller_name:
            data['ipaddress'] = self.controller_ip
            data['network'] = self.controller_network
            data['serverport'] = self.controller_serverport
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
            where = f" WHERE id='{self.controller_clusterid}'"
            cluster = Database().get_record(None, 'cluster', where)
            if cluster:
                if 'createnode_macashost' in cluster[0]:
                    createnode_macashost=Helper().make_bool(cluster[0]['createnode_macashost'])
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")

        # clear mac if it already exists. let's check
        # if there is a mac defined, this means there is already a node with this mac.
        # though we shouldn't, we will remove the other node's MAC so we can proceed.
        # Since we enforce a new node or re-use one, we can safely clear all macs.
        # Further down we configure the interface for the 'discovered' node and set the mac.
        self.clear_existing_mac(macaddress=mac)

#        # then we fetch a list of all nodes that we have, with or without interface config
#        list1 = Database().get_record_join(
#            ['node.*', 'group.name as groupname', 'group.provision_interface',
#            'nodeinterface.interface', 'nodeinterface.macaddress'],
#            ['nodeinterface.nodeid=node.id','group.id=node.groupid']
#        )
#        list2 = Database().get_record_join(
#            ['node.*', 'group.name as groupname'],
#            ['group.id=node.groupid']
#        )
#        node_list = list1 + list2

        # general group info and details. needed below
        group_details = Database().get_record(None,'group',f" WHERE name='{groupname}'")
        provision_interface = 'BOOTIF'
        if group_details and 'provision_interface' in group_details[0] and group_details[0]['provision_interface']:
            provision_interface = str(group_details[0]['provision_interface'])

        # first we generate a list of taken ips. we might need it later
#        ips, ips6 = [], []
#        if data['network']:
#            network = Database().get_record_join(
#                ['ipaddress.ipaddress', 'network.network', 'network.subnet',
#                 'ipaddress.ipaddress_ipv6', 'network.network_ipv6', 'network.subnet_ipv6'],
#                ['network.id=ipaddress.networkid'],
#                [f"network.name='{data['network']}'"]
#            )
#            if network:
#                for network_ip in network:
#                    if network_ip['ipaddress']:
#                        ips.append(network_ip['ipaddress'])
#                    if network_ip['ipaddress_ipv6']:
#                        ips.append(network_ip['ipaddress_ipv6'])

        new_nodename, example_node, _ = self.find_next_suitable_node(groupname=groupname, nextnode=True,
                                                       makeupname=True, macashost=createnode_macashost,
                                                       mac=mac)

        self.logger.info(f"Group boot intelligence: we came up with the following node name: [{new_nodename}]")

        if new_nodename:
            # Antoine aug 15 2023
            result, message = True, None
            if example_node:
                newnodedata = {'config': {'node': {example_node: {}}}}
                newnodedata['config']['node'][example_node]['newnodename'] = new_nodename
                newnodedata['config']['node'][example_node]['name'] = example_node
                newnodedata['config']['node'][example_node]['group'] = groupname # groupname is given through API call
                if self.hastate is True:
                    self.wait_for_insync(self.hatrial)
                    result, message = Journal().add_request(function="Node.clone_node",object=example_node,payload=newnodedata)
                if result is True:
                    result, message = Node().clone_node(example_node,newnodedata)
                self.logger.info(f"Group select boot: Cloning {example_node} to {new_nodename}: result = [{result}], message = [{message}]")
            else:
                newnodedata = {'config': {'node': {new_nodename: {}}}}
                newnodedata['config']['node'][new_nodename]['name'] = new_nodename
                newnodedata['config']['node'][new_nodename]['group'] = groupname # groupname is given through API call
                if self.hastate is True:
                    self.wait_for_insync(self.hatrial)
                    result, message = Journal().add_request(function="Node.update_node",object=new_nodename,payload=newnodedata)
                if result is True:
                    result, message = Node().update_node(new_nodename,newnodedata)
                self.logger.info(f"Group select boot: Creating {new_nodename}: result = [{result}], message = [{message}]")
            if result is True:
                hostname = new_nodename
                nodeid = Database().id_by_name('node', new_nodename)
                if self.hastate is True:
                    self.wait_for_insync(self.hatrial)
                    payload = [{'interface': provision_interface, 'macaddress': mac}]
                    result, _ = Journal().add_request(function="Interface.change_node_interface",object=nodeid,payload=payload)
                if result is True:
                    result, _ = Config().node_interface_config(nodeid=nodeid, interface_name=provision_interface, macaddress=mac)

#                    Below section commented out as it not really up to us to create interface
#                    for nodes if they are not configured. We better just use what's valid and ok
#                    We could also ditch list2 from above if we want - Antoine
#                    note: below section not ipv6 or HA ready
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
#                            nodeid=node['id'],
#                            interface_name=provision_interface,
#                            macaddress=mac
#                        )
#                        if result:
#                            result, _ = Config().node_interface_ipaddress_config(
#                                node['id'],
#                                provision_interface,
#                                avail_ip,
#                                data['network']
#                            )
#                            Service().queue('dns','reload')
#                            Service().queue('dhcp6','restart')
#                        break

        if not new_nodename:
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
            where = [{"column": "name", "value": new_nodename}]
            Database().update('node', row, where)

        # below here is almost identical to a manual node selection boot -----------------
        data['kerneloptions']=""

        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid',
             'group.kerneloptions as groupkerneloptions','group.netboot as groupnetboot'],
            ['group.id=node.groupid'],
            [f'node.name="{new_nodename}"']
        )
        if node:
            data['osimagetagid'] = node[0]['osimagetagid'] or node[0]['grouposimagetagid'] or 'default'
            data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
            data['nodename'] = node[0]['name']
            # data['nodehostname'] = node[0]['hostname']
            data['nodehostname'] = node[0]['name'] # + fqdn ?
            data['nodeservice'] = node[0]['service']
            data['nodeid'] = node[0]['id']
            if node[0]['kerneloptions']:
                data['kerneloptions']=node[0]['kerneloptions']
            elif node[0]['groupkerneloptions']:
                data['kerneloptions']=node[0]['groupkerneloptions']
            if node[0]['netboot'] is not None:
                data['netboot']=Helper().make_bool(node[0]['netboot'])
            elif node[0]['groupnetboot'] is not None:
                data['netboot']=Helper().make_bool(node[0]['groupnetboot'])
            if self.b64regex.match(data['kerneloptions']):
                ko_data = b64decode(data['kerneloptions'])
                try:
                    data['kerneloptions'] = ko_data.decode("ascii")
                except:
                    # apparently we were not base64! it can happen when a string seems like base64 but is not.
                    # is it safe to assume we can then just pass what's in the DB?
                    pass

        if data['nodeid']:
            Service().queue('dhcp','restart')
            Service().queue('dhcp6','restart')
            nodeinterface = Database().get_record_join(
                [
                    'nodeinterface.nodeid',
                    'nodeinterface.interface',
                    'nodeinterface.macaddress',
                    'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp',
                    'network.name as network', 'network.dhcp as networkdhcp',
                    'network.network as networkip', 'network.network_ipv6 as networkip_ipv6',
                    'network.subnet', 'network.subnet_ipv6',
                    'network.gateway', 'network.gateway_ipv6'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{data['nodeid']}'",
                    f'nodeinterface.macaddress="{mac}"'
                ]
            )
            if nodeinterface:
                if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                    data['nodeip'] = 'dhcp'
                elif nodeinterface[0]["ipaddress_ipv6"]:
                    data['nodeip'] = f'{nodeinterface[0]["ipaddress_ipv6"]}/{nodeinterface[0]["subnet_ipv6"]}'
                else:
                    data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                if nodeinterface[0]["ipaddress_ipv6"]:
                    data['gateway'] = nodeinterface[0]['gateway_ipv6'] or ''
                else:
                    data['gateway'] = nodeinterface[0]['gateway'] or ''
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = None
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if UBoot().verify_bootpause(osimage[0]['name']):
                    self.logger.info(f"osimage {osimage[0]['name']} is currently being packed. Node will wait before booting")
                    data['cleartoboot']=None
                if osimage[0]['kernelfile']:
                    data['kernelfile'] = osimage[0]['kernelfile']
                if osimage[0]['initrdfile']:
                    data['initrdfile'] = osimage[0]['initrdfile']
                if osimage[0]['kerneloptions'] and not data['kerneloptions']:
                    if self.b64regex.match(osimage[0]['kerneloptions']):
                        ko_data = b64decode(osimage[0]['kerneloptions'])
                        try:
                            data['kerneloptions'] = ko_data.decode("ascii")
                        except:
                            # apparently we were not base64! it can happen when a string seems like base64 but is not.
                            # is it safe to assume we can then just pass what's in the DB?
                            data['kerneloptions'] = osimage[0]['kerneloptions']
                    else:
                        data['kerneloptions'] = osimage[0]['kerneloptions']

                # ------------ support for alternative provisioning ----------------

                if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                    template = 'templ_nodeboot_kickstart.cfg'
                    data['template'] = template
                    template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
                    check_template = Helper().check_jinja(template_path)
                    if not check_template:
                        environment = jinja2.Environment()
                        template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                        faildata = { template_data: template, message: "template for kickstart not defined or not existing" }
                        return False, faildata

                # ------------------------------------------------------------------

        if data['kerneloptions']:
            data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if data['nodeip'] and data['nodeip'] == 'dhcp':
            data['kerneloptions']+=' luna.bootproto=dhcp'

        if 'netboot' in data and data['netboot'] is False:
            template = 'templ_boot_disk.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                faildata = { template_data: template, message: "disk boot template does not exist" }
                return False, faildata
            data['template'] = template

        if None not in data.values():
            status=True
            # reintroduced below section as if we serve files through e.g. nginx, we won't update
            state = {'monitor': {'status': {data['nodename']: {'state': "install.discovered"} } } }
            Monitor().update_nodestatus(data['nodename'], state)
        else:
            more_info = "No Node is available for this mac address"
            for key, value in data.items():
                if value is None:
                    more_info = f"{key} has no value. Node {data['nodename']} cannot boot"
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
                    more_info=Helper().get_more_info(key)
                    if more_info:
                        self.logger.error(more_info)
                        break
            template = 'templ_boot_failed.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = {
                'template'           : template,
                'message'            : more_info,
                'ipaddress'          : self.controller_ip,
                'webserver_protocol' : data['webserver_protocol'],
                'webserver_port'     : data['webserver_port']
            }
            status = False
            return status, faildata
        self.logger.info(f'Boot API serving {template}')
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
            'loghost'       : self.controller_beaconip,
            'beacon'        : self.controller_beaconip,
            'protocol'      : CONSTANT['API']['PROTOCOL'],
            'verify_certificate': CONSTANT['API']['VERIFY_CERTIFICATE'],
            'webserver_protocol': CONSTANT['API']['PROTOCOL'],
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
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "node boot template does not exist" }
            return False, faildata
        # Antoine
        if self.controller_name:
            data['ipaddress'] = self.controller_ip
            data['network'] = self.controller_network
            data['serverport'] = self.controller_serverport
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        else:
            self.logger.warning(f"possible configuration error: No controller available or missing network for controller")

        data['kerneloptions']=""

        # we probably have to cut the fqdn off of hostname?
        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid','group.osimagetagid as grouposimagetagid',
             'group.kerneloptions as groupkerneloptions','group.netboot as groupnetboot'],
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
            if node[0]['kerneloptions']:
                data['kerneloptions']=node[0]['kerneloptions']
            elif node[0]['groupkerneloptions']:
                data['kerneloptions']=node[0]['groupkerneloptions']
            if node[0]['netboot'] is not None:
                data['netboot']=Helper().make_bool(node[0]['netboot'])
            elif node[0]['groupnetboot'] is not None:
                data['netboot']=Helper().make_bool(node[0]['groupnetboot'])
            if self.b64regex.match(data['kerneloptions']):
                ko_data = b64decode(data['kerneloptions'])
                try:
                    data['kerneloptions'] = ko_data.decode("ascii")
                except:
                    # apparently we were not base64! it can happen when a string seems like base64 but is not.
                    # is it safe to assume we can then just pass what's in the DB?
                    pass

        if data['nodeid']:
            result = True
            self.clear_existing_mac(macaddress=mac,exclude_nodeid=data['nodeid'])
            self.logger.warning(f"Node {hostname} with id {data['nodeid']} will use MAC {mac}")
            provision_interface = 'BOOTIF'

            # we do not have anyone with this mac yet/anymore. we can safely move ahead.
            # BIG NOTE!: This is being done without token! By itself not a threat
            # but some someone could mess up node/interface configs.
            # The alternative would be to use IP from dhcp pool and set MAC after
            # the node has a token. This again will break things where a node is
            # using dhcp as bootproto. e.g. a manual override inside an image. -Antoine
            if self.hastate is True:
                self.wait_for_insync(self.hatrial)
                payload = [{'interface': provision_interface, 'macaddress': mac}]
                result, _ = Journal().add_request(function="Interface.change_node_interface",object=data['nodeid'],payload=payload)
            if result is True:
                result, _ = Config().node_interface_config(
                    nodeid=data['nodeid'],
                    interface_name=provision_interface,
                    macaddress=mac
                )

            Service().queue('dhcp', 'restart')
            Service().queue('dhcp6','restart')
            nodeinterface = Database().get_record_join(
                [
                    'nodeinterface.nodeid',
                    'nodeinterface.interface',
                    'nodeinterface.macaddress',
                    'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp',
                    'network.name as network', 'network.dhcp as networkdhcp',
                    'network.network as networkip', 'network.network_ipv6 as networkip_ipv6',
                    'network.subnet', 'network.subnet_ipv6',
                    'network.gateway', 'network.gateway_ipv6'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                [
                    'tableref="nodeinterface"',
                    f"nodeinterface.nodeid='{data['nodeid']}'",
                    f'nodeinterface.macaddress="{mac}"'
                ]
            )
            if nodeinterface:
                if nodeinterface[0]["dhcp"] and nodeinterface[0]["networkdhcp"]:
                    data['nodeip'] = 'dhcp'
                elif nodeinterface[0]["ipaddress_ipv6"]:
                    data['nodeip'] = f'{nodeinterface[0]["ipaddress_ipv6"]}/{nodeinterface[0]["subnet_ipv6"]}'
                else:
                    data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                if nodeinterface[0]["ipaddress_ipv6"]:
                    data['gateway'] = nodeinterface[0]['gateway_ipv6'] or ''
                else:
                    data['gateway'] = nodeinterface[0]['gateway'] or ''
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = None
            if data['osimagetagid'] and data['osimagetagid'] != 'default':
                osimage = Database().get_record_join(['osimagetag.*'],['osimage.id=osimagetag.osimageid'],
                                [f'osimagetag.id={data["osimagetagid"]}',f'osimage.id={data["osimageid"]}'])
            else:
                osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if UBoot().verify_bootpause(osimage[0]['name']):
                    self.logger.info(f"osimage {osimage[0]['name']} is currently being packed. Node will wait before booting")
                    data['cleartoboot']=None
                if osimage[0]['kernelfile']:
                    data['kernelfile'] = osimage[0]['kernelfile']
                if osimage[0]['initrdfile']:
                    data['initrdfile'] = osimage[0]['initrdfile']
                if osimage[0]['kerneloptions'] and not data['kerneloptions']:
                    if self.b64regex.match(osimage[0]['kerneloptions']):
                        ko_data = b64decode(osimage[0]['kerneloptions'])
                        try:
                            data['kerneloptions'] = ko_data.decode("ascii")
                        except:
                            # apparently we were not base64! it can happen when a string seems like base64 but is not.
                            # is it safe to assume we can then just pass what's in the DB?
                            data['kerneloptions'] = osimage[0]['kerneloptions']
                    else:
                        data['kerneloptions'] = osimage[0]['kerneloptions']

                # ------------ support for alternative provisioning ----------------

                if osimage[0]['imagefile'] and osimage[0]['imagefile'] == 'kickstart':
                    template = 'templ_nodeboot_kickstart.cfg'
                    data['template'] = template
                    template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
                    check_template = Helper().check_jinja(template_path)
                    if not check_template:
                        environment = jinja2.Environment()
                        template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                        faildata = { template_data: template, message: "template for kickstart not defined or not existing" }
                        return False, faildata

                # ------------------------------------------------------------------

        if data['kerneloptions']:
            data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')

        if data['nodeip'] and data['nodeip'] == 'dhcp':
            data['kerneloptions']+=' luna.bootproto=dhcp'

        if 'netboot' in data and data['netboot'] is False:
            template = 'templ_boot_disk.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
                faildata = { template_data: template, message: "disk boot template does not exist" }
                return False, faildata
            data['template'] = template

        if None not in data.values():
            status=True
            # reintroduced below section as if we serve files through e.g. nginx, we won't update
            state = {'monitor': {'status': {data['nodename']: {'state': "install.discovered"} } } }
            Monitor().update_nodestatus(data['nodename'], state)
        else:
            more_info = "No config available"
            for key, value in data.items():
                if value is None:
                    more_info = f"{key} has no value. Node {data['nodename']} cannot boot"
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
                    more_info=Helper().get_more_info(key)
                    if more_info:
                        self.logger.error(more_info)
                        break
            template = 'templ_boot_failed.cfg'
            template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
            check_template = Helper().check_jinja(template_path)
            if not check_template:
                environment = jinja2.Environment()
                template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            status = False
            faildata = {
                'template'           : template,
                'message'            : more_info,
                'ipaddress'          : self.controller_ip,
                'webserver_protocol' : data['webserver_protocol'],
                'webserver_port'     : data['webserver_port']
            }
            return status, faildata
        self.logger.info(f'Boot API serving {template}')
        return status, data


    def install(self, node=None, method=None):
        """
        This method will provide a install ipxe template for a node.
        """
        status=False
        template = 'templ_install.cfg'
        if method:
            template = f'templ_install_{method}.cfg'
        data = {
            'template'              : template,
            'loghost'               : self.controller_beaconip,
            'beacon'                : self.controller_beaconip,
            'protocol'              : CONSTANT['API']['PROTOCOL'],
            'verify_certificate'    : CONSTANT['API']['VERIFY_CERTIFICATE'],
            'webserver_protocol'    : CONSTANT['API']['PROTOCOL'],
            'nodeid'                : None,
            'group'                 : None,
            'ipaddress'             : None,
            'serverport'            : None,
            'nodename'              : None,
            'nodehostname'          : None,
            'osimagename'           : None,
            'imagefile'             : None,
            'selinux'               : None,
            'setupbmc'              : None,
            'unmanaged_bmc_users'   : None,
            'systemroot'            : None,
            'nameserver_ip'         : self.controller_beaconip,
            'domain_search'         : [],
            'interfaces'            : {},
            'bmc'                   : {}
        }
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            environment = jinja2.Environment()
            template = environment.from_string("#!ipxe\necho {{MESSAGE}}\nsleep 10")
            faildata = { template_data: template, message: "install template does not exist" }
            return False, faildata
        with open(template_path, 'r', encoding='utf-8') as file:
            template_data = file.read()

        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            data['selinux']      = Helper().bool_revert(cluster[0]['security'])
            data['cluster_provision_method']   = cluster[0]['provision_method']
            data['cluster_provision_fallback'] = cluster[0]['provision_fallback']
            if cluster[0]['nameserver_ip']:
                data['nameserver_ip'] = cluster[0]['nameserver_ip'].split(',')[0]
            if cluster[0]['domain_search']:
                data['domain_search'] = cluster[0]['domain_search'].split(',')
        nameserver_ips_ipv4, nameserver_ips_ipv6 = [self.controller_beaconip], [self.controller_beaconip]
        if self.controller_ipv4:
            nameserver_ips_ipv4.insert(0, self.controller_ipv4)
            nameserver_ips_ipv4 = Helper().dedupe_adjacent(nameserver_ips_ipv4)
        if self.controller_ipv6:
            nameserver_ips_ipv6.insert(0, self.controller_ipv6)
            nameserver_ips_ipv6 = Helper().dedupe_adjacent(nameserver_ips_ipv6)
        if self.controller_name:
            data['ipaddress'] = self.controller_ip
            data['network'] = self.controller_network
            data['serverport'] = self.controller_serverport
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
            'bootmenu': False,
            'unmanaged_bmc_users': 'skip',
        }
        ret, enclosed_node_details = Node().get_node(name=node)
        node_details=None
        if ret is True:
            if 'config' in enclosed_node_details.keys():
                if 'node' in enclosed_node_details['config'].keys():
                    if node in enclosed_node_details['config']['node']:
                        node_details=enclosed_node_details['config']['node'][node]
            if not node_details:
                status = False
                return False, "i received data back internally that i could not parse"
            self.logger.debug(f"DEBUG: {node_details}")
            for item in ['provision_method','provision_fallback','prescript','partscript','postscript',
                         'netboot','bootmenu','provision_interface','unmanaged_bmc_users','kerneloptions',
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
            data['nodename']     = node_details['name']
            data['nodehostname'] = node_details['hostname']
            data['roles']        = node_details['roles'] or ""
            data['scripts']      = node_details['scripts'] or ""
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
        else:
            del data['bmcsetup']

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
                    'nodeinterface.mtu',
                    'nodeinterface.vlanid',
                    'nodeinterface.vlan_parent',
                    'nodeinterface.bond_mode',
                    'nodeinterface.bond_slaves',
                    'nodeinterface.options',
                    'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'ipaddress.dhcp',
                    'network.name as network', 'network.dhcp as networkdhcp',
                    'network.network as networkip', 'network.network_ipv6 as networkip_ipv6',
                    'network.subnet', 'network.subnet_ipv6',
                    'network.gateway', 'network.gateway_ipv6',
                    'network.gateway_metric',
                    'network.nameserver_ip', 'network.nameserver_ip_ipv6',
                    'network.id as networkid',
                    'network.zone as zone',
                    'network.type as type',
                    'network.type as networktype'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id'],
                ['tableref="nodeinterface"', f"node.name='{data['nodename']}'"]
            )
            domain_search = []
            default_metric = '101'
            if nodeinterface:
                bond_count=0
                for interface in nodeinterface:
                    node_nwk, node_nwk6, netmask, netmask6 = None, None, None, None
                    if interface['ipaddress']:
                        node_nwk = f'{interface["ipaddress"]}/{interface["subnet"]}'
                        netmask = Helper().get_netmask(node_nwk)
                    if interface['ipaddress_ipv6']:
                        node_nwk6 = f'{interface["ipaddress_ipv6"]}/{interface["subnet_ipv6"]}'
                        netmask6 = Helper().get_netmask(node_nwk6)
                    if interface['interface'] == 'BMC':
                        # we configure bmc stuff here and no longer in template. big advantage is
                        # that we can have different networks/interface-names for different h/w,
                        # drivers, subnets, networks, etc
                        if 'bmc' in data:
                            data['bmc']['ipaddress'] = interface['ipaddress']
                            data['bmc']['ipaddress_ipv6'] = interface['ipaddress_ipv6']
                            data['bmc']['netmask'] = netmask
                            data['bmc']['vlanid'] = interface['vlanid'] or ""
                            data['bmc']['netmask_ipv6'] = netmask6
                            data['bmc']['gateway'] = interface['gateway'] or '0.0.0.0'
                            data['bmc']['gateway_ipv6'] = interface['gateway_ipv6'] or '::/0'
                    else:
                        # regular nic
                        zone = 'trusted'
                        if interface['gateway_metric'] is None:
                            interface['gateway_metric'] = default_metric
                        if interface['zone'] == 'external' or interface['zone'] == 'public':
                            zone = 'public'

                        # -----------------------------------------------------

                        interface_data = {
                                'interface': interface['interface'],
                                'macaddress': interface['macaddress'],
                                'mtu': interface['mtu'],
                                'ipaddress': interface['ipaddress'],
                                'ipaddress_ipv6': interface['ipaddress_ipv6'],
                                'prefix': interface['subnet'],
                                'prefix_ipv6': interface['subnet_ipv6'],
                                'network': node_nwk,
                                'network_ipv6': node_nwk6,
                                'vlanid': interface['vlanid'] or "",
                                'netmask': netmask,
                                'netmask_ipv6': netmask6,
                                'networkname': interface['network'],
                                'gateway': interface['gateway'] or "",
                                'gateway_ipv6': interface['gateway_ipv6'] or "",
                                'gateway_metric': str(interface['gateway_metric']) or default_metric,
                                'options': interface['options'] or "",
                                'zone': zone,
                                'type': interface['type'] or "ethernet",
                                'networktype': interface['networktype'] or "ethernet"
                            }

                        if interface['nameserver_ip']:
                            interface_data['nameserver_ip'] = interface['nameserver_ip'].split(',')
                        else:
                            interface_data['nameserver_ip'] = []
                        if interface['nameserver_ip_ipv6']:
                            interface_data['nameserver_ip_ipv6'] = interface['nameserver_ip_ipv6'].split(',')
                        else:
                            interface_data['nameserver_ip_ipv6'] = []

                        if interface['dhcp'] and interface['networkdhcp']:
                            interface_data['dhcp']=True
                        if not interface_data['ipaddress']:
                            del interface_data['gateway']
                            del interface_data['nameserver_ip']
                        if not interface_data['ipaddress_ipv6']:
                            del interface_data['gateway_ipv6']
                            del interface_data['nameserver_ip_ipv6']

                        # -----------------------------------------------------

                        interface_parent = interface['interface']
                        if interface['vlanid']:
                            interface_data['type'] = 'vlan'
                            if interface['vlan_parent'] and interface['vlan_parent'] != interface['interface']:
                                interface_data['vlan_parent'] = interface['vlan_parent']

                        provision_interface = data['provision_interface']
                        if interface['bond_mode'] and interface['bond_slaves']:
                            master = 'bond'+str(bond_count)
                            if interface['interface'] == data['provision_interface']:
                                self.logger.info(f"for interface {interface_parent} trying to use {master}")
                                bond_name_ok = False
                                while not bond_name_ok:
                                    for check_interface in nodeinterface:
                                        if 'interface' in check_interface and master == check_interface['interface']:
                                            bond_count+=1
                                            prev_master = master
                                            master = 'bond'+str(bond_count)
                                            self.logger.info(f"for interface {interface_parent} {prev_master} already exists, trying to use {master}")
                                            break
                                    bond_name_ok = True
                                interface_parent = master
                                provision_interface = interface_parent
                                bond_count+=1
                            else:
                                master = interface['interface']
                            slaves = interface['bond_slaves'].split(',');
                            for slave in slaves:
                                data['interfaces'][slave] = {
                                    'master': master,
                                    'type': "slave",
                                    'networktype': interface['networktype'] or "ethernet",
                                    'mtu': interface['mtu']
                                }
                            interface_data['bond_mode']  = interface['bond_mode']
                            interface_data['bond_slaves']= interface['bond_slaves'].split(',')
                            interface_data['type'] = 'bond'
                 
                        if interface_parent not in data['interfaces']:
                            data['interfaces'][interface_parent] = {}
                        data['interfaces'][interface_parent] = interface_data

                        domain_search.append(interface['network'])
                        if interface['interface'] == data['provision_interface']:
                            if interface['network']:
                                # if it is my prov interface then it will get that domain as a FQDN.
                                data['nodehostname'] = data['nodename'] + '.' + interface['network']
                                domain_search.insert(0, interface['network'])
                            # setting good defaults for BOOTIF if they do not exist. a must.
                            if provision_interface in data['interfaces']:
                                for item in ['gateway','gateway_ipv6','nameserver_ip','nameserver_ip_ipv6']:
                                    if not item in data['interfaces'][provision_interface]:
                                        continue
                                    elif not data['interfaces'][provision_interface][item]:
                                        if item == 'gateway':
                                            data['interfaces'][provision_interface]['gateway'] = self.controller_ipv4 or '0.0.0.0'
                                        elif item == 'gateway_ipv6':
                                            data['interfaces'][provision_interface]['gateway_ipv6'] = self.controller_ipv6 or '::/0'
                                        elif item == 'nameserver_ip':
                                            if nameserver_ips_ipv4[0]:
                                                data['interfaces'][provision_interface]['nameserver_ip'] = nameserver_ips_ipv4
                                            else:
                                                data['interfaces'][provision_interface]['nameserver_ip'] = ['0.0.0.0']
                                        elif item == 'nameserver_ip_ipv6':
                                            if nameserver_ips_ipv6[0]:
                                                data['interfaces'][provision_interface]['nameserver_ip_ipv6'] = nameserver_ips_ipv6
                                            else:
                                                data['interfaces'][provision_interface]['nameserver_ip_ipv6'] = ['::/0']

            if len(data['domain_search']) == 0:
                if domain_search:
                    data['domain_search'] = domain_search
                else:
                    # clearly, the user wants something that has no interface involvement. fallback to '', but not None
                    data['domain_search'] = ['']

        # needed for generating network config templates on server side
        if data['kerneloptions']:
            if self.b64regex.match(data['kerneloptions']):
                ko_data = b64decode(data['kerneloptions'])
                try:
                    data['kerneloptions'] = ko_data.decode("ascii")
                except:
                    pass
            data['kerneloptions']=data['kerneloptions'].replace('\n', ' ').replace('\r', '')
            # --- below section still here but should no longer be needed. cloud nodes should always
            # --- have dhcp configured for their interfaces - Antoine
            #kerneloptions=data['kerneloptions'].split(' ')
            #self.logger.debug(f"*** {kerneloptions}")
            #if 'luna.bootproto=dhcp' in kerneloptions:
            #    # most commonly used for cloud nodes
            #    self.logger.debug(f"*** found dhcp bootproto")
            #    if 'interfaces' in data and data['provision_interface'] in data['interfaces']:
            #        self.logger.debug(f"*** set dhcp for {data['provision_interface']}")
            #        data['interfaces'][data['provision_interface']]['dhcp']=True

        # we clean up what we no longer need
        del data['kerneloptions']

        ## SYSTEMROOT
        osimage_plugin = Helper().plugin_load(self.osimage_plugins,'osimage/operations/image',data['distribution'],data['osrelease'])
        data['systemroot'] = str(osimage_plugin().systemroot or '/sysroot')

        ## FETCH CODE SEGMENT
        cluster_provision_methods = [data['provision_method'], data['provision_fallback']]

        for method in cluster_provision_methods:
            if method:
                provision_plugin = Helper().plugin_load(self.boot_plugins, 'boot/provision', method)
                segment = str(provision_plugin().fetch)
                segment = f"function download_{method} {{\n{segment}\n}}\n## FETCH CODE SEGMENT"
                # self.logger.info(f"SEGMENT {method}:\n{segment}")
                template_data = template_data.replace("## FETCH CODE SEGMENT",segment)

        if not data['provision_fallback']:
            data['provision_fallback'] = data['provision_method']


        ## INTERFACE CODE SEGMENT
        network_template = Helper().template_find(
            self.boot_plugins,
            'boot/network',
            data['distribution'],
            data['osrelease']
        )
        if network_template:
            try:
                self.logger.info(f"{data['nodename']} is using {self.plugins_path}/{network_template} for network config")
                with open(f"{self.plugins_path}/{network_template}") as template_file:
                    interface_template_data = template_file.read()
                segment = str(interface_template_data)
                template_data = template_data.replace("## INTERFACE TEMPLATE SEGMENT", segment)
            except Exception as exp:
                self.logger.error(f"{exp}")

        network_plugin = Helper().plugin_load(
            self.boot_plugins,
            'boot/network',
            data['distribution'],
            data['osrelease']
        )
        try:
            segment = str(network_plugin().init)
            template_data = template_data.replace("## NETWORK INIT CODE SEGMENT", segment)
        except:
            pass
        segment = str(network_plugin().hostname)
        template_data = template_data.replace("## HOSTNAME CODE SEGMENT", segment)
        # --------- ipv4
        segment = str(network_plugin().interface)
        template_data = template_data.replace("## INTERFACE CODE SEGMENT", segment)
        segment = str(network_plugin().gateway)
        template_data = template_data.replace("## GATEWAY CODE SEGMENT", segment)
        segment = str(network_plugin().dns)
        template_data = template_data.replace("## DNS CODE SEGMENT", segment)
        # --------- ipv6
        try:
            segment = str(network_plugin().interface_ipv6)
            template_data = template_data.replace("## INTERFACE IPv6 CODE SEGMENT", segment)
            segment = str(network_plugin().gateway_ipv6)
            template_data = template_data.replace("## GATEWAY IPv6 CODE SEGMENT", segment)
            segment = str(network_plugin().dns_ipv6)
            template_data = template_data.replace("## DNS IPv6 CODE SEGMENT", segment)
        except:
            pass

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

        if None not in data.values():
            status=True
            state = {'monitor': {'status': {data['nodename']: {'state': "install.rendered"} } } }
            Monitor().update_nodestatus(data['nodename'], state)
        else:
            for key, value in data.items():
                if value is None:
                    self.logger.error(f"{key} has no value. Node {data['nodename']} cannot boot")
                    more_info=Helper().get_more_info(key)
                    if more_info:
                        self.logger.error(more_info)
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
