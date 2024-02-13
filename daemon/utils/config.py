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
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        ntp_server, nameserver_ip = None, None
        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            if 'ntp_server' in cluster[0] and cluster[0]['ntp_server']:
                ntp_server = cluster[0]['ntp_server']
            if 'nameserver_ip' in cluster[0] and cluster[0]['nameserver_ip']:
                nameserver_ip = cluster[0]['nameserver_ip']
        dhcp_file = f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}/dhcpd.conf"
        domain = None
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','network.name as domain'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if controller:
            domain=controller[0]['domain']
            ntp_server = ntp_server or controller[0]['ipaddress']
            nameserver_ip = nameserver_ip or controller[0]['ipaddress']
        #
        omapikey=None
        if CONSTANT['DHCP']['OMAPIKEY']:
            omapikey=CONSTANT['DHCP']['OMAPIKEY']
        #
        config_classes = {}
        config_shared = {}
        config_subnets = {}
        config_hosts = {}
        config_pools = {}
        #
        networksbyname = {}
        networks = Database().get_record(None, 'network', ' WHERE `dhcp` = 1')
        if networks:
            networksbyname = Helper().convert_list_to_dict(networks, 'name')

        shared = {}
        for network in networksbyname.keys():
            if networksbyname[network]['shared'] and networksbyname[network]['shared'] in networksbyname.keys():
                if not networksbyname[network]['shared'] in shared.keys():
                    shared[networksbyname[network]['shared']] = []
                shared[networksbyname[network]['shared']].append(network)

        handled = []
        for network in shared.keys():
            shared_dhcp_pool, denied_dhcp_pool = [], []
            shared_name = f"{network}-" + "-".join(shared[network])
            #
            config_pools[shared_name]={}
            config_pools[shared_name]['policy']='deny'
            config_pools[shared_name]['members']=shared[network]
            config_pools[shared_name]['range_begin']=networksbyname[network]['dhcp_range_begin']
            config_pools[shared_name]['range_end']=networksbyname[network]['dhcp_range_end']
            #
            config_shared[shared_name]={}
            config_shared[shared_name][network]=self.dhcp_subnet_config(networksbyname[network],'shared')
            handled.append(network)
            #
            for piggyback in shared[network]:
                config_pools[piggyback]={}
                config_pools[piggyback]['policy']='allow'
                config_pools[piggyback]['members']=[piggyback]
                config_pools[piggyback]['range_begin']=networksbyname[piggyback]['dhcp_range_begin']
                config_pools[piggyback]['range_end']=networksbyname[piggyback]['dhcp_range_end']
                #
                config_shared[shared_name][piggyback]=self.dhcp_subnet_config(networksbyname[piggyback],'shared')
                config_classes[piggyback]={}
                config_classes[piggyback]['network']=piggyback
                handled.append(piggyback)
            #
        if networksbyname:
            for network in networksbyname.keys():
                nwk = networksbyname[network]
                if nwk['name'] not in handled:
                    config_subnets[nwk['name']] = self.dhcp_subnet_config(nwk)
                    handled.append(nwk['name'])
                network_id = nwk['id']
                network_name = nwk['name']
                network_ip = nwk['network']
                node_interface = Database().get_record_join(
                    ['node.name as nodename', 'ipaddress.ipaddress', 'nodeinterface.macaddress'],
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
                            config_hosts[node]={}
                            config_hosts[node]['name']=interface['nodename']
                            config_hosts[node]['domain']=nodedomain
                            config_hosts[node]['ipaddress']=interface['ipaddress']
                            config_hosts[node]['macaddress']=interface['macaddress']
                else:
                    self.logger.info(f'No Nodes available for this network {network_name}  {network_ip}')
                for item in ['otherdevices', 'switch']:
                    devices = Database().get_record_join(
                        [f'{item}.name','ipaddress.ipaddress',f'{item}.macaddress'],
                        [f'ipaddress.tablerefid={item}.id'],
                        [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                    )
                    if devices:
                        for device in devices:
                            if device['macaddress']:
                                config_hosts[device['name']]={}
                                config_hosts[device['name']]['name']=device['name']
                                config_hosts[device['name']]['ipaddress']=device['ipaddress']
                                config_hosts[device['name']]['maccaddress']=device['macaddress']
                    else:
                        self.logger.debug(f'{item} not available for {network_name} {network_ip}')
        
        try:
            file_loader = FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"])
            env = Environment(loader=file_loader)
            dhcpd_template = env.get_template(template)
            dhcpd_config = dhcpd_template.render(CLASSES=config_classes,SHARED=config_shared,SUBNETS=config_subnets,
                                                 HOSTS=config_hosts,POOLS=config_pools,DOMAINNAME=domain,
                                                 NAMESERVERS=nameserver_ip,TIMESERVERS=ntp_server,OMAPIKEY=omapikey)
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
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    def dhcp_subnet_config (self,nwk=[],shared=False):
        """ 
        dhcp subnetblock with config
        glue between the various other subnet blocks: prepare for dhcp_subnet function
        """
        subnet={}
        network_id = nwk['id']
        network_name = nwk['name']
        network_ip = nwk['network']
        if not shared:
            subnet['range_begin']=nwk['dhcp_range_begin']
            subnet['range_end']=nwk['dhcp_range_end']
        netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
        controller_name = 'controller'
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
            ['ipaddress.ipaddress','network.name as networkname'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', f"controller.hostname='{controller_name}'"]
        )
        self.logger.info(f"Building DHCP block for {network_name}")
        subnet['network']=nwk['network']
        subnet['netmask']=netmask
        subnet['domain']=nwk['name']
        subnet['nameserver_ip']=nwk['nameserver_ip']
        subnet['ntp_server']=nwk['ntp_server']
        if nwk['gateway'] and nwk['gateway'] != "None": # left over from database().update/insert bug - Antoine
            subnet['gateway']=nwk['gateway']
        if controller and (controller[0]['networkname'] == nwk['name'] or 'gateway' in subnet):
            # if the controller is in this network (cluster default as such), we can serve next-server stuff.
            # we allow to have an alternate route to the next-server (which is us) but ONLY when gateway is configured,
            # this is usefull if we want to support booting on other networks as well.
            serverport = 7050
            if CONSTANT['API']['PROTOCOL'] == 'https' and 'WEBSERVER' in CONSTANT and 'PORT' in CONSTANT['WEBSERVER']:
                # we rely on nginx serving non https stuff for e.g. /boot.
                # ipxe does support https but has issues dealing with self signed certificates
                serverport = CONSTANT['WEBSERVER']['PORT']
            subnet['nextserver']=controller[0]['ipaddress']
            subnet['nextport']=serverport
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
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        if (not controller) or (not cluster):
            self.logger.error("Error building dns config. either controller or cluster does not exist")
            return False
        controller_ip = controller[0]['ipaddress']
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
            if nwk['network'] and nwk['name']:
                networkname = nwk['name']
                self.logger.info(f"Building DNS block for {networkname}")
                if nwk['network']:
                    rev_ip = ip_address(nwk['network']).reverse_pointer
                    rev_ip = rev_ip.split('.')
                    rev_ip = '.'.join(rev_ip[2:])
                if nwk['network_ipv6']:
                    rev_ipv6 = ip_address(nwk['network_ipv6']).reverse_pointer
                    rev_ipv6 = rev_ipv6.split('.')
                    rev_ipv6 = '.'.join(rev_ipv6[16:])
                    self.logger.info(f"-----------------> rev_ipv6: {rev_ipv6}, {ip_address(nwk['network_ipv6']).reverse_pointer}, {nwk['network_ipv6']}")
                self.logger.info(f"Building DNS block for {rev_ip}")
                #
                dns_allowed_query.append(nwk['network']+"/"+nwk['subnet']) # used for e.g. named. allow query
                dns_zones.append(networkname)
                if rev_ip and rev_ip not in dns_zones:
                    dns_zones.append(rev_ip)
                    dns_rev_domain[rev_ip]=networkname
                if rev_ipv6 and rev_ipv6 not in dns_zones:
                    dns_zones.append(rev_ipv6)
                    dns_rev_domain[rev_ipv6]=networkname
                dns_zone_records[networkname]={}
                # we always add a zone record for controller even when we're actually in it. we can override.
                dns_zone_records[networkname]['controller']={}
                dns_zone_records[networkname]['controller']['key']='controller'
                dns_zone_records[networkname]['controller']['type']='A'
                dns_zone_records[networkname]['controller']['value']=controller_ip
                if rev_ip:
                    if rev_ip not in dns_zone_records.keys():
                        dns_zone_records[rev_ip]={}
                    dns_authoritative[rev_ip]='controller'
                if rev_ipv6:
                    if rev_ipv6 not in dns_zone_records.keys():
                        dns_zone_records[rev_ipv6]={}
                    dns_authoritative[rev_ipv6]='controller'
                dns_authoritative[networkname]='controller'

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
                     'network.name as networkname'],
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
                    dns_zone_records[networkname][host['host']]={}
                    dns_zone_records[networkname][host['host']]['key']=host['host'].rstrip('.')
                    if 'ipaddress_ipv6' in host and host['ipaddress_ipv6']:
                        ipv6_rev = ip_address(host['ipaddress_ipv6']).reverse_pointer
                        ipv6_list = ipv6_rev.split('.')
                        host_ptr = '.'.join(ipv6_list[0:16])
                        dns_zone_records[networkname][host['host']]['type']='AAAA'
                        dns_zone_records[networkname][host['host']]['value']=host['ipaddress_ipv6']
                        dns_zone_records[rev_ipv6][host['host']]={}
                        dns_zone_records[rev_ipv6][host['host']]['key']=host_ptr
                        dns_zone_records[rev_ipv6][host['host']]['type']='PTR'
                        dns_zone_records[rev_ipv6][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"
                    if host['ipaddress']:
                        sub_ip = host['ipaddress'].split('.')
                        host_ptr = sub_ip[3] + '.' + sub_ip[2]
                        dns_zone_records[networkname][host['host']]['type']='A'
                        dns_zone_records[networkname][host['host']]['value']=host['ipaddress']
                        dns_zone_records[rev_ip][host['host']]={}
                        dns_zone_records[rev_ip][host['host']]['key']=host_ptr
                        dns_zone_records[rev_ip][host['host']]['type']='PTR'
                        dns_zone_records[rev_ip][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"


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
                                                           AUTHORITATIVE_SERVER=f"controller.{networkname}",
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
            result_ip = False
            network_details = Database().get_record(None, 'network', f"WHERE id='{network_id}'")
            valid_ip = Helper().check_ip_range(
                ipaddress,
                f"{network_details[0]['network']}/{network_details[0]['subnet']}"
            )
            self.logger.info(f"Ipaddress {ipaddress} for {device} is [{valid_ip}]")
            if valid_ip is False:
                message = f"invalid IP address for {device}. Network {network_details[0]['name']}: "
                message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                return False, message

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


    def node_interface_config(self, nodeid=None, interface_name=None,
                              macaddress=None, options=None):
        """
        This method will collect node interfaces and return configuration.
        """
        result_if = False
        my_interface = {}

        where_interface = f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(None, 'nodeinterface', where_interface)

        if not check_interface: # ----> easy. both the interface as ipaddress do not exist
            my_interface['interface'] = interface_name
            my_interface['nodeid'] = nodeid
            if macaddress is not None:
                my_interface['macaddress'] = macaddress.lower()
            if options is not None:
                my_interface['options'] = options
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('nodeinterface', row)

        else:
            # we have to update the interface
            if macaddress is not None:
                my_interface['macaddress'] = macaddress.lower()
            if options is not None:
                my_interface['options'] = options
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


    def node_interface_ipaddress_config(self,nodeid,interface_name,ipaddress,network=None):
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
            my_ipaddress['ipaddress'] = ipaddress
            valid_ip = Helper().check_ip_range(
                ipaddress,
                f"{network_details[0]['network']}/{network_details[0]['subnet']}"
            )

        if not valid_ip:
            message = f"invalid IP address for {interface_name}. "
            message += f"Network {network_details[0]['name']}: "
            message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"
            self.logger.info(message)
            return False, message

        ipaddress_check = Database().get_record(None, 'ipaddress', f"WHERE ipaddress='{ipaddress}'")
        if ipaddress_check:
            ipaddress_check_own = Database().get_record_join(
                ['node.id as nodeid','nodeinterface.interface'],
                ['ipaddress.tablerefid=nodeinterface.id','nodeinterface.nodeid=node.id'],
                ['tableref="nodeinterface"',f"ipaddress.ipaddress='{ipaddress}'"]
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
        It's called from a group add/change. it handles all nodes in that group
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_on_group_nodes called")
        try:
            while next_id := Queue().next_task_in_queue('group_interface'):
                message = f"update_interface_on_group_nodes sees job in queue as next: {next_id}"
                self.logger.info(message)
                details=Queue().get_task_details(next_id)
                # request_id = details['request_id']
                action, group, interface, *_ = details['task'].split(':') + [None] + [None]

                if group == name:
                    # ADDING/UPDATING --------------------------------------------------------
                    if (action in ['add_interface_to_group_nodes', 'update_interface_for_group_nodes']) and interface:
                        network = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.networkid as networkid',
                                'network.network',
                                'network.subnet',
                                'network.name as networkname'
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
                                    'network.network',
                                    'network.subnet',
                                    'network.name as networkname'
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
                        if network:
                            dhcp_ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'])
                        ips = dhcp_ips.copy()
                        if network and 'ipaddress' in network[0]:
                            for ip in network:
                                ips.append(ip['ipaddress'])
                        nodes = Database().get_record_join(
                            ['node.id as nodeid'],
                            ['node.groupid=group.id'],
                            [f"`group`.name='{group}'"]
                        )
                        if nodes:
                            for node in nodes:
                                check, text = self.node_interface_config(node['nodeid'], interface)
                                message = f"Adding/Updating interface {interface} to node id "
                                message += f"{node['nodeid']} for group {group}. {text}"
                                self.logger.info(message)
                                if check and network:
                                    valid_ip, avail = None, None
                                    if action == 'update_interface_for_group_nodes':
                                        ip_details = Database().get_record_join(
                                            ['ipaddress.ipaddress'],
                                            ['ipaddress.tablerefid=nodeinterface.id'],
                                            [
                                                "ipaddress.tableref='nodeinterface'",
                                                f"nodeinterface.nodeid=\"{node['nodeid']}\"",
                                                f"nodeinterface.interface='{interface}'"
                                            ]
                                        )
                                        if ip_details:
                                            valid_ip = Helper().check_ip_range(
                                                ip_details[0]['ipaddress'],
                                                f"{network[0]['network']}/{network[0]['subnet']}"
                                            )
                                        if valid_ip and ip_details[0]['ipaddress'] not in dhcp_ips:
                                            avail = ip_details[0]['ipaddress']
                                            self.logger.info(f"---> reusing ipaddress {avail}")
                                    if not avail:
                                        ret = 0
                                        maximum = 5
                                        # we try to ping for X ips, if none of these are free,
                                        # something else is going on (read: rogue devices)....
                                        while(maximum > 0 and ret != 1):
                                            avail = Helper().get_available_ip(
                                                network[0]['network'],
                                                network[0]['subnet'],
                                                ips
                                            )
                                            ips.append(avail)
                                            result, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                            maximum -= 1

                                    if avail:
                                        ipaddress = avail
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
                    Queue().add_task_to_queue(
                        'dns:restart',
                        'housekeeper',
                        '__update_interface_on_group_nodes__'
                    )
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            self.logger.error(f"update_interface_on_group_nodes has problems: {exp}")


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
                action, network, *_ = details['task'].split(':') + [None] + [None]

                if (name and network==name) or network:
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if action == 'update_all_interface_ipaddress':
                        ips = self.get_dhcp_range_ips_from_network(network)
                        ipaddress_list = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.networkid as networkid',
                                'network.network',
                                'network.subnet',
                                'network.name as networkname',
                                'ipaddress.id as ipaddressid',
                                'ipaddress.tableref',
                                'ipaddress.tablerefid'
                            ],
                            ['ipaddress.networkid=network.id'],
                            [f"network.name='{network}'", "ipaddress.tableref!='controller'"]
                        )
                        if ipaddress_list:
                            for ipaddress in ipaddress_list:
                                valid_ip = Helper().check_ip_range(ipaddress['ipaddress'],
                                    f"{ipaddress['network']}/{ipaddress['subnet']}"
                                )
                                if valid_ip and ipaddress['ipaddress'] not in ips:
                                    ips.append(ipaddress['ipaddress'])
                                    self.logger.info(f"For network {network} no change for IP {ipaddress['ipaddress']}")
                                    continue
                                ret, avail = 0, None
                                maximum = 5
                                # we try to ping for X ips, if none of these are free,
                                # something else is going on (read: rogue devices)....
                                while(maximum > 0 and ret != 1):
                                    avail = Helper().get_available_ip(
                                        ipaddress['network'],
                                        ipaddress['subnet'],
                                        ips
                                    )
                                    ips.append(avail)
                                    _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                    maximum -= 1
                                message = f"For network {network} changing IP "
                                if avail:
                                    # row   = [{"column": "ipaddress", "value": f"{avail}"}]
                                    # where = [{"column": "id", "value": f"{ipaddress['ipaddressid']}"}]
                                    # message = Database().update('ipaddress', row, where)
                                    Database().delete_row(
                                        'ipaddress',
                                        [{"column": "ipaddress", "value": f"{avail}"}]
                                    )
                                    Database().delete_row(
                                        'ipaddress',
                                        [
                                            {"column": "tableref", "value": f"{ipaddress['tableref']}"},
                                            {"column": "tablerefid", "value": f"{ipaddress['tablerefid']}"}
                                        ]
                                    )
                                    row = [
                                        {"column": "ipaddress", "value": f"{avail}"},
                                        {"column": "networkid", "value": f"{ipaddress['networkid']}"},
                                        {"column": "tableref", "value": f"{ipaddress['tableref']}"},
                                        {"column": "tablerefid", "value": f"{ipaddress['tablerefid']}"}
                                    ]
                                    result = Database().insert('ipaddress', row)

                                    message += f"{ipaddress['ipaddress']} to {avail}. {result}"
                                    self.logger.info(message)
                                else:
                                    message += f"{ipaddress['ipaddress']} not possible. "
                                    message += "no free IP addresses available."
                                    self.logger.error(message)
                    Queue().remove_task_from_queue(next_id)
                    Queue().add_task_to_queue(
                        'dns:restart',
                        'housekeeper',
                        '__update_interface_ipaddress_on_network_change__'
                    )
                    Queue().add_task_to_queue(
                        'dhcp:restart',
                        'housekeeper',
                        '__update_interface_ipaddress_on_network_change__'
                    )
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            self.logger.error(f"update_interface_ipaddress_on_network_change has problems: {exp}")


    def update_dhcp_range_on_network_change(self, name=None, request_id=None): # name=network
        """
        This method will update dhcp range, when network will changes.
        """
        self.logger.info(f'request_id: {request_id}')
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            if network[0]['dhcp_range_begin'] and network[0]['dhcp_range_end']:
                subnet = network[0]['network']+'/'+network[0]['subnet']
                dhcp_begin_ok = Helper().check_ip_range(network[0]['dhcp_range_begin'], subnet)
                dhcp_end_ok = Helper().check_ip_range(network[0]['dhcp_range_end'], subnet)
                if dhcp_begin_ok and dhcp_end_ok:
                    message = f"{network[0]['network']}/{network[0]['subnet']} :: dhcp "
                    message += f"{network[0]['dhcp_range_begin']}-{network[0]['dhcp_range_end']} "
                    message += "fits with in network range. no change"
                    self.logger.info(message)
                    return True
                dhcp_size = Helper().get_ip_range_size(
                    network[0]['dhcp_range_begin'],
                    network[0]['dhcp_range_end']
                )
                nwk_size = Helper().get_network_size(network[0]['network'], network[0]['subnet'])
                if ((100 * dhcp_size) / nwk_size) > 50: # == 50%
                    dhcp_size = int(nwk_size / 10)
                    # we reduce this to 10%
                    # how many,  offset start
                dhcp_begin, dhcp_end = Helper().get_ip_range_first_last_ip(
                    network[0]['network'],
                    network[0]['subnet'],
                    dhcp_size, (int(nwk_size / 2) - 4)
                )
                message = f"{network[0]['network']}/{network[0]['subnet']}"
                message += f" :: new dhcp range {dhcp_begin}-{dhcp_end}"
                self.logger.info(message)
                if dhcp_begin and dhcp_end:
                    row = [
                        {"column": "dhcp_range_begin", "value": f"{dhcp_begin}"},
                        {"column": "dhcp_range_end", "value": f"{dhcp_end}"}
                    ]
                    where = [{"column": "name", "value": f"{name}"}]
                    Database().update('network', row, where)
                    Queue().add_task_to_queue(
                        'dhcp:restart',
                        'housekeeper',
                        '__update_dhcp_range_on_network_change__'
                    )


    def get_dhcp_range_ips_from_network(self, network=None):
        """
        This method will return dhcp range for network.
        """
        ips = []
        network_details = Database().get_record(None, 'network', f' WHERE `name` = "{network}"')
        if network_details and network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
            ips = Helper().get_ip_range_ips(
                network_details[0]['dhcp_range_begin'],
                network_details[0]['dhcp_range_end']
            )
        return ips


    def get_all_occupied_ips_from_network(self, network=None):
        """
        This method will return all occupied IP from a network.
        """
        ips = []
        network_details = Database().get_record(None, 'network', f' WHERE `name` = "{network}"')
        if network_details and network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
            ips = Helper().get_ip_range_ips(
                network_details[0]['dhcp_range_begin'],
                network_details[0]['dhcp_range_end']
            )
        network_details = Database().get_record_join(
            ['ipaddress.ipaddress'],
            ['network.id=ipaddress.networkid'],
            [f"network.name='{network}'"]
        )
        if network_details:
            for each in network_details:
                ips.append(each['ipaddress'])
        return ips
