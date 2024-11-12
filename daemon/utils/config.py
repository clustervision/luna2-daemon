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
This is a Config Class, which provide the configuration
to DHN and DHCP methods.

"""

__author__      = 'Sumit Sharma/Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma/Antoine Schonewille'
__email__       = 'support@clustervision.com'
__status__      = 'Development'

import os
import sys
import subprocess
import shutil
from time import time, sleep
import re
from jinja2 import Environment, FileSystemLoader
from ipaddress import ip_address
from textwrap import dedent
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue
from utils.ha import HA
from utils.controller import Controller
from common.constant import CONSTANT


class Config(object):
    """
    All kind of configuration methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing has to initialize.
        """
        self.logger = Log.get_logger()


    def dhcp_overwrite(self):
        """
        This method collect dhcp enabled networks, node interfaces belongs to the networks and
        other devices which have the mac address. write and validates the /var/tmp/luna/dhcpd.conf
        """
        validate = True
        template = 'templ_dhcpd.cfg'
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dhcp config. {template_path} does not exist")
            return False
        template6 = 'templ_dhcpd6.cfg'
        template6_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template6}'
        check_template6 = Helper().check_jinja(template6_path)
        if not check_template6:
            self.logger.error(f"Error building dhcp config. {template6_path} does not exist")
            return False
        ntp_server, nameserver_ip, nameserver_ip_ipv6 = None, None, None
        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            if 'ntp_server' in cluster[0] and cluster[0]['ntp_server']:
                ntp_server = cluster[0]['ntp_server']
            if 'nameserver_ip' in cluster[0] and cluster[0]['nameserver_ip']:
                nameserver_ip = cluster[0]['nameserver_ip']
            if 'nameserver_ip_ipv6' in cluster[0] and cluster[0]['nameserver_ip_ipv6']:
                nameserver_ip_ipv6 = cluster[0]['nameserver_ip_ipv6']
        dhcp_file = f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}/dhcpd.conf"
        dhcp6_file = f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}/dhcpd6.conf"
        domain = None
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as domain'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.beacon=1']
        )
        if controller:
            domain=controller[0]['domain']
            ntp_server = ntp_server or controller[0]['ipaddress']
            nameserver_ip = nameserver_ip or controller[0]['ipaddress']
            nameserver_ip_ipv6 = nameserver_ip_ipv6 or controller[0]['ipaddress_ipv6']
        #
        omapikey=None
        if CONSTANT['DHCP']['OMAPIKEY']:
            omapikey=CONSTANT['DHCP']['OMAPIKEY']
        #
        config_classes = {}
        config_classes6 = {}
        config_shared = {}
        config_shared6 = {}
        config_subnets = {}
        config_subnets6 = {}
        config_hosts = {}
        config_hosts6 = {}
        config_pools = {}
        config_pools6 = {}
        #
        networksbyname = {}
        networks = Database().get_record(None, 'network', ' WHERE `dhcp` = 1')
        if networks:
            networksbyname = Helper().convert_list_to_dict(networks, 'name')

        shared = {}
        shared6 = {}
        for network in networksbyname.keys():
            networksbyname[network]['ipv6'], networksbyname[network]['ipv4'] = False, False
            if networksbyname[network]['dhcp_range_begin'] and networksbyname[network]['dhcp_range_end'] and networksbyname[network]['network']:
                networksbyname[network]['ipv4'] = True
            if networksbyname[network]['dhcp_range_begin_ipv6'] and networksbyname[network]['dhcp_range_end_ipv6'] and networksbyname[network]['network_ipv6']:
                networksbyname[network]['ipv6'] = True
            if networksbyname[network]['shared'] and networksbyname[network]['shared'] in networksbyname.keys():
                if networksbyname[network]['ipv4']:
                    if not networksbyname[network]['shared'] in shared.keys():
                        shared[networksbyname[network]['shared']] = []
                    shared[networksbyname[network]['shared']].append(network)
                if networksbyname[network]['ipv6']:
                    if not networksbyname[network]['shared'] in shared6.keys():
                        shared6[networksbyname[network]['shared']] = []
                    shared6[networksbyname[network]['shared']].append(network)

        handled = []
        # IPv4
        for network in shared.keys():
            shared_name = f"{network}-" + "-".join(shared[network])
            #
            config_pools[shared_name]={}
            config_pools[shared_name]['policy']='deny'
            config_pools[shared_name]['members']=shared[network]
            config_pools[shared_name]['range_begin']=networksbyname[network]['dhcp_range_begin']
            config_pools[shared_name]['range_end']=networksbyname[network]['dhcp_range_end']
            #
            config_shared[shared_name]={}
            config_shared[shared_name][network]=self.dhcp_subnet_config(networksbyname[network],'shared','ipv4')
            handled.append(network)

            for piggyback in shared[network]:
                config_pools[piggyback]={}
                config_pools[piggyback]['policy']='allow'
                config_pools[piggyback]['members']=[piggyback]
                config_shared[shared_name][piggyback]=self.dhcp_subnet_config(networksbyname[piggyback],'shared','ipv4')
                config_pools[piggyback]['range_begin']=networksbyname[piggyback]['dhcp_range_begin']
                config_pools[piggyback]['range_end']=networksbyname[piggyback]['dhcp_range_end']
                config_classes[piggyback]={}
                config_classes[piggyback]['network']=piggyback
                handled.append(piggyback)

        # IPv6
        for network in shared6.keys():
            shared_name = f"{network}-" + "-".join(shared6[network])
            #
            config_pools6[shared_name]={}
            config_pools6[shared_name]['policy']='deny'
            config_pools6[shared_name]['members']=shared6[network]
            config_pools6[shared_name]['range_begin']=networksbyname[network]['dhcp_range_begin_ipv6']
            config_pools6[shared_name]['range_end']=networksbyname[network]['dhcp_range_end_ipv6']
            #
            config_shared6[shared_name]={}
            config_shared6[shared_name][network]=self.dhcp_subnet_config(networksbyname[network],'shared','ipv6')
            handled.append(network+'_ipv6')

            for piggyback in shared6[network]:
                config_pools6[piggyback]={}
                config_pools6[piggyback]['policy']='allow'
                config_pools6[piggyback]['members']=[piggyback]
                config_shared6[shared_name][piggyback]=self.dhcp_subnet_config(networksbyname[piggyback],'shared','ipv6')
                config_pools6[piggyback]['range_begin']=networksbyname[piggyback]['dhcp_range_begin_ipv6']
                config_pools6[piggyback]['range_end']=networksbyname[piggyback]['dhcp_range_end_ipv6']
                config_classes6[piggyback]={}
                config_classes6[piggyback]['network']=piggyback
                handled.append(piggyback+'_ipv6')

        if networksbyname:
            for network in networksbyname.keys():
                nwk = networksbyname[network]
                if nwk['name'] not in handled and nwk['ipv4']:
                    config_subnets[nwk['name']] = self.dhcp_subnet_config(nwk,False,'ipv4')
                    handled.append(nwk['name'])
                if nwk['name']+'_ipv6' not in handled and nwk['ipv6']:
                    config_subnets6[nwk['name']] = self.dhcp_subnet_config(nwk,False,'ipv6')
                    handled.append(nwk['name']+'_ipv6')
                network_id = nwk['id']
                network_name = nwk['name']
                network_ip = nwk['network']
                network_ipv6 = nwk['network_ipv6']
                node_interface = Database().get_record_join(
                    ['node.name as nodename', 'ipaddress.ipaddress', 
                     'ipaddress.ipaddress_ipv6', 'nodeinterface.macaddress'],
                    ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id'],
                    ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
                )
                nodedomain=nwk['name']
                if node_interface:
                    for interface in node_interface:
                        if nodedomain == domain:
                            node=interface['nodename']
                        else:
                            node=f"{interface['nodename']}.{nodedomain}"
                        if interface['macaddress'] and node not in config_hosts:
                            if interface['ipaddress_ipv6']:
                                config_hosts6[node]={}
                                config_hosts6[node]['name']=interface['nodename']
                                config_hosts6[node]['domain']=nodedomain
                                config_hosts6[node]['ipaddress']=interface['ipaddress_ipv6']
                                config_hosts6[node]['macaddress']=interface['macaddress']
                            else:
                                config_hosts[node]={}
                                config_hosts[node]['name']=interface['nodename']
                                config_hosts[node]['domain']=nodedomain
                                config_hosts[node]['ipaddress']=interface['ipaddress']
                                config_hosts[node]['macaddress']=interface['macaddress']
                else:
                    self.logger.info(f'No Nodes available for this network {network_name} IPv4: {network_ip} or IPv6: {network_ipv6}')
                for item in ['otherdevices', 'switch']:
                    devices = Database().get_record_join(
                        [f'{item}.name','ipaddress.ipaddress','ipaddress.ipaddress_ipv6',f'{item}.macaddress'],
                        [f'ipaddress.tablerefid={item}.id'],
                        [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                    )
                    if devices:
                        for device in devices:
                            if device['macaddress']:
                                if device['ipaddress_ipv6']:
                                    config_hosts6[device['name']]={}
                                    config_hosts6[device['name']]['name']=device['name']
                                    config_hosts6[device['name']]['ipaddress']=device['ipaddress_ipv6']
                                    config_hosts6[device['name']]['maccaddress']=device['macaddress']
                                else:
                                    config_hosts[device['name']]={}
                                    config_hosts[device['name']]['name']=device['name']
                                    config_hosts[device['name']]['ipaddress']=device['ipaddress']
                                    config_hosts[device['name']]['maccaddress']=device['macaddress']
                    else:
                        self.logger.debug(f'{item} not available for {network_name}  IPv4: {network_ip} or IPv6: {network_ipv6}')
        
        try:
            file_loader = FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"])
            env = Environment(loader=file_loader)
            # IPv4 -----------------------------------
            if len(config_subnets) > 0 or len(config_shared) > 0:
                dhcpd_template = env.get_template(template)
                dhcpd_config = dhcpd_template.render(CLASSES=config_classes,SHARED=config_shared,SUBNETS=config_subnets,
                                                     HOSTS=config_hosts,POOLS=config_pools,DOMAINNAME=domain,
                                                     NAMESERVERS=nameserver_ip,NTPSERVERS=ntp_server,OMAPIKEY=omapikey)
                with open(dhcp_file, 'w', encoding='utf-8') as dhcp:
                    dhcp.write(dhcpd_config)
                try:
                    validate_config = subprocess.run(["dhcpd", "-t", "-cf", dhcp_file], check=True)
                    if validate_config.returncode:
                        validate = False
                        self.logger.error(f'DHCP file : {dhcp_file} containing errors.')
                except Exception as exp:
                    self.logger.info(exp)
                    validate = False
                    self.logger.error(f'DHCP file : {dhcp_file} containing errors.')
                else:
                    shutil.copyfile(dhcp_file, '/etc/dhcp/dhcpd.conf')
            # IPv6 -----------------------------------
            if len(config_subnets6) > 0 or len(config_shared6) > 0:
                dhcpd_template = env.get_template(template6)
                dhcpd_config = dhcpd_template.render(CLASSES=config_classes6,SHARED=config_shared6,SUBNETS=config_subnets6,
                                                     HOSTS=config_hosts6,POOLS=config_pools6,DOMAINNAME=domain,
                                                     NAMESERVERS=nameserver_ip,NAMESERVERS_IPV6=nameserver_ip_ipv6,
                                                     NTPSERVERS=ntp_server,OMAPIKEY=omapikey)
                with open(dhcp6_file, 'w', encoding='utf-8') as dhcp:
                    dhcp.write(dhcpd_config)
                try:
                    validate_config = subprocess.run(["dhcpd", '-6', "-t", "-cf", dhcp6_file], check=True)
                    if validate_config.returncode:
                        validate = False
                        self.logger.error(f'DHCP6 file : {dhcp6_file} containing errors.')
                except Exception as exp:
                    self.logger.info(exp)
                    validate = False
                    self.logger.error(f'DHCP6 file : {dhcp6_file} containing errors.')
                else:
                    shutil.copyfile(dhcp6_file, '/etc/dhcp/dhcpd6.conf')
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"building DHCP config encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            validate = False
        return validate


    def dhcp_subnet_config (self,nwk=[],shared=False,ipversion='ipv4'):
        """ 
        dhcp subnetblock with config
        glue between the various other subnet blocks: prepare for dhcp_subnet function
        """
        subnet={}
        add_string=''
        if ipversion == 'ipv6':
            add_string='_ipv6'
        network_id = nwk['id']
        network_name = nwk['name']+add_string
        network_ip = nwk['network'+add_string]
        if not shared:
            subnet['range_begin']=nwk['dhcp_range_begin'+add_string]
            subnet['range_end']=nwk['dhcp_range_end'+add_string]
        netmask = nwk['subnet_ipv6']
        if ipversion == 'ipv4':
            netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
        controller_name = Controller().get_beacon()
        # ---------------------------------------------------
        ha_object=HA()
        ha_enabled=ha_object.get_hastate()
        ha_insync=ha_object.get_insync()
        ha_master=ha_object.get_role()
        ha_me=ha_object.get_me()
        # ---------------------------------------------------
        if ha_enabled and ha_insync:
                controller_name = ha_me
        # ---------------------------------------------------
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as networkname'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', f"controller.hostname='{controller_name}'"]
        )
        self.logger.info(f"Building DHCP block for {network_name}")
        subnet['network']=nwk['network'+add_string]
        subnet['netmask']=netmask
        subnet['domain']=nwk['name']
        subnet['nameserver_ip']=nwk['nameserver_ip']
        subnet['nameserver_ip_ipv6']=nwk['nameserver_ip_ipv6']
        subnet['ntp_server']=nwk['ntp_server']
        if nwk['gateway'+add_string] and nwk['gateway'+add_string] != "None": # left over from database().update/insert bug - Antoine
            subnet['gateway']=nwk['gateway'+add_string]
        if controller and (controller[0]['networkname'] == nwk['name'] or 'gateway' in subnet):
            # if the controller is in this network (cluster default as such), we can serve next-server stuff.
            # we allow to have an alternate route to the next-server (which is us) but ONLY when gateway is configured,
            # this is usefull if we want to support booting on other networks as well.
            serverport = 7050
            if CONSTANT['API']['PROTOCOL'] == 'https' and 'WEBSERVER' in CONSTANT and 'PORT' in CONSTANT['WEBSERVER']:
                # we rely on nginx serving non https stuff for e.g. /boot.
                # ipxe does support https but has issues dealing with self signed certificates
                serverport = CONSTANT['WEBSERVER']['PORT']
            if controller[0]['ipaddress'+add_string]:
                subnet['nextserver']=controller[0]['ipaddress'+add_string]
            else:
                subnet['nextserver']=controller[0]['ipaddress']
            subnet['nextport']=serverport
        self.logger.debug(f"SUBNET: {subnet}")
        return subnet


    def dns_configure(self):
        """
        This method will write /etc/named.conf and zone files for every network
        """
        validate = True
        template_dns_conf = 'templ_dns_conf.cfg' # i.e. /etc/named.conf
        template_dns_zones_conf = 'templ_dns_zones_conf.cfg' # i.e. /etc/named.luna.zones
        template_dns_zone = 'templ_dns_zone.cfg' # the actual zone data
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_conf}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_zones_conf}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_zone}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        file_loader = FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"])
        env = Environment(loader=file_loader)

        tmpdir=f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}"
        files, forwarder = [], []
        unix_time = int(time())
        dns_allowed_query=['any']
        dns_zones=[]
        dns_zone_records={}
        dns_authoritative={}
        dns_rev_domain={}
 
        cluster = Database().get_record(None, 'cluster', None)
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as networkname'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.beacon=1']
        )
        if (not controller) or (not cluster):
            self.logger.error("Error building dns config. either controller or cluster does not exist")
            return False
        controller_name = Controller().get_beacon()
        controller_ip = controller[0]['ipaddress']
        controller_ip_ipv6 = controller[0]['ipaddress_ipv6']
        controller_network = controller[0]['networkname']
        if 'forwardserver_ip' in cluster[0] and cluster[0]['forwardserver_ip']:
            forwarder = cluster[0]['forwardserver_ip'].split(',')
        networks = Database().get_record(None, 'network', None)
        if networks:
            dns_allowed_query=['127.0.0.0/8']
 
        for nwk in networks:
            network_id = nwk['id']
            networkname = None
            rev_ip, rev_ipv6 = None, None
            if (nwk['network'] or nwk['network_ipv6']) and nwk['name']:
                networkname = nwk['name']
                self.logger.info(f"Building DNS block for {networkname}")
                try:
                    if nwk['network']:
                        rev_ip = ip_address(nwk['network']).reverse_pointer
                        rev_ip = rev_ip.split('.')
                        rev_ip = '.'.join(rev_ip[2:])
                        dns_allowed_query.append(nwk['network']+"/"+nwk['subnet']) # used for e.g. named. allow query
                        self.logger.info(f"Building DNS block for {rev_ip}")
                    if nwk['network_ipv6']:
                        rev_ipv6 = ip_address(nwk['network_ipv6']).reverse_pointer
                        rev_ipv6 = rev_ipv6.split('.')
                        rev_ipv6 = '.'.join(rev_ipv6[16:])
                        dns_allowed_query.append(nwk['network_ipv6']+"/"+nwk['subnet_ipv6'])
                        self.logger.info(f"Building DNS block for {rev_ipv6}")
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"defining networks encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                #
                dns_zones.append(networkname)
                if rev_ip and rev_ip not in dns_zones:
                    dns_zones.append(rev_ip)
                    dns_rev_domain[rev_ip]=networkname
                if rev_ipv6 and rev_ipv6 not in dns_zones:
                    dns_zones.append(rev_ipv6)
                    dns_rev_domain[rev_ipv6]=networkname
                dns_zone_records[networkname]={}
                # we always add a zone record for controller even when we're actually in it. we can override.
                dns_zone_records[networkname][controller_name]={}
                dns_zone_records[networkname][controller_name]['key']=controller_name
                if nwk['network_ipv6'] and controller_ip_ipv6:
                    dns_zone_records[networkname][controller_name]['type']='AAAA'
                    dns_zone_records[networkname][controller_name]['value']=controller_ip_ipv6
                else:
                    dns_zone_records[networkname][controller_name]['type']='A'
                    dns_zone_records[networkname][controller_name]['value']=controller_ip
                if rev_ip:
                    if rev_ip not in dns_zone_records.keys():
                        dns_zone_records[rev_ip]={}
                    dns_authoritative[rev_ip]=controller_name
                if rev_ipv6:
                    if rev_ipv6 not in dns_zone_records.keys():
                        dns_zone_records[rev_ipv6]={}
                    dns_authoritative[rev_ipv6]=controller_name
                dns_authoritative[networkname]=controller_name

            mergedlist = []
            controllers = Database().get_record_join(
                ['controller.hostname as host', 'ipaddress.ipaddress',
                 'ipaddress.ipaddress_ipv6','network.name as networkname'],
                ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                ['ipaddress.tableref="controller"', f'ipaddress.networkid="{network_id}"']
            )
            if controllers:
                mergedlist.append(controllers)
            nodes = Database().get_record_join(
                ['node.name as host', 'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6',
                  'network.name as networkname'],
                ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id',
                 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
            )
            if nodes:
                mergedlist.append(nodes)

            for item in ['otherdevices','switch']:
                devices = Database().get_record_join(
                    [f'{item}.name as host', 'ipaddress.ipaddress',
                     'ipaddress.ipaddress_ipv6', 'network.name as networkname'],
                    [f'ipaddress.tablerefid={item}.id', 'network.id=ipaddress.networkid'],
                    [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                )
                if devices:
                    mergedlist.append(devices)

            additional = Database().get_record_join(
                    ['dns.*','network.name as networkname'],
                    ['dns.networkid=network.id'],
                    [f"network.name='{networkname}'"])
            if additional:
                mergedlist.append(additional)

            for hosts in mergedlist:
                for host in hosts:
                    try:
                        dns_zone_records[networkname][host['host']]={}
                        dns_zone_records[networkname][host['host']]['key']=host['host'].rstrip('.')
                        if 'ipaddress_ipv6' in host and host['ipaddress_ipv6']:
                            dns_zone_records[networkname][host['host']]['type']='AAAA'
                            dns_zone_records[networkname][host['host']]['value']=host['ipaddress_ipv6']
                            self.logger.debug(f"DNS -- IPv6: host {host['host']}, AAAA ip [{host['ipaddress_ipv6']}]")
                            if rev_ipv6:
                                ipv6_rev = ip_address(host['ipaddress_ipv6']).reverse_pointer
                                ipv6_list = ipv6_rev.split('.')
                                host_ptr = '.'.join(ipv6_list[0:16])
                                self.logger.debug(f"DNS -- IPv6: host {host['host']}, rev ip [{host_ptr}]")
                                if host['host'] not in dns_zone_records[rev_ipv6].keys():
                                    dns_zone_records[rev_ipv6][host['host']]={}
                                    dns_zone_records[rev_ipv6][host['host']]['key']=host_ptr
                                    dns_zone_records[rev_ipv6][host['host']]['type']='PTR'
                                    dns_zone_records[rev_ipv6][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"
                        elif host['ipaddress']:
                            dns_zone_records[networkname][host['host']]['type']='A'
                            dns_zone_records[networkname][host['host']]['value']=host['ipaddress']
                            self.logger.debug(f"DNS -- IPv4: host {host['host']}, A ip [{host['ipaddress']}]")
                            if rev_ip:
                                sub_ip = host['ipaddress'].split('.')
                                if len(sub_ip) == 4:
                                    host_ptr = sub_ip[3] + '.' + sub_ip[2]
                                    self.logger.debug(f"DNS -- IPv4: host {host['host']}, rev ip [{host_ptr}]")
                                    if host['host'] not in dns_zone_records[rev_ip].keys():
                                        dns_zone_records[rev_ip][host['host']]={}
                                        dns_zone_records[rev_ip][host['host']]['key']=host_ptr
                                        dns_zone_records[rev_ip][host['host']]['type']='PTR'
                                        dns_zone_records[rev_ip][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"
                    except Exception as exp:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        self.logger.error(f"creating zone file encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")

        # we create the zone files with zone info like addresses
        for zone in dns_zones:
            zone_file = {
                'source': f'{tmpdir}/{zone}.luna.zone',
                'destination': f'/var/named/{zone}.luna.zone'
            }
            files.append(zone_file)
            try:
                dns_zone_template = env.get_template(template_dns_zone)
                networkname=zone
                if zone in dns_rev_domain:
                    networkname=dns_rev_domain[zone]
                dns_zone_config = dns_zone_template.render(RECORDS=dns_zone_records[zone],
                                                           AUTHORITATIVE_SERVER=f"{controller_name}.{networkname}",
                                                           SERIAL=unix_time)
                with open(f'{tmpdir}/{zone}.luna.zone', 'w', encoding='utf-8') as filename:
                    filename.write(dns_zone_config)
                try:
                    zone_cmd = ['named-checkzone', f'luna.{zone}', f'{tmpdir}/{zone}.luna.zone']
                    validate_zone_name = subprocess.run(zone_cmd, check = True)
                    if validate_zone_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {tmpdir}/{zone}.luna.zone containing errors.')
                except Exception as exp:
                    self.logger.error(f'DNS zone file: {tmpdir}/{zone}.luna.zone containing errors. {exp}')
            except Exception as exp:
                self.logger.error(f"Uh oh... {exp}")

        # we create the actual /etc/named.conf and /etc/named.luna.zones
        managed_keys="/trinity/local/var/lib/named/dynamic"
        if not os.path.exists(managed_keys):
            managed_keys=None
        dns_conf_template = env.get_template(template_dns_conf)
        dns_conf_config = dns_conf_template.render(ALLOWED_QUERY=dns_allowed_query,FORWARDERS=forwarder,MANAGED_KEYS=managed_keys)
        dns_zones_conf_template = env.get_template(template_dns_zones_conf)
        dns_zones_conf_config = dns_zones_conf_template.render(ZONES=dns_zones)

        dns_file = {'source': f'{tmpdir}/named.conf', 'destination': '/etc/named.conf'}
        files.append(dns_file)
        dns_zone_file = {
                'source': f'{tmpdir}/named.luna.zones',
                'destination': '/etc/named.luna.zones'
        }
        files.append(dns_zone_file)
        try:
            with open(dns_file["source"], 'w', encoding='utf-8') as dns:
                dns.write(dns_conf_config)
            with open(dns_zone_file["source"], 'w', encoding='utf-8') as dns_zone:
                dns_zone.write(dns_zones_conf_config)
            if validate:
                if not os.path.exists('/var/named'):
                    os.makedirs('/var/named')
                for dns_files in files:
                    shutil.copyfile(dns_files["source"], dns_files["destination"])
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    # ----------------------------------------------------------------------------------------------

    def device_raw_ipaddress_config(self, device_id=None, device=None, ipaddress=None):
        """
        This method will set the ipaddress as is. no checks.
        """
        if not ipaddress:
            return False, "IP address not supplied"
        result_ip = False
        my_ipaddress = {}
        if Helper().check_if_ipv6(ipaddress):
            my_ipaddress={'ipaddress_ipv6': ipaddress, 'networkid': None}
        else:
            my_ipaddress={'ipaddress': ipaddress, 'networkid': None}
        where = f'WHERE tablerefid = "{device_id}" AND tableref = "{device}"'
        check_ip = Database().get_record(None, 'ipaddress', where)
        if check_ip:
            row = Helper().make_rows(my_ipaddress)
            where = [
                {"column": "tablerefid", "value": device_id},
                {"column": "tableref", "value": device}
            ]
            result_ip=Database().update('ipaddress', row, where)
        else:
            my_ipaddress['tableref'] = device
            my_ipaddress['tablerefid'] = device_id
            row = Helper().make_rows(my_ipaddress)
            result_ip=Database().insert('ipaddress', row)
            self.logger.info(f"IP for {device} created => {result_ip}.")
        if result_ip is False:
            return False,"IP address assignment failed"
        return True,"ip address changed"
    
    # ----------------------------------------------------------------------------------------------

    def device_ipaddress_config(self, device_id=None, device=None, ipaddress=None, network=None):
        """
        This method will verify the ipaddress with supplied or pre-configured network and sets it 
        """
        if network:
            network_id = Database().id_by_name('network', network)
        else:
            network_details = Database().get_record_join(
                ['network.name as network', 'network.id'],
                ['ipaddress.tablerefid=switch.id', 'network.id=ipaddress.networkid'],
                [f'tableref="{device}"', f"switch.id='{device_id}'"]
            )
            if network_details:
                network_id = network_details[0]['id']
            else:
                return False,"Network not specified"
        if ipaddress and device_id and network_id:
            my_ipaddress = {}
            my_ipaddress['networkid'] = network_id
            result_ip, valid_ip = False, None
            network_details = Database().get_record(None, 'network', f"WHERE id='{network_id}'")
            if Helper().check_if_ipv6(ipaddress):
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
                )
            else:
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                )
            self.logger.info(f"Ipaddress {ipaddress} for {device} is [{valid_ip}]")
            if valid_ip is False:
                message = f"invalid IP address for {device}. Network {network_details[0]['name']}: "
                message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                return False, message

            if Helper().check_if_ipv6(ipaddress):
                my_ipaddress['ipaddress_ipv6']=ipaddress
            else:
                my_ipaddress['ipaddress']=ipaddress
            where = f'WHERE tablerefid = "{device_id}" AND tableref = "{device}"'
            check_ip = Database().get_record(None, 'ipaddress', where)
            if check_ip:
                row = Helper().make_rows(my_ipaddress)
                where = [
                    {"column": "tablerefid", "value": device_id},
                    {"column": "tableref", "value": device}
                ]
                Database().update('ipaddress', row, where)
            else:
                my_ipaddress['tableref'] = device
                my_ipaddress['tablerefid'] = device_id
                row = Helper().make_rows(my_ipaddress)
                result_ip=Database().insert('ipaddress', row)
                self.logger.info(f"IP for {device} created => {result_ip}.")
                if result_ip is False:
                    return False,"IP address assignment failed"
            return True,"ip address changed"
        return False,"not enough details"


    def node_interface_config(self, nodeid=None, interface_name=None, macaddress=None, vlanid=None, options=None):
        """
        This method will collect node interfaces and return configuration.
        """
        result_if = False
        my_interface = {}

        where_interface = f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(None, 'nodeinterface', where_interface)

        if macaddress is not None:
            my_interface['macaddress'] = macaddress.lower()
        if options is not None:
            my_interface['options'] = options
        if vlanid is not None:
            my_interface['vlanid'] = vlanid

        if not check_interface: # ----> easy. both the interface and ipaddress do not exist
            my_interface['interface'] = interface_name
            my_interface['nodeid'] = nodeid
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('nodeinterface', row)
        else:
            # we have to update the interface
            if my_interface:
                row = Helper().make_rows(my_interface)
                where = [{"column": "id", "value": check_interface[0]['id']}]
                result_if = Database().update('nodeinterface', row, where)
            else:
                # no change here, we bail
                result_if=True

        if result_if:
            message = f"interface {interface_name} created or changed with result {result_if}"
            self.logger.info(message)
            return True, message
        message = f"interface {interface_name} config failed with result {result_if}"
        self.logger.info(message)
        return False, message


    def node_interface_clear_ipaddress(self, nodeid, interface_name, ipversion='ipv4'):
        """
        This method will clear (None) the ipaddress config of a given node interface
        """
        where_interface = f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(None, 'nodeinterface', where_interface)
        if check_interface:
            clear_ip={}
            if ipversion == 'ipv4':
                clear_ip['ipaddress'] = None
            if ipversion == 'ipv6':
                clear_ip['ipaddress_ipv6'] = None
            row = Helper().make_rows(clear_ip)
            where = [{"column": "tableref", "value": "nodeinterface"},
                     {"column": "tablerefid", "value": check_interface[0]['id']}]
            result_if = Database().update('ipaddress', row, where)
        if result_if:
            message = f"interface {interface_name} cleared of {ipversion} address with result {result_if}"
            self.logger.info(message)
            return True, message
        message = f"interface {interface_name} config failed with result {result_if}"
        self.logger.info(message)
        return False, message


    def node_interface_ipaddress_config(self, nodeid, interface_name, ipaddress,network=None):
        """
        This method will collect ipaddress of node interfaces and return configuration.
        """
        ipaddress_check, valid_ip, result_ip = False, False, False
        my_ipaddress = {}

        if network is not None:
            network_details = Database().get_record(None, 'network', f'WHERE name="{network}"')
        else:
            network_details = Database().get_record_join(
                ['network.*'],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                [
                    'tableref="nodeinterface"',
                    f'nodeinterface.nodeid="{nodeid}"',
                    f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if not network_details:
            message = "not enough information provided. network name incorrect or need network name if there is no existing ipaddress"
            self.logger.info(message)
            return False, message

        my_ipaddress['networkid'] = network_details[0]['id']
        if ipaddress:
            if Helper().check_if_ipv6(ipaddress):
                my_ipaddress['ipaddress_ipv6'] = ipaddress
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
                )
            else:
                my_ipaddress['ipaddress'] = ipaddress
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                )

        if not valid_ip:
            message = f"invalid IP address {ipaddress} for {interface_name}. "
            message += f"Network {network_details[0]['name']}: "
            if network_details[0]['network']:
                message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"+" "
            if network_details[0]['network_ipv6']:
                message += f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
            self.logger.info(message)
            return False, message

        ipaddress_check = Database().get_record(None, 'ipaddress', f"WHERE ipaddress='{ipaddress}' or ipaddress_ipv6='{ipaddress}'")
        if ipaddress_check:
            ipaddress_type='ipaddress'
            if Helper().check_if_ipv6(ipaddress):
                ipaddress_type='ipaddress_ipv6'
            ipaddress_check_own = Database().get_record_join(
                ['node.id as nodeid','nodeinterface.interface'],
                ['ipaddress.tablerefid=nodeinterface.id','nodeinterface.nodeid=node.id'],
                ['tableref="nodeinterface"',f"ipaddress.{ipaddress_type}='{ipaddress}'"]
            )
            if ipaddress_check_own and ((ipaddress_check_own[0]['nodeid'] != nodeid) or (interface_name != ipaddress_check_own[0]['interface'])):
                return False, f"ip address {ipaddress} is already in use"

        ipaddress_check = Database().get_record_join(
            ['ipaddress.*'],
            ['ipaddress.tablerefid=nodeinterface.id'],
            [
                'tableref="nodeinterface"',
                f'nodeinterface.nodeid="{nodeid}"',
                f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if ipaddress_check: # existing ip config we need to modify
            row = Helper().make_rows(my_ipaddress)
            where = [{"column": "id", "value": f"{ipaddress_check[0]['id']}"}]
            result_ip = Database().update('ipaddress', row, where)

        else:
            # no ip set yet for the interface
            where = f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"'
            check_interface = Database().get_record(None, 'nodeinterface', where)
            if check_interface:
                my_ipaddress['tableref']='nodeinterface'
                my_ipaddress['tablerefid']=check_interface[0]['id']
                row = Helper().make_rows(my_ipaddress)
                result_ip = Database().insert('ipaddress', row)

        if result_ip:
            message = f"ipaddress for {interface_name} configured with result {result_ip}"
            self.logger.info(message)
            return True, message
        message = f"ipaddress for {interface_name} config failed with result {result_ip}"
        self.logger.info(message)
        return False, message


    def update_interface_on_group_nodes(self, name=None, request_id=None):
        """
        This method will update node/group interfaces.
        It's called from a group add/change (base/group + base/interface). it handles all nodes in that group.
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_on_group_nodes called")
        try:
            while next_id := Queue().next_task_in_queue('group_interface'):
                message = f"update_interface_on_group_nodes sees job in queue as next: {next_id}"
                self.logger.info(message)
                details=Queue().get_task_details(next_id)
                # request_id = details['request_id']
                action = details['task']
                group, interface, *_ = details['param'].split(':') + [None]

                if group == name:
                    # ADDING/UPDATING --------------------------------------------------------
                    if (action in ['add_interface_to_group_nodes', 'update_interface_for_group_nodes']) and interface:
                        network = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.networkid as networkid',
                                'network.network', 'network.network_ipv6',
                                'network.subnet', 'network.subnet_ipv6',
                                'network.name as networkname',
                                'groupinterface.vlanid'
                            ],
                            [
                                'ipaddress.networkid=network.id',
                                'network.id=groupinterface.networkid',
                                'groupinterface.groupid=group.id'
                            ],
                            [f"`group`.name='{group}'", f"groupinterface.interface='{interface}'"]
                        )
                        if not network: # as in we did not have any ipaddress used...
                            network = Database().get_record_join(
                                [
                                    'network.id as networkid',
                                    'network.network', 'network.network_ipv6',
                                    'network.subnet', 'network.subnet_ipv6',
                                    'network.name as networkname',
                                    'groupinterface.vlanid'
                                ],
                                [
                                    'network.id=groupinterface.networkid',
                                    'groupinterface.groupid=group.id'
                                ],
                                [
                                    f"`group`.name='{group}'",
                                    f"groupinterface.interface='{interface}'"
                                ]
                            )
                        dhcp_ips = []
                        dhcp6_ips = []
                        vlanid = None
                        if network:
                            dhcp_ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'])
                            dhcp6_ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'],'ipv6')
                            vlanid = network[0]['vlanid']
                        ips = dhcp_ips.copy()
                        ips6 = dhcp6_ips.copy()
                        if network: 
                            if 'ipaddress' in network[0]:
                                for ip in network:
                                    ips.append(ip['ipaddress'])
                            if 'ipaddress_ipv6' in network[0]:
                                for ip in network:
                                    ips6.append(ip['ipaddress_ipv6'])
                        nodes = Database().get_record_join(
                            ['node.id as nodeid'],
                            ['node.groupid=group.id'],
                            [f"`group`.name='{group}'"]
                        )
                        if nodes:
                            for node in nodes:
                                check, text = self.node_interface_config(nodeid=node['nodeid'], interface_name=interface, vlanid=vlanid)
                                message = f"Adding/Updating interface {interface} to node id "
                                message += f"{node['nodeid']} for group {group}. {text}"
                                self.logger.info(message)
                                if check and network:
                                    valid_ip, avail, valid_ip6, avail6 = None, None, None, None
                                    if action == 'update_interface_for_group_nodes':
                                        ip_details = Database().get_record_join(
                                            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
                                            ['ipaddress.tablerefid=nodeinterface.id'],
                                            [
                                                "ipaddress.tableref='nodeinterface'",
                                                f"nodeinterface.nodeid=\"{node['nodeid']}\"",
                                                f"nodeinterface.interface='{interface}'"
                                            ]
                                        )
                                        if ip_details:
                                            if network[0]['network']:
                                                valid_ip = Helper().check_ip_range(
                                                    ip_details[0]['ipaddress'],
                                                    f"{network[0]['network']}/{network[0]['subnet']}"
                                                )
                                            if network[0]['network_ipv6']:
                                                valid_ip6 = Helper().check_ip_range(
                                                    ip_details[0]['ipaddress_ipv6'],
                                                    f"{network[0]['network_ipv6']}/{network[0]['subnet_ipv6']}"
                                                )
                                        if valid_ip and ip_details[0]['ipaddress'] not in dhcp_ips:
                                            avail = ip_details[0]['ipaddress']
                                            self.logger.info(f"---> reusing ipaddress {avail}")
                                        if valid_ip6 and ip_details[0]['ipaddress_ipv6'] not in dhcp_ips6:
                                            avail6 = ip_details[0]['ipaddress_ipv6']
                                            self.logger.info(f"---> reusing ipaddress {avail6}")

                                    # IPv4, ipv4 ------------------------------
                                    if network[0]['network'] and not avail:
                                        avail = Helper().get_available_ip(
                                            network[0]['network'],
                                            network[0]['subnet'],
                                            ips, ping=True
                                        )

                                    if avail:
                                        ipaddress = avail
                                        ips.append(ipaddress)
                                        _, response = self.node_interface_ipaddress_config(
                                            node['nodeid'],
                                            interface,
                                            ipaddress,
                                            network[0]['networkname']
                                        )
                                        message = f"Adding IP {ipaddress} to node id "
                                        message += f"{node['nodeid']} for group {group} interface "
                                        message += f"{interface}. {response}"
                                        self.logger.info(message)

                                    if not network[0]['network']:
                                        _, response = self.node_interface_clear_ipaddress(
                                            node['nodeid'],
                                            interface,
                                            'ipv4'
                                        )

                                    # IPv6, ipv6 ------------------------------
                                    if network[0]['network_ipv6'] and not avail6:
                                        avail6 = Helper().get_available_ip(
                                            network[0]['network_ipv6'],
                                            network[0]['subnet_ipv6'],
                                            ips6, ping=True
                                        )

                                    if avail6:
                                        ipaddress = avail6
                                        ips6.append(ipaddress)
                                        _, response = self.node_interface_ipaddress_config(
                                            node['nodeid'],
                                            interface,
                                            ipaddress,
                                            network[0]['networkname']
                                        )
                                        message = f"Adding IP {ipaddress} to node id "
                                        message += f"{node['nodeid']} for group {group} interface "
                                        message += f"{interface}. {response}"
                                        self.logger.info(message)

                                    if not network[0]['network_ipv6']:
                                        _, response = self.node_interface_clear_ipaddress(
                                            node['nodeid'],
                                            interface,
                                            'ipv6'
                                        )

                    # DELETING --------------------------------------------------------------
                    elif action == 'delete_interface_from_group_nodes' and interface:
                        nodes = Database().get_record_join(
                            [
                                'node.id as nodeid',
                                'nodeinterface.id as ifid',
                                'ipaddress.id as ipid'
                            ],
                            [
                                'ipaddress.tablerefid=nodeinterface.id',
                                'nodeinterface.nodeid=node.id',
                                'node.groupid=group.id'
                            ],
                            [
                                f"`group`.name='{name}'",
                                f"nodeinterface.interface='{interface}'",
                                'ipaddress.tableref="nodeinterface"'
                            ]
                        )
                        if nodes:
                            for node in nodes:
                                Database().delete_row(
                                    'ipaddress',
                                    [{"column": "id", "value": node['ipid']}]
                                )
                                Database().delete_row(
                                    'nodeinterface',
                                    [{"column": "id", "value": node['ifid']}]
                                )

                        nodes = Database().get_record_join(
                            ['node.id as nodeid', 'nodeinterface.id as ifid'],
                            ['nodeinterface.nodeid=node.id','node.groupid=group.id'],
                            [f"`group`.name='{name}'",f"nodeinterface.interface='{interface}'"]
                        )
                        if nodes:
                            for node in nodes:
                                Database().delete_row(
                                    'nodeinterface',
                                    [{"column": "id", "value": node['ifid']}]
                                )
                    Queue().remove_task_from_queue(next_id)
                    Queue().add_task_to_queue(task='restart', param='dns',
                                              subsystem='housekeeper',
                                              request_id='__update_interface_on_group_nodes__')
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"update_interface_on_group_nodes has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")


    def update_interface_ipaddress_on_network_change(self, name=None, request_id=None):  #name=network
        """
        This method will update ipaddress of node/group interface.
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_ipaddress_on_network_change called")
        try:
            while next_id := Queue().next_task_in_queue('network_change'):
                message = "update_interface_ipaddress_on_network_change "
                message += f"sees job in queue as next: {next_id}"
                self.logger.info(message)
                details = Queue().get_task_details(next_id)
                action = details['task']
                network, *_ = details['param'].split(':') + [None]

                if (name and network==name) or network:
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if action == 'update_all_interface_ipaddress':
                        ips = self.get_dhcp_range_ips_from_network(network)
                        ips6 = self.get_dhcp_range_ips_from_network(network,'ipv6')
                        ipaddress_list = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.networkid as networkid',
                                'network.network',
                                'network.subnet',
                                'network.network_ipv6',
                                'network.subnet_ipv6',
                                'network.name as networkname',
                                'ipaddress.id as ipaddressid',
                                'ipaddress.tableref',
                                'ipaddress.tablerefid'
                            ],
                            ['ipaddress.networkid=network.id'],
                            [f"network.name='{network}'"]
                        )
                        if ipaddress_list:
                            for ipaddress in ipaddress_list:
                                # we assume that there's always either configured. ipv4 or ipv6
                                ret, avail, avail6, maximum = 0, ipaddress['ipaddress'], ipaddress['ipaddress_ipv6'], 5
                                we_continue = False
                                we_continue6 = False
                                if ipaddress['network']:
                                    if not ipaddress['network_ipv6']:
                                        avail6 = None
                                        we_continue6 = True
                                    valid_ip = Helper().check_ip_range(ipaddress['ipaddress'],
                                        f"{ipaddress['network']}/{ipaddress['subnet']}"
                                    )
                                    if valid_ip and ipaddress['ipaddress'] not in ips:
                                        ips.append(ipaddress['ipaddress'])
                                        self.logger.info(f"For network {network} no change for IP {ipaddress['ipaddress']}")
                                        we_continue = True
                                if ipaddress['network_ipv6']:
                                    if not ipaddress['network']:
                                        avail = None
                                        we_continue = True
                                    valid_ip6 = Helper().check_ip_range(ipaddress['ipaddress_ipv6'],
                                        f"{ipaddress['network_ipv6']}/{ipaddress['subnet_ipv6']}"
                                    )
                                    if valid_ip6 and ipaddress['ipaddress_ipv6'] not in ips6:
                                        ips6.append(ipaddress['ipaddress_ipv6'])
                                        self.logger.info(f"For network {network} no change for IP {ipaddress['ipaddress_ipv6']}")
                                        we_continue6 = True
                                if we_continue and we_continue6:
                                    continue
                                if not we_continue:
                                    avail = Helper().get_available_ip(
                                        ipaddress['network'],
                                        ipaddress['subnet'],
                                        ips, ping=True
                                    )
                                if not we_continue6:
                                    avail6 = Helper().get_available_ip(
                                        ipaddress['network_ipv6'],
                                        ipaddress['subnet_ipv6'],
                                        ips6, ping=True
                                    )
                                message = f"For network {network} changing IP "
                                if avail:
                                    # row   = [{"column": "ipaddress", "value": f"{avail}"}]
                                    # where = [{"column": "id", "value": f"{ipaddress['ipaddressid']}"}]
                                    # message = Database().update('ipaddress', row, where)
                                    Database().delete_row(
                                        'ipaddress',
                                        [{"column": "ipaddress", "value": avail}]
                                    )
                                    ips.append(avail)
                                if avail6:
                                    Database().delete_row(
                                        'ipaddress',
                                        [{"column": "ipaddress_ipv6", "value": avail6}]
                                    )
                                    ips6.append(avail6)
                                if avail or avail6:
                                    Database().delete_row(
                                        'ipaddress',
                                        [
                                            {"column": "tableref", "value": f"{ipaddress['tableref']}"},
                                            {"column": "tablerefid", "value": f"{ipaddress['tablerefid']}"}
                                        ]
                                    )
                                    row = [
                                        {"column": "ipaddress", "value": avail},
                                        {"column": "ipaddress_ipv6", "value": avail6},
                                        {"column": "networkid", "value": f"{ipaddress['networkid']}"},
                                        {"column": "tableref", "value": f"{ipaddress['tableref']}"},
                                        {"column": "tablerefid", "value": f"{ipaddress['tablerefid']}"}
                                    ]
                                    result = Database().insert('ipaddress', row)

                                    message += f"{ipaddress['ipaddress']} to {avail} and {ipaddress['ipaddress_ipv6']} to {avail6}. {result}"
                                    self.logger.info(message)
                                else:
                                    message += f"{ipaddress['ipaddress']} or {ipaddress['ipaddress_ipv6']} not possible. "
                                    message += "no free IP addresses available."
                                    self.logger.error(message)
                    Queue().remove_task_from_queue(next_id)
                    Queue().add_task_to_queue(task='restart', param='dns', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                    Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                    Queue().add_task_to_queue(task='restart', param='dhcp6', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"update_interface_ipaddress_on_network_change has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")


    def update_dhcp_range_on_network_change(self, name=None, request_id=None): # name=network
        """
        This method will update dhcp range, when network will changes.
        """
        self.logger.info(f'request_id: {request_id}')
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            for ipv in ['', '_ipv6']:
                if network[0]['dhcp_range_begin'+ipv] and network[0]['dhcp_range_end'+ipv]:
                    subnet = network[0]['network'+ipv]+'/'+network[0]['subnet'+ipv]
                    dhcp_begin_ok = Helper().check_ip_range(network[0]['dhcp_range_begin'+ipv], subnet)
                    dhcp_end_ok = Helper().check_ip_range(network[0]['dhcp_range_end'+ipv], subnet)
                    if dhcp_begin_ok and dhcp_end_ok:
                        message = f"{network[0]['network'+ipv]}/{network[0]['subnet'+ipv]} :: dhcp "
                        message += f"{network[0]['dhcp_range_begin'+ipv]}-{network[0]['dhcp_range_end'+ipv]} "
                        message += "fits with in network range. no change"
                        self.logger.info(message)
                        return True
                    dhcp_size = Helper().get_ip_range_size(
                        network[0]['dhcp_range_begin'+ipv],
                        network[0]['dhcp_range_end'+ipv]
                    )
                    nwk_size = Helper().get_network_size(network[0]['network'+ipv], network[0]['subnet'+ipv])
                    if ((100 * dhcp_size) / nwk_size) > 50: # == 50%
                        dhcp_size = int(nwk_size / 10)
                        # we reduce this to 10%
                        # how many,  offset start
                    dhcp_begin, dhcp_end = Helper().get_ip_range_first_last_ip(
                        network[0]['network'+ipv],
                        network[0]['subnet'+ipv],
                        dhcp_size, (int(nwk_size / 2) - 4)
                    )
                    message = f"{network[0]['network'+ipv]}/{network[0]['subnet'+ipv]}"
                    message += f" :: new dhcp range {dhcp_begin}-{dhcp_end}"
                    self.logger.info(message)
                    if dhcp_begin and dhcp_end:
                        row = [
                            {"column": f"dhcp_range_begin{ipv}", "value": f"{dhcp_begin}"},
                            {"column": f"dhcp_range_end{ipv}", "value": f"{dhcp_end}"}
                        ]
                        where = [{"column": "name", "value": f"{name}"}]
                        Database().update('network', row, where)
                        Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper',
                                                  request_id='__update_dhcp_range_on_network_change__')


    def get_dhcp_range_ips_from_network(self, network=None, ipversion='ipv4'):
        """
        This method will return dhcp range for network.
        """
        ips = []
        network_details = Database().get_record(None, 'network', f' WHERE `name` = "{network}"')
        if network_details:
            if ipversion == 'ipv6' and network_details[0]['dhcp_range_begin_ipv6'] and network_details[0]['dhcp_range_end_ipv6']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin_ipv6'],
                    network_details[0]['dhcp_range_end_ipv6']
                )
            elif network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin'],
                    network_details[0]['dhcp_range_end']
                )
        return ips


    def get_all_occupied_ips_from_network(self, network=None, ipversion='ipv4'):
        """
        This method will return all occupied IP from a network.
        """
        ips = []
        network_details = Database().get_record(None, 'network', f' WHERE `name` = "{network}"')
        if network_details:
            if ipversion == 'ipv6' and network_details[0]['dhcp_range_begin_ipv6'] and network_details[0]['dhcp_range_end_ipv6']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin_ipv6'],
                    network_details[0]['dhcp_range_end_ipv6']
                )
            elif network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin'],
                    network_details[0]['dhcp_range_end']
                )
        network_details = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
            ['network.id=ipaddress.networkid'],
            [f"network.name='{network}'"]
        )
        if network_details:
            if ipversion == 'ipv6':
                for each in network_details:
                    ips.append(each['ipaddress_ipv6'])
            else:
                for each in network_details:
                    ips.append(each['ipaddress'])
        reserved_details = Database().get_record(None, "reservedipaddress", f"WHERE version='{ipversion}'")
        if reserved_details:
            for each in reserved_details:
                ips.append(each['ipaddress'])
        return ips

