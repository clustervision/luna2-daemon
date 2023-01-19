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
import time
import re
from ipaddress import ip_address
from utils.log import Log
from utils.database import Database

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
        This method collect dhcp enabled networks,
        node interfaces belongs to the networks and
        other devices which have the mac address.
        write and validates the /var/tmp/luna/dhcpd.conf
        """
        validate = True
        ntpserver, dhcp_subnet_block = '', ''
        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            ntpserver = cluster[0]['ntp_server']
        networks = Database().get_record(None, 'network', ' WHERE `dhcp` = 1;')
        dhcpfile = f"{CONSTANT['TEMPLATES']['TEMP_DIR']}/dhcpd.conf"
        if networks:
            for nwk in networks:
                nwkid = nwk['id']
                nwkname = nwk['name']
                nwknetwork = nwk['network']
                subnet_block = self.dhcp_subnet(nwk['network'], nwk['subnet'], nwk['gateway'], nwk['dhcp_range_begin'], nwk['dhcp_range_end'])
                dhcp_subnet_block = f'{dhcp_subnet_block}{subnet_block}'

                node_interface = Database().get_record(None, 'nodeinterface', f' WHERE networkid = "{nwkid}" and macaddress IS NOT NULL;')
                node_block, device_block = [] , []
                if node_interface:
                    for interface in node_interface:
                        nodename = Database().getname_byid('node', interface['nodeid'])
                        node_block.append(self.dhcp_node(nodename, interface['macaddress'], interface['ipaddress']))
                else:
                    self.logger.info(f'No Nodes available for this network {nwkname}  {nwknetwork}')
                devices = Database().get_record(None, 'otherdevices', f' WHERE network = "{nwkid}" and macaddr IS NOT NULL;')
                if devices:
                    for device in devices:
                        device_block.append(self.dhcp_node(device['name'], device['macaddr'], device['ipaddress']))
                else:
                    self.logger.info(f'Device not available for {nwkname} {nwknetwork}')

        config = self.dhcp_config(ntpserver)
        config = f'{config}{dhcp_subnet_block}'
        for node in node_block:
            config = f'{config}{node}'
        for dev in device_block:
            config = f'{config}{dev}'

        with open(dhcpfile, 'w', encoding='utf-8') as dhcp:
            dhcp.write(config)
        validate_config = subprocess.run(["dhcpd", "-t", "-cf", dhcpfile], check=True)
        if validate_config.returncode:
            validate = False
            self.logger.error(f'DHCP file : {dhcpfile} containing errors.')
        else:
            shutil.copyfile(dhcpfile, '/etc/dhcp/dhcpd.conf')
            self.logger.info(f'DHCP File created : {dhcpfile}')
        return validate


    def dhcp_config(self, ntpserver=None):
        """
        This method will prepare DHCP configuration."""
        if ntpserver:
            ntpserver = f'option domain-name-servers {ntpserver};'
            secretkey = CONSTANT['DHCP']['OMAPIKEY']
        config = f"""
#
# DHCP Server Configuration file.
# created by Luna
#
option domain-name "lunacluster";
option luna-id code 129 = text;
option client-architecture code 93 = unsigned integer 16;
{ntpserver}

omapi-port 7911;
omapi-key omapi_key;

key omapi_key {{
    algorithm hmac-md5;
    secret {secretkey};
}}

# how to get luna_ipxe.efi and luna_undionly.kpxe :
# git clone git://git.ipxe.org/ipxe.git
# cd ipxe/src
# make bin/undionly.kpxe
# cp bin/undionly.kpxe /tftpboot/luna_undionly.kpxe
# make bin-x86_64-efi/ipxe.efi
# cp bin-x86_64-efi/ipxe.efi /tftpboot/luna_ipxe.efi
#
"""
        return config


    def dhcp_subnet(self, subnet=None, netmask=None, nextserver=None,
                    dhcp_range_start=None, dhcp_range_end=None):
        """
        This method prepare the netwok block
        for all DHCP enabled networks
        """
        subnet_block = f"""
subnet {subnet} netmask {netmask} {{
    max-lease-time 28800;
    if exists user-class and option user-class = "iPXE" {{
        filename "http://{{{{ boot_server }}}}:7050/luna?step=boot";
    }} else {{
        if option client-architecture = 00:07 {{
            filename "luna_ipxe.efi";
        }} elsif option client-architecture = 00:0e {{
        # OpenPower do not need binary to execure.
        # Petitboot will request for config
        }} else {{
            filename "luna_undionly.kpxe";
        }}
    }}
    next-server {nextserver};
    range {dhcp_range_start} {dhcp_range_end};

    option routers 10.141.255.254;
    option luna-id "lunaclient";
}}
"""
        return subnet_block


    def dhcp_node(self, node=None, macaddress=None, ipaddr=None):
        """
        This method will generate node and
        otherdecices configuration for the DHCP
        """
        node_block = f"""
host {node}  {{
    hardware ethernet {macaddress};
    fixed-address {ipaddr};
}}
"""
        return node_block
    

    def dns_configure(self):
        """
        This method will write /etc/named.conf
        and zone files for every network
        """
        validate = True
        files, ns_ip, nodelist, ptrnodelist= [], [], [], []
        zone_config, rev_ip = '', ''
        cluster = Database().get_record(None, 'cluster', None)
        ns_ip = cluster[0]['ns_ip']
        controllerip = cluster[0]['ntp_server']
        if ns_ip:
            forwarder = ns_ip
        networks = Database().get_record(None, 'network', None)
        for nwk in networks:
            nwkid = nwk['id']
            if nwk['ns_ip'] and ns_ip is None:
                ns_ip.append(nwk['ns_ip'])
            if nwk['network'] and nwk['name']:
                networkname = nwk['name']
                rev_ip = ip_address(nwk['network']).reverse_pointer
                rev_ip = rev_ip.split('.')
                rev_ip = rev_ip[2:]
                rev_ip = '.'.join(rev_ip)
                zone_config = f'{zone_config}{self.dns_zone_config(networkname, rev_ip)}'
            node_interface = Database().get_record(None, 'nodeinterface', f' WHERE networkid = "{nwkid}";')
            if node_interface:
                for interface in node_interface:
                    nodeip = interface['ipaddress']
                    nodename = Database().getname_byid('node', interface['nodeid'])
                    nodelist.append(f'{nodename}                 IN A {nodeip}')
                    nodeptr = int(re.sub('\D', '', nodename))
                    nodeptr = f'{nodeptr}.0'
                    ptrnodelist.append(f'{nodeptr}                    IN PTR {nodename}.{networkname}.')

            zone_name_config = self.dns_zone_name(networkname, controllerip, nodelist)
            zone_ptr_config = self.dns_zone_ptr(networkname, ptrnodelist)
            namefile = {'source': f'/var/tmp/luna2/{networkname}.luna.zone', 'destination': f'/var/named/{networkname}.luna.zone'}
            ptrfile = {'source': f'/var/tmp/luna2/{rev_ip}.luna.zone', 'destination': f'/var/named/{rev_ip}.luna.zone'}
            files.append(namefile)
            files.append(ptrfile)
            with open(namefile['source'], 'w', encoding='utf-8') as filename:
                filename.write(zone_name_config)
            with open(ptrfile['source'], 'w', encoding='utf-8') as fileptr:
                fileptr.write(zone_ptr_config)
            validate_zone_name = subprocess.run(['named-checkzone', f'luna.{networkname}', namefile['source']], check = True)
            if validate_zone_name.returncode:
                validate = False
                self.logger.error(f'DNS zone file: {namefile["source"]} containing errors.')
            validate_ptr_name = subprocess.run(['named-checkzone', f'luna.{networkname}', ptrfile['source']], check = True)
            if validate_ptr_name.returncode:
                validate = False
                self.logger.error(f'DNS zone file: {ptrfile["source"]} containing errors.')
            if ns_ip is None:
                forwarder = ';'.join(ns_ip)

        config = self.dns_config(forwarder)
        dnsfile = {'source': '/var/tmp/luna2/named.conf', 'destination': '/etc/named.conf'}
        files.append(dnsfile)
        with open(dnsfile["source"], 'w', encoding='utf-8') as dns:
            dns.write(config)
        dnszonefile = {'source': '/var/tmp/luna2/named.luna.zones', 'destination': '/trinity/local/etc/named.luna.zones'}
        files.append(dnszonefile)
        with open(dnszonefile["source"], 'w', encoding='utf-8') as dnszone:
            dnszone.write(zone_config)
        self.logger.info(f'DNS files : {files}')
        if validate:
            if not os.path.exists('/var/named'):
                os.makedirs('/var/named')
            for dnsfiles in files:
                shutil.copyfile(dnsfiles["source"], dnsfiles["destination"])
        return validate


    def dns_config(self, forwarder=None):
        """
        This method prepare the dns configuration
        with forwarder IP's
        """
        if forwarder:
            forwarder = f"""
// BEGIN forwarders
    forwarders {{
              {forwarder};
    }};
// END forwarders
            """

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
        directory       "/trinity/local/var/lib/named";
        dump-file       "/trinity/local/var/lib/named/data/cache_dump.db";
        statistics-file "/trinity/local/var/lib/named/data/named_stats.txt";
        memstatistics-file "/trinity/local/var/lib/named/data/named_mem_stats.txt";
        secroots-file   "/trinity/local/var/lib/named/data/named.secroots";
        recursing-file  "/trinity/local/var/lib/named/data/named.recursing";
        allow-query     {{ any; }};

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
{forwarder}

dnssec-enable no;
dnssec-validation no;

        managed-keys-directory "/trinity/local/var/lib/named/dynamic";

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

zone "." IN {{
        type hint;
        file "named.ca";
}};

include "/etc/named.rfc1912.zones";
include "/etc/named.root.key";

include "/etc/named.luna.zones";

"""
        return config


    def dns_zone_config(self, networkname=None, reverseip=None):
        """
        This method will generate the configuration
        for zone file
        """
        zone_config = f"""
zone "{networkname}" IN {{
    type master;
    file "/var/named/{networkname}.luna.zone";
    allow-update {{ none; }};
    allow-transfer {{none; }};
}};
zone "{reverseip}" IN {{
    type master;
    file "/var/named/{reverseip}.luna.zone";
    allow-update {{ none; }};
    allow-transfer {{none; }};
}};

"""
        return zone_config


    def dns_zone_name(self, networkname=None, controllerip=None, nodelist=None):
        """
        This method will generate the DNS network
        name zone file.
        """
        unixtime = int(time.time())
        if nodelist:
            nodelist = '\n'.join(nodelist)
        zone_name_config = f"""
$TTL 604800
@ IN SOA                controller.{networkname}. root.controller.{networkname}. ( ; domain email
                        {unixtime}        ; serial number
                        86400       ; refresh
                        14400       ; retry
                        3628800       ; expire
                        604800 )     ; min TTL

                        IN NS controller.{networkname}.
                        IN A {controllerip}

{nodelist}

"""
        return zone_name_config
    

    def dns_zone_ptr(self, networkname=None, nodelist=None):
        """
        This method will generate the DNS network
        name zone file.
        """
        unixtime = int(time.time())
        if nodelist:
            nodelist = '\n'.join(nodelist)
        zone_name_config = f"""
$TTL 604800
@ IN SOA                controller.{networkname}. root.controller.{networkname}. ( ; domain email
                        {unixtime}        ; serial number
                        86400       ; refresh
                        14400       ; retry
                        3628800       ; expire
                        604800 )     ; min TTL

                        IN NS controller.{networkname}.


{nodelist}

"""
        return zone_name_config


