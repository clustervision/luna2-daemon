#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.service import Service
from utils.config import Config
from common.constant import CONSTANT

try:
    from plugins.detection.switchport import Plugin as DetectionPlugin
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
        self.provision_plugins = Helper().plugin_finder(f'{plugins_path}/provision')
        self.network_plugins = Helper().plugin_finder(f'{plugins_path}/network')
        self.bmc_plugins = Helper().plugin_finder(f'{plugins_path}/bmc')
        self.install_plugins = Helper().plugin_finder(f'{plugins_path}/install')
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
            webserver_protocol = protocol
            webserver_port = serverport
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    webserver_port = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    webserver_protocol = CONSTANT['WEBSERVER']['PROTOCOL']
            status=True
        else:
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
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        # Antoine
        # LOGGER.info(f"BOOT/SEARCH/MAC received for {mac}")
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            data['ipaddress'] = controller[0]['ipaddress']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        nodeinterface = Database().get_record_join(
            ['nodeinterface.nodeid', 'nodeinterface.interface', 'ipaddress.ipaddress',
            'network.name as network', 'network.network as networkip', 'network.subnet'],
            ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
        )
        if nodeinterface:
            data['nodeid'] = nodeinterface[0]['nodeid']
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
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
                             'ipaddress.ipaddress', 'network.name as network',
                             'network.network as networkip', 'network.subnet'],
                            [
                                'network.id=ipaddress.networkid',
                                'ipaddress.tablerefid=nodeinterface.id'
                            ],
                            ['tableref="nodeinterface"', f"nodeinterface.macaddress='{mac}'"]
                        )
                        if nodeinterface:
                            data['nodeid'] = nodeinterface[0]['nodeid']
                            nodeip = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
                            data['nodeip'] = nodeip
                            Service().queue('dhcp', 'restart')
            except Exception as exp:
                self.logger.info(f"port detection call in boot returned: {exp}")
        # -----------------------------------------------------------------------
        if data['nodeid']:
            node = Database().get_record_join(
                ['node.*','group.osimageid as grouposimageid'],
                ['group.id=node.groupid'],
                [f'node.id={data["nodeid"]}']
            )
            if node:
                data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
                data['nodename'] = node[0]['name']
                # data['nodehostname'] = node[0]['hostname']
                data['nodehostname'] = node[0]['name'] # + fqdn - pending
                data['nodeservice'] = node[0]['service']
        if data['osimageid']:
            osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']

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
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        # Antoine
        networkname, network, createnode_ondemand = None, None, True # used below

        # get controller and cluster info
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress', 'network.name as networkname'],
            ['ipaddress.tablerefid=controller.id', 'network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if not controller:
            # e.g. when the controller has some other IP address that is reachable by 
            # a node but not configured in luna.
            controller = Database().get_record_join(
                ['controller.*', 'ipaddress.ipaddress'],
                ['ipaddress.tablerefid=controller.id'],
                ['tableref="controller"', 'controller.hostname="controller"']
            )
            altnetwork = Database().get_record(None, 'network', f"WHERE dhcp='1' or dhcp='true'")
            if controller[0] and altnetwork:
                controller[0]['networkname']=altnetwork[0]['name']
        if controller:
            data['ipaddress'] = controller[0]['ipaddress']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
            if 'networkname' in controller[0]:
                networkname = controller[0]['networkname']
            where = f" WHERE id='{controller[0]['clusterid']}'"
            cluster = Database().get_record(None, 'cluster', where)
            if cluster and 'createnode_ondemand' in cluster[0]:
                createnode_ondemand=Helper().bool_revert(cluster[0]['createnode_ondemand'])
        # clear mac if it already exists. let's check
        nodeinterface_check = Database().get_record_join(
            ['nodeinterface.nodeid as nodeid', 'nodeinterface.interface'],
            ['nodeinterface.nodeid=node.id'],
            [f'nodeinterface.macaddress="{mac}"']
        )
        if nodeinterface_check:
            # this means there is already a node with this mac.
            # though we shouldn't, we will remove the other node's MAC so we can proceed
            self.logger.warning(f"node with id {nodeinterface_check[0]['nodeid']} will have its\
                                 MAC cleared and this <to be declared>-node  will use MAC {mac}")
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

        # things we have to set if we 'clone' or create a node
        items = {
            # 'setupbmc'       : False,
            # 'netboot'        : False,
            # 'localinstall'   : False,
            # 'bootmenu'       : False,
            'service'        : False,
            'localboot'      : False
        }

        # first we generate a list of taken ips. we might need it later
        ips = []
        if networkname:
            network = Database().get_record_join(
                ['ipaddress.ipaddress', 'network.network', 'network.subnet'],
                ['network.id=ipaddress.networkid'],
                [f"network.name='{networkname}'"]
            )
            if network:
                for network_ip in network:
                    ips.append(network_ip['ipaddress'])
        else:
            return False, "we do not have enough network information"

        hostname = None # we use it further down below.
        checked = []
        if (not node_list) or (createnode_ondemand is True):
            # we have no spare or free nodes in here -or- we create one on demand.
            new_data = {}
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
                    new_data['name'] = f"{ename}{new_enumber}"
                elif ename:
                    new_enumber = '001'
                    new_data['name'] = f"{ename}{new_enumber}"
                else:
                    # we have to create a name ourselves
                    new_data['name'] = f"{groupname}001"
            else:
                # we have to create a name ourselves
                new_data['name'] = f"{groupname}001"
            self.logger.info(f"Group boot intelligence: we came up with the following\
                              node name: [{new_data['name']}]")
            # we kinda already do this further down... but i leave it here as it makes sense
            if group_details:
                new_data['groupid']=group_details[0]['id']

            for key, value in items.items():
                if list2 and key in list2[0] and list2[0][key]:
                    # we copy from another node. not sure if this is really correct. pending
                    new_data[key] = list2[0][key]
                    if isinstance(value, bool):
                        new_data[key] = str(Helper().make_bool(new_data[key]))
                else:
                    new_data[key] = value
                if (not new_data[key]) and (key not in items):
                    del new_data[key]
            row = Helper().make_rows(new_data)
            nodeid = Database().insert('node', row)

            if nodeid:
                hostname = new_data['name']
                # we need to pick the current network in a smart way. we assume the
                # default network, the network where controller is in.
                # HOWEVER: we do not copy/create network if options. it's a bit tedious
                # so we leave it here for now as pending. -Antoine
                avail_ip = Helper().get_available_ip(
                    network[0]['network'],
                    network[0]['subnet'],
                    ips
                )
                result, _ = Config().node_interface_config(nodeid, provision_interface, mac)
                if result:
                    result, _ = Config().node_interface_ipaddress_config(
                        nodeid,
                        provision_interface,
                        avail_ip,
                        networkname
                    )
                Service().queue('dns', 'restart')
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
                    elif not 'interface' in node:
                        # node is there but no interface. we'll take it!
                        hostname = node['name']
                        # we need to pick the current network in a smart way. we assume
                        # the default network where controller is in as well
                        avail_ip = Helper().get_available_ip(
                            network[0]['network'],
                            network[0]['subnet'],
                            ips
                        )
                        result, _ = Config().node_interface_config(
                            node['id'],
                            provision_interface,
                            mac
                        )
                        if result:
                            result, _ = Config().node_interface_ipaddress_config(
                                node['id'],
                                provision_interface,
                                avail_ip,
                                networkname
                            )
                            Service().queue('dns','restart')
                        break

        if not hostname:
            # we bail out because we could not re-use a node or create one.
            # something above did not work out.
            environment = jinja2.Environment()
            template = environment.from_string('No Node is available for this group.')
            status=False
            return status, template

        # we update the groupid of the node. this is actually only really
        # needed if we re-use a node (unassigned)
        if group_details:
            row = [{"column": "groupid", "value": group_details[0]['id']}]
            where = [{"column": "name", "value": hostname}]
            Database().update('node', row, where)

        # below here is almost identical to a manual node selection boot -----------------

        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid'],
            ['group.id=node.groupid'],
            [f'node.name="{hostname}"']
        )
        if node:
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
                    'network.subnet'
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
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']
        #self.logger.info(f"manual group boot template data: [{data}]")

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
            'serverport'    : None,
            'initrdfile'    : None,
            'kernelfile'    : None,
            'nodename'      : None,
            'nodehostname'  : None,
            'nodeservice'   : None,
            'nodeip'        : None
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
        data['webserver_protocol'] = data['protocol']
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            return False, 'Empty'
        # Antoine
        controller = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"','controller.hostname="controller"']
        )
        if controller:
            data['ipaddress'] = controller[0]['ipaddress']
            data['serverport'] = controller[0]['serverport']
            data['webserver_port'] = data['serverport']
            if 'WEBSERVER' in CONSTANT:
                if 'PORT' in CONSTANT['WEBSERVER']:
                    data['webserver_port'] = CONSTANT['WEBSERVER']['PORT']
                if 'PROTOCOL' in CONSTANT['WEBSERVER']:
                    data['webserver_protocol'] = CONSTANT['WEBSERVER']['PROTOCOL']

        # we probably have to cut the fqdn off of hostname?
        node = Database().get_record_join(
            ['node.*', 'group.osimageid as grouposimageid'],
            ['group.id=node.groupid'],
            [f'node.name="{hostname}"']
        )
        if node:
            data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
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
                    message = f"Warning: node with id {nodeinterface_check[0]['nodeid']} "
                    message += f"will have its MAC cleared and node {hostname} with "
                    message += f"id {data['nodeid']} will use MAC {mac}"
                    self.logger.info(message)
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
                    'network.subnet'
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
            else:
                # uh oh... no bootif??
                data['nodeip'] = None

        if data['osimageid']:
            osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                    data['kernelfile'] = osimage[0]['kernelfile']
                if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                    data['initrdfile'] = osimage[0]['initrdfile']
        #self.logger.info(f"manual node boot template data: [{data}]")

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


    def install(self, node=None):
        """
        This method will provide a install ipxe template for a node.
        """
        status=False
        template = 'templ_install.cfg'
        data = {
            'template'              : template,
            'osimageid'             : None,
            'groupid'               : None,
            'nodeid'                : None,
            'ipaddress'             : None,
            'serverport'            : None,
            'nodehostname'          : None,
            'osimagename'           : None,
            'imagefile'             : None,
            'selinux'               : None,
            'setupbmc'              : None,
            'localinstall'          : None,
            'unmanaged_bmc_users'   : None,
            'interfaces'            : {},
            'bmc'                   : {}
        }
        data['protocol'] = CONSTANT['API']['PROTOCOL']
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
        node_details = Database().get_record_join(
            [
                'node.*',
                'group.osimageid as grouposimageid',
                'group.name as groupname',
                'group.bmcsetupid as groupbmcsetupid'
            ],
            ['group.id=node.groupid'],
            [f'node.name="{node}"']
        )
        if node_details:
            # ---
            if node_details[0]['osimageid']:
                data['osimageid']       = node_details[0]['osimageid']
            else:
                data['osimageid']       = node_details[0]['grouposimageid']
            # ---
            if node_details[0]['bmcsetupid']:
                data['bmcsetupid']       = node_details[0]['bmcsetupid']
            else:
                data['bmcsetupid']       = node_details[0]['groupbmcsetupid']
            # ---
            data['groupid']             = node_details[0]['groupid']
            data['groupname']           = node_details[0]['groupname']
            data['nodename']            = node_details[0]['name']
            data['nodehostname']        = node_details[0]['name'] # + fqdn further below
            data['nodeid']              = node_details[0]['id']
            data['provision_method']    = node_details[0]['provision_method']
            data['provision_fallback']  = node_details[0]['provision_fallback']

            en_part = "bW91bnQgLXQgdG1wZnMgdG1wZnMgL3N5c3Jvb3QK"
            en_post = "ZWNobyAndG1wZnMgLyB0bXBmcyBkZWZhdWx0cyAwIDAnID4+IC9zeXNyb290L2V0Yy9mc3RhYgo="

            items = {
                'prescript': '',
                'partscript': en_part,
                'postscript': en_post,
                'setupbmc': False,
                'netboot': False,
                'localinstall': False,
                'bootmenu': False,
                'provision_interface': 'BOOTIF',
                'unmanaged_bmc_users': 'skip',
                'provision_method': data['cluster_provision_method'],
                'provision_fallback': data['cluster_provision_fallback']
            }

            for key, value in items.items():
                data[key] = node_details[0][key]
                if isinstance(value, bool):
                    data[key] = Helper().make_bool(data[key])

        if data['setupbmc'] is True and data['bmcsetupid']:
            bmcsetup = Database().get_record(None, 'bmcsetup', f" WHERE id = {data['bmcsetupid']}")
            if bmcsetup:
                data['bmc'] = {}
                data['bmc']['userid'] = bmcsetup[0]['userid']
                data['bmc']['username'] = bmcsetup[0]['username']
                data['bmc']['password'] = bmcsetup[0]['password']
                data['bmc']['netchannel'] = bmcsetup[0]['netchannel']
                data['bmc']['mgmtchannel'] = bmcsetup[0]['mgmtchannel']
                data['unmanaged_bmc_users'] = bmcsetup[0]['unmanaged_bmc_users']
            else:
                data['setupbmc'] = False

        if data['groupid']:
            group = Database().get_record(None, 'group', f' WHERE id = {data["groupid"]}')
            if group:
                # What's configured for the node, or the group, or a default fallback
                for key, value in items.items():
                    if key in data and key in group[0] and group[0][key] and not str(data[key]):
                        # we check if we have data filled. if not (meaning node does not have
                        # that info) we verify if the group has it and if so, we fill it
                        if isinstance(value, bool):
                            group[0][key] = Helper().make_bool(group[0][key])
                        data[key] = data[key] or group[0][key] or value
                    elif str(data[key]) and data[key] is not None:
                        pass
                    else:
                        # if anything else fails we use the fallback
                        if isinstance(value, bool):
                            data[key] = Helper().make_bool(data[key])
                        data[key] = value

        if data['osimageid']:
            osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
            if osimage:
                data['osimagename'] = osimage[0]['name']
                data['imagefile'] = osimage[0]['imagefile']
                data['distribution'] = osimage[0]['distribution'].lower() or 'redhat'
                data['osrelease'] = 'default.py'
                if 'osrelease' in osimage[0]:
                    data['osrelease'] = osimage[0]['osrelease'] or 'default.py'

        if data['nodeid']:
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
                    'network.id as networkid'
                ],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{data['nodeid']}'"]
            )
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
                            'network': node_nwk,
                            'netmask': netmask,
                            'networkname': interface['network'],
                            'gateway': interface['gateway'],
                            'options': interface['options'] or ""
                        }
                        if interface['interface'] == data['provision_interface'] and interface['network']:
                            # if it is my prov interface then it will get that domain as a FQDN.
                            data['nodehostname'] = data['nodename'] + '.' + interface['network']

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

        ## FETCH CODE SEGMENT
        cluster_provision_methods = [data['provision_method'], data['provision_fallback']]

        for method in cluster_provision_methods:
            provision_plugin = Helper().plugin_load(self.provision_plugins, 'provision', method)
            segment = str(provision_plugin().fetch)
            segment = f"function download_{method} {{\n{segment}\n}}\n## FETCH CODE SEGMENT"
            # self.logger.info(f"SEGMENT {method}:\n{segment}")
            template_data = template_data.replace("## FETCH CODE SEGMENT",segment)

        ## INTERFACE CODE SEGMENT
        network_plugin = Helper().plugin_load(
            self.network_plugins,
            'network',
            data['distribution'],
            data['osrelease']
        )
        segment = str(network_plugin().interface)
        template_data = template_data.replace("## INTERFACE CODE SEGMENT", segment)
        segment = str(network_plugin().hostname)
        template_data = template_data.replace("## HOSTNAME CODE SEGMENT", segment)
        segment = str(network_plugin().gateway)
        template_data = template_data.replace("## GATEWAY CODE SEGMENT", segment)

        ## BMC CODE SEGMENT
        bmc_plugin = Helper().plugin_load(
            self.bmc_plugins,
            'bmc',
            [data['nodename'], data['groupname']]
        )
        segment = str(bmc_plugin().config)
        template_data = template_data.replace("## BMC CODE SEGMENT",segment)

        ## INSTALL <PRE|PART|POST>SCRIPT CODE SEGMENT
        install_plugin = Helper().plugin_load(
            self.install_plugins,
            'install',
            [data['nodename'],data['groupname']]
        )
        for script in ['prescript', 'partscript', 'postscript']:
            segment = ""
            match script:
                case 'prescript':
                    segment = str(install_plugin().prescript)
                case 'partscript':
                    segment = str(install_plugin().partscript)
                case 'postscript':
                    segment = str(install_plugin().postscript)
            template_data = template_data.replace(
                f"## INSTALL {script.upper()} CODE SEGMENT",
                segment
            )

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