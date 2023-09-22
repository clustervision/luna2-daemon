#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is a Config Class, which provide the configuration
to DHN and DHCP methods.

"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import subprocess
import shutil
from time import time, sleep
import re
from ipaddress import ip_address
from textwrap import dedent
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue
from common.constant import CONSTANT


class Config(object):
    """
    All kind of configuration methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()


    def dhcp_overwrite(self):
        """
        This method collect dhcp enabled networks, node interfaces belongs to the networks and
        other devices which have the mac address. write and validates the /var/tmp/luna/dhcpd.conf
        """
        validate = True
        ntp_server, dhcp_subnet_block = '', ''
        node_block, device_block = [] , []
        cluster = Database().get_record(None, 'cluster', None)
        if cluster and 'ntp_server' in cluster[0] and cluster[0]['ntp_server']:
            ntp_server = cluster[0]['ntp_server']
        dhcp_file = f"{CONSTANT['TEMPLATES']['TEMP_DIR']}/dhcpd.conf"
        serverport = 7050
        if CONSTANT['API']['PROTOCOL'] == 'https' and 'WEBSERVER' in CONSTANT and 'PORT' in CONSTANT['WEBSERVER']:
            # we rely on nginx serving non https stuff for e.g. /boot. 
            # ipxe does support https but has issues dealing with self signed certificates
            serverport = CONSTANT['WEBSERVER']['PORT']
        domain = None
        handled=[]
        # do we have shared networks?
        shared_dhcp_header=[]
        dhcp_decl_header,dhcp_subnet_block = "",""
        shared = Database().get_record(None, 'network', ' WHERE `dhcp` = 1 AND (shared != "" OR shared != "None")')
        if shared:
            dhcp_decl_header = "\nshared-network shared {"
            for sharednw in shared:
                shared_dhcp_header.append(self.shared_header(sharednw['name']))
                if sharednw['shared'] not in handled:
                    mainshared = Database().get_record(None, 'network', ' WHERE name = "'+sharednw['shared']+'"')
                    if mainshared:
                        handled.append(sharednw['shared'])
                        dhcp_subnet_block += self.dhcp_decl_config(mainshared[0])
                dhcp_subnet_block += self.dhcp_decl_config(sharednw)
            dhcp_decl_header = "}\n"
                    
        networks = Database().get_record(None, 'network', ' WHERE `dhcp` = 1')
        
        if networks:
            for nwk in networks:
                if nwk['name'] not in handled:
                    dhcp_subnet_block += self.dhcp_decl_config(nwk)
                    handled.append(nwk['name'])
                network_id = nwk['id']
                network_name = nwk['name']
                network_ip = nwk['network']
                node_interface = Database().get_record_join(
                    ['node.name as nodename', 'ipaddress.ipaddress', 'nodeinterface.macaddress'],
                    ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id'],
                    ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
                )
                if node_interface:
                    for interface in node_interface:
                        if interface['macaddress']:
                            node_block.append(self.dhcp_node(
                                interface['nodename'],
                                interface['macaddress'],
                                interface['ipaddress']
                            ))
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
                                device_block.append(
                                    self.dhcp_node(device['name'], device['macaddress'], device['ipaddress'])
                                )
                    else:
                        self.logger.debug(f'{item} not available for {network_name} {network_ip}')

        config = self.dhcp_config(domain,ntp_server)
        config = f'{config}{shared_dhcp_header}{dhcp_subnet_block}'
        for node in node_block:
            config = f'{config}{node}'
        for dev in device_block:
            config = f'{config}{dev}'
        config += "\n"

        try:
            with open(dhcp_file, 'w', encoding='utf-8') as dhcp:
                dhcp.write(config)
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
                self.logger.info(f'DHCP File created : {dhcp_file}')
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    def dhcp_decl_config (nwk=[]):
        """ 
        dhcp subnetblock with config
        glue between the various other subnet blocks: prepare for dhcp_subnet function
        """
        network_id = nwk['id']
        network_name = nwk['name']
        network_ip = nwk['network']
        netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
        controller = Database().get_record_join(
            ['ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"', f'ipaddress.networkid="{network_id}"']
        )
        self.logger.info(f"Building DHCP block for {network_name}")
        if controller:
            domain = nwk['name']
            subnet_block = self.dhcp_subnet(
                nwk['network'], netmask, serverport, controller[0]['ipaddress'], nwk['gateway'],
                nwk['dhcp_range_begin'], nwk['dhcp_range_end']
            )
        else:
            subnet_block = self.dhcp_subnet(
                nwk['network'], netmask, None, None, nwk['gateway'],
                nwk['dhcp_range_begin'], nwk['dhcp_range_end']
            )
        dhcp_subnet_block = f'{dhcp_subnet_block}{subnet_block}'

        if shared:
            dhcp_subnet_block += "}\n"
        return dhcp_subnet_block


    def dhcp_config(self, domain=None, ntp_server=None):
        """
        This method will prepare DHCP configuration.
        """
        if ntp_server:
            ntp_server = f'option time-servers {ntp_server};\n'
        else:
            ntp_server = ''

        if domain:
            option_domain = f'option domain-name "{domain}";'
        else:
            option_domain = f'option domain-name "cluster";'

        omapi_key = ''
        if CONSTANT['DHCP']['OMAPIKEY']:
            omapi_key = dedent(f"""
                omapi-port 7911;
                omapi-key omapi_key;

                key omapi_key {{
                    algorithm hmac-md5;
                    secret {CONSTANT['DHCP']['OMAPIKEY']};
                }}
            """)

        config = dedent(f"""
            #
            # DHCP Server Configuration file.
            # created by Luna
            #
            """)

        config += option_domain

        config += dedent(f"""
            option luna-id code 129 = text;
            option client-architecture code 93 = unsigned integer 16;
            {ntp_server}
            """)
            
        config += omapi_key

        config += dedent(f"""
            # how to get luna_ipxe.efi and luna_undionly.kpxe :
            # git clone git://git.ipxe.org/ipxe.git
            # cd ipxe/src
            # make bin/undionly.kpxe
            # cp bin/undionly.kpxe /tftpboot/luna_undionly.kpxe
            # make bin-x86_64-efi/ipxe.efi
            # cp bin-x86_64-efi/ipxe.efi /tftpboot/luna_ipxe.efi
            #
            """)
        return config


    def shared_header(self, network=None, identifier=None):
        identifier = identifier or "udhcp" 
        header_block = dedent(f"""
            class "{network}" {{
                match if substring (option vendor-class-identifier, 0, 5) = "{identifier}";
            }}""")
        header_block += "\n"
        return header_block


    def dhcp_subnet(self, network=None, netmask=None, serverport=None, nextserver=None, gateway=None,
                    dhcp_range_start=None, dhcp_range_end=None):
        """
        This method prepare the network block for all DHCP enabled networks
        """
        subnet_block = dedent(f"""
            subnet {network} netmask {netmask} {{
                max-lease-time 28800;
                if exists user-class and option user-class = "iPXE" {{
                    filename "http://{nextserver}:{serverport}/boot";
                }} else {{
                    if option client-architecture = 00:07 {{
                        filename "luna_ipxe.efi";
                    }} elsif option client-architecture = 00:0e {{
                    # OpenPower do not need binary to execure.
                    # Petitboot will request for config
                    }} else {{
                        filename "luna_undionly.kpxe";
                    }}
                }}""")
        if nextserver:
            subnet_block += f"""\n    next-server {nextserver};"""
        subnet_block += f"""\n    range {dhcp_range_start} {dhcp_range_end};"""
        if gateway:
            subnet_block += f"""\n    option routers {gateway};"""
        subnet_block += """\n    option luna-id "lunaclient";\n}\n"""
        return subnet_block


    def dhcp_node(self, node=None, macaddress=None, ipaddr=None):
        """
        This method will generate node and other devices configuration for the DHCP
        """
        if macaddress:
            if re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", macaddress.lower()):
                node_block = dedent(f"""
                    host {node}  {{
                        hardware ethernet {macaddress};
                        fixed-address {ipaddr};
                    }}""")
                return node_block
        return ""  # has to be ""


    def dns_configure(self):
        """
        This method will write /etc/named.conf and zone files for every network
        """
        validate = True
        files, nameserver_ip, forwarder, network = [], [], [], []
        zone_config, rev_ip = '', ''
        cluster = Database().get_record(None, 'cluster', None)
        if cluster and 'nameserver_ip' in cluster[0]:
            nameserver_ip.append(cluster[0]['nameserver_ip'])
        controller = Database().get_record_join(
            ['ipaddress.ipaddress'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"', 'controller.hostname="controller"']
        )
        controller_ip = controller[0]['ipaddress']
        if 'forwardserver_ip' in cluster[0] and cluster[0]['forwardserver_ip']:
            forwarder = cluster[0]['forwardserver_ip'].split(',')
        networks = Database().get_record(None, 'network', None)
        for nwk in networks:
            network_id = nwk['id']
            if nwk['nameserver_ip']: # Technically mean, authoritative server is outside cluster
                nameserver_ip.append(nwk['nameserver_ip'])
            if nwk['network'] and nwk['name']:
                network.append(nwk['network']+"/"+nwk['subnet']) # used for e.g. named. allow query
                networkname = nwk['name']
                rev_ip = ip_address(nwk['network']).reverse_pointer
                rev_ip = rev_ip.split('.')
                rev_ip = rev_ip[2:]
                rev_ip = '.'.join(rev_ip)
                zone_config = f'{zone_config}{self.dns_zone_config(networkname, rev_ip)}'
            # TWAN
            node_interface = Database().get_record_join(
                ['node.name as nodename', 'ipaddress.ipaddress', 'network.name as networkname'],
                ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id', 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
            )
            nodelist, ptr_node_list= [], []
            if node_interface:
                for interface in node_interface:
                    # nodeip = interface['ipaddress']
                    nodelist.append(f"{interface['nodename']}                 IN A {interface['ipaddress']}")
                    sub_ip = interface['ipaddress'].split('.')  # NOT IPv6 COMPLIANT!! needs overhaul. PENDING
                    node_ptr = sub_ip[2] + '.' + sub_ip[3]
                    ptr_node_list.append(f"{node_ptr}                    IN PTR {interface['nodename']}.{interface['networkname']}.")

            for item in ['otherdevices','switch']:
                devices = Database().get_record_join(
                    [f'{item}.name as devname', 'ipaddress.ipaddress', 'network.name as networkname'],
                    [f'ipaddress.tablerefid={item}.id', 'network.id=ipaddress.networkid'],
                    [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                )
                if devices:
                    for device in devices:
                        # devip = device['ipaddress']
                        nodelist.append(f"{device['devname']}                 IN A {device['ipaddress']}")
                        sub_ip = device['ipaddress'].split('.')  # NOT IPv6 COMPLIANT!! needs overhaul. PENDING
                        node_ptr = sub_ip[2] + '.' + sub_ip[3]
                        ptr_node_list.append(f"{node_ptr}                    IN PTR {device['devname']}.{device['networkname']}.")

            zone_name_config = self.dns_zone_name(networkname, controller_ip, nodelist)
            zone_ptr_config = self.dns_zone_ptr(networkname, ptr_node_list)
            name_file = {
                'source': f'/var/tmp/luna2/{networkname}.luna.zone',
                'destination': f'/var/named/{networkname}.luna.zone'
            }
            ptr_file = {
                'source': f'/var/tmp/luna2/{rev_ip}.luna.zone',
                'destination': f'/var/named/{rev_ip}.luna.zone'
            }
            files.append(name_file)
            files.append(ptr_file)
            try:
                with open(name_file['source'], 'w', encoding='utf-8') as filename:
                    filename.write(zone_name_config)
                with open(ptr_file['source'], 'w', encoding='utf-8') as fileptr:
                    fileptr.write(zone_ptr_config)
                try:
                    zone_cmd = ['named-checkzone', f'luna.{networkname}', name_file['source']]
                    validate_zone_name = subprocess.run(zone_cmd, check = True)
                    if validate_zone_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {name_file["source"]} containing errors.')
                except Exception as exp:
                    self.logger.error(f'DNS zone file: {name_file["source"]} containing errors.')
                try:
                    ptr_cmd = ['named-checkzone', f'luna.{networkname}', ptr_file['source']]
                    validate_ptr_name = subprocess.run(ptr_cmd, check = True)
                    if validate_ptr_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {ptr_file["source"]} containing errors.')
                except:
                    self.logger.error(f'DNS zone file: {ptr_file["source"]} containing errors.')
            except Exception as exp:
                self.logger.error(f"Uh oh... {exp}")

        config = self.dns_config(forwarder,network)
        dns_file = {'source': '/var/tmp/luna2/named.conf', 'destination': '/etc/named.conf'}
        try:
            files.append(dns_file)
            with open(dns_file["source"], 'w', encoding='utf-8') as dns:
                dns.write(config)
            dns_zone_file = {
                'source': '/var/tmp/luna2/named.luna.zones',
#                'destination': '/trinity/local/etc/named.luna.zones'
                'destination': '/etc/named.luna.zones'
            }
            files.append(dns_zone_file)
            with open(dns_zone_file["source"], 'w', encoding='utf-8') as dns_zone:
                dns_zone.write(zone_config)
#            self.logger.info(f'DNS files : {files}')
            if validate:
                if not os.path.exists('/var/named'):
                    os.makedirs('/var/named')
                for dns_files in files:
                    shutil.copyfile(dns_files["source"], dns_files["destination"])
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    def dns_config(self, forwarder=None, network=None):
        """
        This method prepare the dns configuration
        with forwarder IP's
        """
        caching=""
        # -------------
        if forwarder:
            forwarders = f"""
        // BEGIN forwarders
        forwarders {{
            """
            for ip in forwarder:
                forwarders += f"\n\t\t{ip};"
            forwarders += f"""
        }};
        // END forwarders
            """
        # -------------
        else:
            forwarders=''
            caching = f"""
        zone "." IN {{
                type hint;
                file "named.ca";
        }};
            """
        # -------------
        managed_keys=''
        if os.path.exists("/trinity/local/var/lib/named/dynamic"):
            managed_keys="managed-keys-directory \"/trinity/local/var/lib/named/dynamic\";"
        # -------------
        allow="any;"
        if network:
            allow="127.0.0.0/8; "
            for ip in network:
                allow+=ip+"; "

        config = f"""
//
// named.conf
//
// Provided by Red Hat bind package to configure the ISC BIND named(8) DNS
// server as a caching only nameserver (as a localhost DNS resolver only).
//
// See /usr/share/doc/bind*/sample/ for example named configuration files.
//

options {{
        listen-on port 53 {{ any; }};
        listen-on-v6 port 53 {{ any; }};
        /* BELOW NEEDS REVISION IN utils/config.py !!! */
        /*directory       "/trinity/local/var/lib/named";
        dump-file       "/trinity/local/var/lib/named/data/cache_dump.db";
        statistics-file "/trinity/local/var/lib/named/data/named_stats.txt";
        memstatistics-file "/trinity/local/var/lib/named/data/named_mem_stats.txt";
        secroots-file   "/trinity/local/var/lib/named/data/named.secroots";
        recursing-file  "/trinity/local/var/lib/named/data/named.recursing";*/
        directory       "/var/named";
        allow-query     {{ {allow} }};

        /*
         - If you are building an AUTHORITATIVE DNS server, do NOT enable recursion.
         - If you are building a RECURSIVE (caching) DNS server, you need to enable
           recursion.
         - If your recursive DNS server has a public IP address, you MUST enable access
           control to limit queries to your legitimate users. Failing to do so will
           cause your server to become part of large scale DNS amplification
           attacks. Implementing BCP38 within your network would greatly
           reduce such attack surface
        */
        recursion yes;
        {forwarders}

        dnssec-enable no;
        dnssec-validation no;

        {managed_keys}

        pid-file "/run/named/named.pid";
        session-keyfile "/run/named/session.key";

        /* https://fedoraproject.org/wiki/Changes/CryptoPolicy */
        include "/etc/crypto-policies/back-ends/bind.config";
}};

logging {{
        channel default_debug {{
                file "data/named.run";
                severity dynamic;
        }};
}};

{caching}

include "/etc/named.rfc1912.zones";
include "/etc/named.root.key";

include "/etc/named.luna.zones";
/*include "/trinity/local/etc/named.luna.zones";*/

"""
        return config


    def dns_zone_config(self, networkname=None, reverse_ip=None):
        """
        This method will generate the configuration for zone file
        """
        zone_config = f"""
zone "{networkname}" IN {{
    type master;
    file "/var/named/{networkname}.luna.zone";
    allow-update {{ none; }};
    allow-transfer {{none; }};
}};
zone "{reverse_ip}" IN {{
    type master;
    file "/var/named/{reverse_ip}.luna.zone";
    allow-update {{ none; }};
    allow-transfer {{none; }};
}};

"""
        return zone_config


    def dns_zone_name(self, networkname=None, controller_ip=None, nodelist=None):
        """
        This method will generate the DNS network
        name zone file.
        """
        unix_time = int(time())
        if nodelist:
            nodelist = '\n'.join(nodelist)
        else:
            nodelist = ''
        zone_name_config = f"""
$TTL 604800
@ IN SOA                controller.{networkname}. root.controller.{networkname}. ( ; domain email
                        {unix_time}        ; serial number
                        86400       ; refresh
                        14400       ; retry
                        3628800       ; expire
                        604800 )     ; min TTL

                        IN NS controller.{networkname}.
"""
        if controller_ip is not None:
            zone_name_config += f"""
controller              IN A {controller_ip}
"""
        zone_name_config += f"""
{nodelist}

"""
        return zone_name_config


    def dns_zone_ptr(self, networkname=None, nodelist=None):
        """
        This method will generate the DNS network name zone file.
        """
        unix_time = int(time())
        if nodelist:
            nodelist = '\n'.join(nodelist)
        else:
            nodelist = ''
        zone_name_config = f"""
$TTL 604800
@ IN SOA                controller.{networkname}. root.controller.{networkname}. ( ; domain email
                        {unix_time}        ; serial number
                        86400       ; refresh
                        14400       ; retry
                        3628800       ; expire
                        604800 )     ; min TTL

                        IN NS controller.{networkname}.


{nodelist}

"""
        return zone_name_config


    def device_ipaddress_config(self, device_id=None, device=None, ipaddress=None, network=None):
        """
        This method will collect device ipaddress and return configuration.
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


    def node_interface_config(self, nodeid=None, interface_name=None, macaddress=None, options=None):
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
                my_interface['macaddress'] = macaddress
            if options is not None:
                my_interface['options'] = options
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('nodeinterface', row)

        else:
            # we have to update the interface
            if macaddress is not None:
                my_interface['macaddress'] = macaddress
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
            message = "not enough information provided. network name incorrect or \
                need network name if there is no existing ipaddress"
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
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_on_group_nodes called")
        try:
            while next_id := Queue().next_task_in_queue('group_interface'):
                message = f"update_interface_on_group_nodes sees job in queue as next: {next_id}"
                self.logger.info(message)
                details=Queue().get_task_details(next_id)
                # request_id = details['request_id']
                action, group, interface, *_ = (details['task'].split(':') + [None] + [None] )

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
                        ips = []
                        if network:
                            ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'])
                        dhcp_ips = ips
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
                                            _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                            maximum -= 1

                                    if avail:
                                        ipaddress = avail
                                        result, response = self.node_interface_ipaddress_config(
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
                action, network, *_ = (details['task'].split(':') + [None] + [None])

                if (name and network==name) or network:
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
