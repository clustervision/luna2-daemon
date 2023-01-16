#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is a Helper Class, which help the project to provide the common Methods.

"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import pwd
import subprocess
import shutil
import queue
import json
import ipaddress
import hostlist
from configparser import RawConfigParser
import pyodbc
from netaddr import IPNetwork
from cryptography.fernet import Fernet
from jinja2 import Environment
from utils.log import Log
from utils.database import Database

from common.constant import CONSTANT, LUNAKEY

class Helper(object):
    """
    All kind of helper methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()
        self.packing = queue.Queue()


    def runcommand(self, command):
        """
        Input - command, which need to be executed
        Process - Via subprocess, execute the command and wait to receive the complete output.
        Output - Detailed result.
        """
        output = None
        with subprocess.Popen(command, stdout=subprocess.PIPE, shell=True) as process:
            self.logger.debug(f'Command Executed {command}')
            output = process.communicate()
            process.wait()
            self.logger.debug(f'Output Of Command {output}')
        return output


    def stop(self, message=None):
        """
        Input - Error Message (String)
        Output - Stop The Daemon With Error Message .
        """
        self.logger.error(f'Daemon Stopped Because: {message}')
        return False


    def checkpathstate(self, path=None):
        """
        Input - Directory
        Output - Directory if exists, readable or writable
        """
        state = False
        pathtype = self.checkpathtype(path)
        if pathtype in('File', 'Directory'):
            if os.access(path, os.R_OK):
                if os.access(path, os.W_OK):
                    state = True
                else:
                    self.logger.debug(f'{pathtype} {path} is writable.')
            else:
                self.logger.debug(f'{pathtype} {path} is not readable.')
        else:
            self.logger.debug(f'{pathtype} {path} is not exists.')
        return state


    def checkpathtype(self, path=None):
        """
        Input - Path of File or Directory
        Output - File or directory or Not Exists
        """
        pathstatus = self.checkpath(path)
        if pathstatus:
            if os.path.isdir(path):
                response = 'File'
            elif os.path.isfile(path):
                response = 'Directory'
            else:
                response = 'socket or FIFO or device'
        else:
            response = 'Not exists'
        return response


    def checkpath(self, path=None):
        """
        Input - Path of File or Directory
        Output - True or False Is exists or not
        """
        if os.path.exists(path):
            response = True
        else:
            response = None
        return response


    def checkjinja(self, template=None):
        """
        Input - Path of Template
        Output - True or False For Errors
        """
        check = False
        env = Environment()
        try:
            with open(template, encoding='utf-8') as template:
                env.parse(template.read())
            check = True
        except OSError as exp:
            self.logger.error(f'{template} Have Errors {exp}.')
        return check


    def check_json(self, request=None):
        """
        Input - JSON
        Output - True or False For Errors
        Usecase - switchcolumn = Database().get_columns('switch')
        """
        check = False
        try:
            json.loads(request)
            check = True
        except ValueError as exp:
            self.logger.error(f'Exception in JSON data: {exp}.')
        return check


    def getlist(self, dictionary=None):
        """
        Get Section List
        """
        key_list = []
        for key in dictionary.keys():
            key_list.append(key)
        return key_list

    def checkin_list(self, list1=None, list2=None):
        """
        Input - TWO LISTS
        Output - True or False For Errors
        """
        check = True
        for item in list1:
            if item not in list2:
                check = False
        return check


    def check_ip(self, ipaddr=None):
        """
        Add blacklist filter;
        https://clustervision.atlassian.net/wiki/spaces/TRIX/pages/52461574/2022-11-11+Development+meeting
        """
        response = ''
        try:
            ip_address = IPNetwork(ipaddr)
            response = str(ip_address.ip)
        except Exception as exp:
            self.logger.error(f'Invalid IP address: {ipaddr}, Exception is {exp}.')
        return response


    def get_network(self, ipaddr=None, subnet=None):
        """
        Input - IP Address + Subnet
        Output - Network such as 10.141.0.0/16
        """
        if subnet:
            net = ipaddress.ip_network(ipaddr+'/'+subnet, strict=False)
        else:
            net = ipaddress.ip_network(ipaddr, strict=False)
        return str(net)


    def get_network_details(self, ipaddr=None):
        """
        Input - IP Address such as 10.141.0.0/16
        Output - Network and Subnet such as 10.141.0.0 and 255.255.0.0
        """
        response = {}
        try:
            net = ipaddress.ip_network(ipaddr, strict=False)
            response['network'] = str(net)
            response['subnet'] = str(net.netmask)
        except (ValueError, TypeError) as exp:
            self.logger.error(f'Invalid IP address: {ipaddr}, Exception is {exp}.')
        return response


    def get_subnet(self, ipaddr=None):
        """
        Input - IP Address
        Output - Subnet
        """
        response = None
        try:
            net = ipaddress.ip_network(ipaddr, strict=False)
            response = net.netmask
        except (ValueError, TypeError) as exp:
            self.logger.error(f'Invalid subnet: {ipaddr}, Exception is {exp}.')
        return response


    def check_ip_range(self, ipaddr=None, network=None):
        """
        Check If IP is in range or not
        """
        response = False
        try:
            if self.check_ip(ipaddr):
                if ipaddress.ip_address(ipaddr) in list(ipaddress.ip_network(network).hosts()):
                    response = True
        except Exception as exp:
            self.logger.error(f'Invalid subnet: {ipaddr}, Exception is {exp}.')
        return response


    def check_ip_exist(self, data=None):
        """
        check if IP is valid or not
        check if IP address is in database or not True false
        """
        if 'ipaddress' in data:
            if self.check_ip(data['ipaddress']):
                where = ' WHERE `ipaddress` = "{}";'.format(data["ipaddress"])
                record = Database().get_record(None, 'ipaddress', where)
                if not record:
                    subnet = self.get_subnet(data['ipaddress'])
                    row = [
                            {"column": 'ipaddress', "value": data['ipaddress']},
                            {"column": 'network', "value": data['network']},
                            {"column": 'subnet', "value": subnet}
                            ]
                    Database().insert('ipaddress', row)
                    where = ' WHERE `ipaddress` = "{}";'.format(data['ipaddress'])
                    subnet_record = Database().get_record(None, 'ipaddress', where)
                    data['ipaddress'] = subnet_record[0]['id']
        return data

    def make_rows(self, data=None):
        """
        Input - IP Address
        Output - Subnet
        """
        row = []
        for column, value in data.items():
            row.append({"column": column, "value": value})
        return row


    def bool_revert(self, variable=None):
        """
        Input - string
        Output - Boolean
        """
        if isinstance(variable, bool):
            if variable is True:
                variable = '1'
            elif variable is False:
                variable = '0'
        elif isinstance(variable, (str, int)):
            if variable in ('1', 1):
                variable = True
            elif variable in ('0', 0):
                variable = False
        else:
            variable = None
        return variable

    def encrypt_string(self, string=None):
        """
        Input - string
        Output - Encrypt String
        """
        fernetobj = Fernet(bytes(LUNAKEY, 'utf-8'))
        response = fernetobj.encrypt(string.encode()).decode()
        return response


    def decrypt_string(self, string=None):
        """
        Input - string
        Output - Decrypt Encoded String
        """
        fernetobj = Fernet(bytes(LUNAKEY, 'utf-8'))
        response = fernetobj.decrypt(string).decode()
        return response


    def pack(self, image=None):
        """
        OS Image Packing method with queue checking
        """
        if {"packing": image} in self.packing.queue:
            self.logger.warning(f'Image {image} packing is ongoing, request is in Queue.')
            response = f'Image {image} packing is ongoing, request is in Queue.'
        else:
            self.packing.put({"packing": image})
            response = self.packimage(image)
            self.logger.info(response)
        return response


    def packimage(self, image=None):
        """
        Input - OS Image Name (string)
        Output - Success/Failure (Boolean)
        """
        def mount(source, target, file_system):
            subprocess.Popen(['/usr/bin/mount', '-t', file_system, source, target])

        def umount(source):
            subprocess.Popen(['/usr/bin/umount', source])

        def prepare_mounts(path):
            mount('devtmpfs', path + '/dev', 'devtmpfs')
            mount('proc', path + '/proc', 'proc')
            mount('sysfs', path + '/sys', 'sysfs')

        def cleanup_mounts(path):
            umount(path + '/dev')
            umount(path + '/proc')
            umount(path + '/sys')

        osimage = Database().get_record(None, 'osimage', f' WHERE name = "{image}"')
        if osimage:
            temp_path = '/tmp'
            image_name = osimage[0]['name']
            image_path = osimage[0]['path']
            dracutmodules = osimage[0]['dracutmodules']
            kernelmodules = osimage[0]['kernelmodules']
            kernelversion = osimage[0]['kernelversion']
            kernelversion_os = self.runcommand('uname -r')
            kernelversion_os = str(kernelversion_os[0])
            kernelversion_os = kernelversion_os.replace("b'", '')
            kernelversion_os = kernelversion_os.replace("\\n'", '')

            if kernelversion_os != kernelversion:
                self.logger.error(f'OS kernel {kernelversion_os} not match with {kernelversion}.')
                return False

            kernel_file = image+'-vmlinuz-'+kernelversion
            intrd_file = image+'-initramfs-'+kernelversion

            cluster = Database().get_record(None, 'cluster', None)
            if cluster:
                user = cluster[0]['user']
            else:
                user = 'luna'
            destination = CONSTANT['FILES']['TARBALL']
            userid = pwd.getpwnam(user).pw_uid
            groupid = pwd.getpwnam(user).pw_gid

            if not os.path.exists(destination):
                os.makedirs(destination)
                os.chown(destination, userid, groupid)

            module_add, module_remove, driver_add, driver_remove = [], [], [], []

            if dracutmodules:
                for i in dracutmodules.split(','):
                    if i[0] != '-':
                        module_add.extend(['--add', i])
                    else:
                        module_remove.extend(['--omit', i[1:]])
            if kernelmodules:
                for i in kernelmodules.split(','):
                    if i[0] != '-':
                        driver_add.extend(['--add-drivers', i])
                    else:
                        driver_remove.extend(['--omit-drivers', i[1:]])

            prepare_mounts(image_path)
            root_path = os.open("/", os.O_RDONLY)
            os.chroot(image_path)
            chroot_path = os.open("/", os.O_DIRECTORY)
            os.fchdir(chroot_path)
            dracut = True
            make = None

            try:
                cmd = ['/usr/sbin/dracut', '--kver', kernelversion, '--list-modules']
                with subprocess.check_output(cmd, universal_newlines=True) as dracut_process:
                    self.logger.info(f'DRACUTPROCESS ==> {dracut_process}.')
                dc_run = (['/usr/sbin/dracut', '--force', '--kver', kernelversion] + module_add + module_remove + driver_add + driver_remove + [temp_path + '/' + intrd_file])
                tout=CONSTANT['FILES']['MAXPACKAGINGTIME']
                with subprocess.check_output(dc_run, timeout=tout, universal_newlines=True) as make:
                    self.logger.info(f'CREATE ==> {make}.')
            except subprocess.CalledProcessError as exp:
                self.logger.error(f'Exception ==> {exp}.')
                dracut = False

            os.fchdir(root_path)
            os.chroot(".")
            os.close(root_path)
            os.close(chroot_path)
            cleanup_mounts(image_path)

            if not dracut:
                self.logger.error(f'Error while building initrd for OS Image {image_name}.')
                return False

            intrd_path = image_path + temp_path + '/' + intrd_file
            kernel_path = image_path + '/boot/vmlinuz-' + kernelversion

            if not os.path.isfile(kernel_path):
                self.logger.error(f'Unable to find kernel in {kernel_path}.')
                return False

            if not os.path.isfile(intrd_path):
                self.logger.error(f'Unable to find initrd in {intrd_path}.')
                return False

            # copy initrd file to inherit perms from parent folder
            shutil.copy(intrd_path, destination + '/' + intrd_file)
            os.remove(intrd_path)
            shutil.copy(kernel_path, destination + '/' + kernel_file)
            os.chown(destination + '/' + intrd_file, userid, groupid)
            os.chmod(destination + '/' + intrd_file, int('0644'))
            os.chown(destination + '/' + kernel_file, userid, groupid)
            os.chmod(destination + '/' + kernel_file, int('0644'))
            self.packing.get() ## Get the Last same Element from Queue
            self.packing.empty() ## Deque the same element from the Queue
        return True


    def checkdbstatus(self):
        """
        A validation method to check which db is configured.
        """
        sqlite, read, write = False, False, False
        code = 503
        if os.path.isfile(CONSTANT['DATABASE']['DATABASE']):
            sqlite = True
            if os.access(CONSTANT['DATABASE']['DATABASE'], os.R_OK):
                read = True
                code = 500
                try:
                    file = open(CONSTANT['DATABASE']['DATABASE'], "a", encoding='utf-8')
                    if file.writable():
                        write = True
                        code = 200
                        file.close()
                except Exception as exp:
                    self.logger.error(f"{CONSTANT['DATABASE']['DATABASE']} has exception {exp}.")

                with open(CONSTANT['DATABASE']['DATABASE'],'r', encoding = "ISO-8859-1") as dbfile:
                    header = dbfile.read(100)
                    if header.startswith('SQLite format 3'):
                        read, write = True, True
                        code = 200
                    else:
                        read, write = False, False
                        code = 503
                        self.logger.error(f"{CONSTANT['DATABASE']['DATABASE']} is not SQLite3.")
            else:
                self.logger.error(f"DATABASE {CONSTANT['DATABASE']['DATABASE']} is not readable.")
        else:
            self.logger.info(f"{CONSTANT['DATABASE']['DATABASE']} is not a SQLite database.")
        if not sqlite:
            try:
                Database().get_cursor()
                read, write = True, True
                code = 200
            except pyodbc.Error as error:
                self.logger.error(f"{CONSTANT['DATABASE']['DATABASE']} connection error: {error}.")
        response = {"database": CONSTANT['DATABASE']['DRIVER'], "read": read, "write": write}
        return response, code


    def checksection(self, filename=None, parent_dict=None):
        """
        Compare the bootstrap/constants section with the predefined dictionary sections.
        """
        check = True
        parser = RawConfigParser()
        parser.read(filename)
        for item in list(parent_dict.keys()):
            if item not in parser.sections():
                self.logger.error(f'{item} is missing, kindly check {filename}.')
                check = False
        return check


    def checkoption(self, filename=None, section=None, option=None, parent_dict=None):
        """
        Compare the bootstrap/constants option with the predefined dictionary options.
        """
        check = True
        parser = RawConfigParser()
        parser.read(filename)
        for item in list(parent_dict[section].keys()):
            if item.lower() not in list(dict(parser.items(section)).keys()):
                self.logger.error(f'{section} do not have {option}, kindly check {filename}.')
                check = False
        return check

    def ipmi_action(self, hostname=None, action=None, username=None, password=None):
        """
        This method will perform below operations on node:
        on, off, reset, identify, noidentify, status
        RAW Command:
        ipmitool -U admin -P password chassis power status -H 127.0.0.1 -I lanplus -C3
        """
        ## TODO
        ## Uncomment line 534 with real hostname, and remove line 535.
        ## Line 535 is for testing purpose.
        # command = f'ipmitool -U {username} -P {password} chassis power {action} -H {hostname} -I lanplus -C3'
        command = f'ipmitool -U {username} -P {password} chassis power {action} -H 127.0.0.1 -I lanplus -C3'
        self.logger.info(f'IPMI command to be executed: {command}.')
        output = self.runcommand(command)
        if output:
            response = str(output[0].decode())
            response = response.replace('Chassis Power is ', '')
            response = response.replace('\n', '')
        else:
            response = "Command execution failed."
        self.logger.info(f'response: {response}.')
        return response


    def chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]


    def get_hostlist(self, rawhosts=None):
        """
        This method will perform power option on node.
        """
        response = []
        # TODO use library hostlist and validate the rawhosts & return a list of hosts.
        self.logger.info(f'Received hostlist: {rawhosts}.')
        try:
            response = hostlist.expand_hostlist(rawhosts)
            self.logger.info(f'Expanded hostlist: {response}.')
        except Exception:
            response = False
            self.logger.error(f'Hostlist is incorrect: {rawhosts}.')
        return response
    

    def dhcp_overwrite(self):
        """
        This method collect dhcp enabled networks,
        node interfaces belongs to the networks and
        other devices which have the mac address.
        write and validates the /var/tmp/luna/dhcpd.conf
        """
        result = False
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

        with open(dhcpfile, 'w') as dhcp:
            dhcp.write(config)
        validate_config = subprocess.run(["dhcpd", "-t", "-cf", dhcpfile])
        if validate_config.returncode:
            self.logger.error(f'DHCP File : {dhcpfile} containing errors.')
        else:
            result = True
            self.logger.info(f'DHCP File created : {dhcpfile}')
        return result


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
        cluster = Database().get_record(None, 'cluster', None)
        ns_ip = cluster[0]['ns_ip']
        if ns_ip:
            forwarder = ns_ip
        else:
            ns_ip = Database().get_record('ns_ip', 'network', None)
            forwarder = ns_ip
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
// BEGIN forwarders
    forwarders {{
              {forwarder};
    }};
// END forwarders

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
        self.logger.info(f'DNS File created : {config}')
        return True
