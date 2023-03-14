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
from utils.helper import Helper

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
        node_block, device_block = [] , []
        cluster = Database().get_record(None, 'cluster', None)
        if cluster and ('ntp_server' in cluster[0]):
            ntpserver = cluster[0]['ntp_server']
        controller = Database().get_record_join(['ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'], ['tableref="controller"','controller.hostname="controller"'])
        networks = Database().get_record(None, 'network', ' WHERE `dhcp` = 1')
        dhcpfile = f"{CONSTANT['TEMPLATES']['TEMP_DIR']}/dhcpd.conf"
        if networks:
            for nwk in networks:
                nwkid = nwk['id']
                nwkname = nwk['name']
                nwknetwork = nwk['network']
                netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
                subnet_block = self.dhcp_subnet(
                    nwk['network'], netmask, controller[0]['ipaddress'], nwk['gateway'],
                    nwk['dhcp_range_begin'], nwk['dhcp_range_end']
                )
                dhcp_subnet_block = f'{dhcp_subnet_block}{subnet_block}'

                node_interface = Database().get_record_join(['node.name as nodename','ipaddress.ipaddress','nodeinterface.macaddress'], ['ipaddress.tablerefid=nodeinterface.id','nodeinterface.nodeid=node.id'], ['tableref="nodeinterface"',f'ipaddress.networkid="{nwkid}"'])
                if node_interface:
                    for interface in node_interface:
                        if interface['macaddress']: 
                            node_block.append(
                                self.dhcp_node(interface['nodename'], interface['macaddress'],interface['ipaddress'])
                            )
                else:
                    self.logger.info(f'No Nodes available for this network {nwkname}  {nwknetwork}')
                for item in ['otherdevices','switch']:
                    devices = Database().get_record_join([f'{item}.name','ipaddress.ipaddress',f'{item}.macaddress'], [f'ipaddress.tablerefid={item}.id'], [f'tableref="{item}"',f'ipaddress.networkid="{nwkid}"'])
                    if devices:
                        for device in devices:
                            if device['macaddress']: 
                                device_block.append(
                                    self.dhcp_node(device['name'], device['macaddress'], device['ipaddress'])
                                )
                else:
                    self.logger.info(f'Device not available for {nwkname} {nwknetwork}')

        config = self.dhcp_config(ntpserver)
        config = f'{config}{dhcp_subnet_block}'
        for node in node_block:
            config = f'{config}{node}'
        for dev in device_block:
            config = f'{config}{dev}'

        try:
            with open(dhcpfile, 'w', encoding='utf-8') as dhcp:
                dhcp.write(config)
            try:
                validate_config = subprocess.run(["dhcpd", "-t", "-cf", dhcpfile], check=True)
                if validate_config.returncode:
                    validate = False
                    self.logger.error(f'DHCP file : {dhcpfile} containing errors.')
            except:
                self.logger.error(f'DHCP file : {dhcpfile} containing errors.')
            else:
                shutil.copyfile(dhcpfile, '/etc/dhcp/dhcpd.conf')
                self.logger.info(f'DHCP File created : {dhcpfile}')
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    def dhcp_config(self, ntpserver=None):
        """
        This method will prepare DHCP configuration."""
        if ntpserver:
            ntpserver = f'option domain-name-servers {ntpserver};'
        else:
            ntpserver=''

        omapi_key=''
        if CONSTANT['DHCP']['OMAPIKEY']:
           omapi_key = f"""
omapi-port 7911;
omapi-key omapi_key;

key omapi_key {{
    algorithm hmac-md5;
    secret {CONSTANT['DHCP']['OMAPIKEY']};
}}
"""

        config = f"""
#
# DHCP Server Configuration file.
# created by Luna
#
option domain-name "lunacluster";
option luna-id code 129 = text;
option client-architecture code 93 = unsigned integer 16;
{ntpserver}

{omapi_key}

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


    def dhcp_subnet(self, network=None, netmask=None, nextserver=None, gateway=None,
                    dhcp_range_start=None, dhcp_range_end=None):
        """
        This method prepare the netwok block
        for all DHCP enabled networks
        """
        subnet_block = f"""
subnet {network} netmask {netmask} {{
    max-lease-time 28800;
    if exists user-class and option user-class = "iPXE" {{
        filename "http://{nextserver}:7050/boot";
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

    option routers {gateway};
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
        files, ns_ip = [], []
        zone_config, rev_ip = '', ''
        cluster = Database().get_record(None, 'cluster', None)
        if cluster and 'ns_ip' in cluster[0]:
            ns_ip.append(cluster[0]['ns_ip'])
#	TWAN
        controller = Database().get_record_join(['ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'], ['tableref="controller"','controller.hostname="controller"'])
        controllerip = controller[0]['ipaddress']
#        if ns_ip:
#            forwarder = ns_ip
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
            #TWAN
            node_interface = Database().get_record_join(['node.name as nodename','ipaddress.ipaddress','network.name as networkname'], ['ipaddress.tablerefid=nodeinterface.id','nodeinterface.nodeid=node.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f'ipaddress.networkid="{nwkid}"'])
            nodelist, ptrnodelist= [], []
            if node_interface:
                for interface in node_interface:
                    nodeip = interface['ipaddress']
                    nodelist.append(f"{interface['nodename']}                 IN A {interface['ipaddress']}")
                    sub_ip = interface['ipaddress'].split('.')  # NOT IPv6 COMPLIANT!! needs overhaul. PENDING
                    nodeptr = sub_ip[2]+'.'+sub_ip[3]
                    ptrnodelist.append(f"{nodeptr}                    IN PTR {interface['nodename']}.{interface['networkname']}.")

            for item in ['otherdevices','switch']:
                devices = Database().get_record_join([f'{item}.name as devname','ipaddress.ipaddress','network.name as networkname'], [f'ipaddress.tablerefid={item}.id','network.id=ipaddress.networkid'], [f'tableref="{item}"',f'ipaddress.networkid="{nwkid}"'])
                if devices:
                    for device in devices:
                        devip = device['ipaddress']
                        nodelist.append(f"{device['devname']}                 IN A {device['ipaddress']}")
                        sub_ip = device['ipaddress'].split('.')  # NOT IPv6 COMPLIANT!! needs overhaul. PENDING
                        nodeptr = sub_ip[2]+'.'+sub_ip[3]
                        ptrnodelist.append(f"{nodeptr}                    IN PTR {device['devname']}.{device['networkname']}.")

            zone_name_config = self.dns_zone_name(networkname, controllerip, nodelist)
            zone_ptr_config = self.dns_zone_ptr(networkname, ptrnodelist)
            namefile = {
                'source': f'/var/tmp/luna2/{networkname}.luna.zone',
                'destination': f'/var/named/{networkname}.luna.zone'
            }
            ptrfile = {
                'source': f'/var/tmp/luna2/{rev_ip}.luna.zone',
                'destination': f'/var/named/{rev_ip}.luna.zone'
            }
            files.append(namefile)
            files.append(ptrfile)
            try:
                with open(namefile['source'], 'w', encoding='utf-8') as filename:
                    filename.write(zone_name_config)
                with open(ptrfile['source'], 'w', encoding='utf-8') as fileptr:
                    fileptr.write(zone_ptr_config)
                try:
                    zone_cmd = ['named-checkzone', f'luna.{networkname}', namefile['source']]
                    validate_zone_name = subprocess.run(zone_cmd, check = True)
                    if validate_zone_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {namefile["source"]} containing errors.')
                except:
                    self.logger.error(f'DNS zone file: {namefile["source"]} containing errors.')
                try:
                    ptr_cmd = ['named-checkzone', f'luna.{networkname}', ptrfile['source']]
                    validate_ptr_name = subprocess.run(ptr_cmd, check = True)
                    if validate_ptr_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {ptrfile["source"]} containing errors.')
                except:
                    self.logger.error(f'DNS zone file: {ptrfile["source"]} containing errors.')
            except Exception as exp:
                self.logger.error(f"Uh oh... {exp}")
#            if ns_ip is None:
#                forwarder = ';'.join(ns_ip)

#        config = self.dns_config(forwarder)
        config = self.dns_config()  # < ------------  we call this one without any forwarder as that forwarder thing above here has to be revised
        dnsfile = {'source': '/var/tmp/luna2/named.conf', 'destination': '/etc/named.conf'}
        try:
            files.append(dnsfile)
            with open(dnsfile["source"], 'w', encoding='utf-8') as dns:
                dns.write(config)
            dnszonefile = {
                'source': '/var/tmp/luna2/named.luna.zones',
#                'destination': '/trinity/local/etc/named.luna.zones'
                'destination': '/etc/named.luna.zones'
            }
            files.append(dnszonefile)
            with open(dnszonefile["source"], 'w', encoding='utf-8') as dnszone:
                dnszone.write(zone_config)
            self.logger.info(f'DNS files : {files}')
            if validate:
                if not os.path.exists('/var/named'):
                    os.makedirs('/var/named')
                for dnsfiles in files:
                    shutil.copyfile(dnsfiles["source"], dnsfiles["destination"])
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
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
        else:
            forwarder=''

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
"""

#TWAN
        if os.path.exists("/trinity/local/var/lib/named/dynamic"):
            config += f"""
        managed-keys-directory "/trinity/local/var/lib/named/dynamic";
"""

        config += f"""

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
/*include "/trinity/local/etc/named.luna.zones";*/

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
        else:
            nodelist = ''
        zone_name_config = f"""
$TTL 604800
@ IN SOA                controller.{networkname}. root.controller.{networkname}. ( ; domain email
                        {unixtime}        ; serial number
                        86400       ; refresh
                        14400       ; retry
                        3628800       ; expire
                        604800 )     ; min TTL

                        IN NS controller.{networkname}.
"""
        if controllerip is not None:
            zone_name_config += f"""
controller              IN A {controllerip}
"""
        zone_name_config += f"""
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
        else:
            nodelist = ''
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

    # ----------------------------------------------------------------

    def device_ipaddress_config(self,deviceid,device,ipaddress,network=None):
        if network:
            networkid = Database().getid_byname('network', network)
        else:
            network_details = Database().get_record_join(['network.name as network','network.id'], ['ipaddress.tablerefid=switch.id','network.id=ipaddress.networkid'], [f'tableref="{device}"',f"switch.name='{deviceid}'"])
            if network_details:
                networkid=network_details[0]['id']
            else:
                return False,"Network not specified"
        if ipaddress and deviceid:
            my_ipaddress={}
            my_ipaddress['networkid']=networkid
            result_ip=False
            network_details = Database().get_record(None, 'network', f'WHERE id={networkid}')
            valid_ip = Helper().check_ip_range(ipaddress, f"{network_details[0]['network']}/{network_details[0]['subnet']}")
            self.logger.info(f"Ipaddress {ipaddress} for {device} is [{valid_ip}]")
            if valid_ip is False:
                return False,f"invalid IP address for {device}. Network {network_details[0]['name']}: {network_details[0]['network']}/{network_details[0]['subnet']}"

            my_ipaddress['ipaddress']=ipaddress
            check_ip = Database().get_record(None, 'ipaddress', f'WHERE tablerefid = "{deviceid}" AND tableref = "{device}"')
            if check_ip:
                row = Helper().make_rows(my_ipaddress)
                where = [{"column": "tablerefid", "value": deviceid},{"column": "tableref", "value": device}]
                Database().update('ipaddress', row, where)
            else:
                my_ipaddress['tableref']=device
                my_ipaddress['tablerefid']=deviceid
                row = Helper().make_rows(my_ipaddress)
                result_ip=Database().insert('ipaddress', row)
                self.logger.info(f"IP for {device} created => {result_ip}.")
                if result_ip is False:
                    return False,"IP address assignment failed"

            return True,"ip address changed"

        return False,"not enough details"


    # ----------------------------------------------------------------

    def node_interface_config(self,nodeid,interface_name,macaddress=None):

        check_interface = Database().get_record(None, 'nodeinterface', f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"')

        result_if=False
        my_interface={}

        if not check_interface: # ----> easy. both the interface as ipaddress do not exist
            my_interface['interface']=interface_name
            my_interface['nodeid']=nodeid                
            if macaddress is not None:
                my_interface['macaddress']=interface['macaddress'] 
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('nodeinterface', row)

        else: # we have to update the interface
            if macaddress is not None:
                my_interface['macaddress']=macaddress
            if my_interface:
                row = Helper().make_rows(my_interface)
                where = [{"column": "id", "value": check_interface[0]['id']}]
                result_if = Database().update('nodeinterface', row, where)
            else: # no change here, we bail
                result_if=True

        if result_if:
            self.logger.info(f"interface {interface_name} created or changed with result {result_if}")
            return True,f"interface {interface_name} created or changed with result {result_if}"

        self.logger.info(f"interface {interface_name} config failed with result {result_if}")
        return False,f"interface {interface_name} config failed with result {result_if}"


    # -----------------

    def node_interface_ipaddress_config(self,nodeid,interface_name,ipaddress,network=None):

        ipaddress_check,valid_ip,result_ip=False,False,False
        my_ipaddress={}

        if network:
            network_details = Database().get_record(None, 'network', f'WHERE name="{network}"')
        else:
            network_details = Database().get_record_join(['network.*'], ['ipaddress.tablerefid=nodeinterface.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f'nodeinterface.id="{nodeid}"',f'nodeinterface.interface="{interface_name}"'])
                
        if not network_details:
            self.logger.info(f"not enough information provided. network name incorrect or need network name if there is no existing ipaddress")
            return False,f"not enough information provided. network name incorrect or need network name if there is no existing ipaddress"

        my_ipaddress['networkid']=network_details[0]['id']
        if ipaddress:
            my_ipaddress['ipaddress']=ipaddress
            valid_ip = Helper().check_ip_range(ipaddress, f"{network_details[0]['network']}/{network_details[0]['subnet']}")

        if not valid_ip:
            self.logger.info(f"invalid IP address for {interface_name}. Network {network_details[0]['name']}: {network_details[0]['network']}/{network_details[0]['subnet']}")
            return False,f"invalid IP address for {interface_name}. Network {network_details[0]['name']}: {network_details[0]['network']}/{network_details[0]['subnet']}"

        ipaddress_check = Database().get_record_join(['ipaddress.*'], ['ipaddress.tablerefid=nodeinterface.id'], ['tableref="nodeinterface"',f'nodeinterface.nodeid="{nodeid}"',f'nodeinterface.interface="{interface_name}"'])

        if ipaddress_check: # existing ip config we need to modify
            row = Helper().make_rows(my_ipaddress)
            where = [{"column": "id", "value": f"{ipaddress_check[0]['id']}"}]
            result_ip = Database().update('ipaddress', row, where)

        else: # no ip set yet for the interface
            check_interface = Database().get_record(None, 'nodeinterface', f'WHERE nodeid = "{nodeid}" AND interface = "{interface_name}"')
            if check_interface:
                my_ipaddress['tableref']='nodeinterface'
                my_ipaddress['tablerefid']=check_interface[0]['id']
                row = Helper().make_rows(my_ipaddress)
                result_ip = Database().insert('ipaddress', row)

        if result_ip:
            self.logger.info(f"ipaddress for {interface_name} configured with result {result_ip}")
            return True,f"ipaddress for {interface_name} configured with result {result_ip}"
        
        self.logger.info(f"ipaddress for {interface_name} config failed with result {result_ip}")
        return False,f"ipaddress for {interface_name} config failed with result {result_ip}"

    # -----------------

