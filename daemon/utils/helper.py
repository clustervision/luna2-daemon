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
This Is a Helper Class, which help the project to provide the common Methods.

"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import signal
import sys
import subprocess
import pwd
import grp
from time import time
import logging
import threading
import re
import queue
import json
import ipaddress
import netifaces as ni
from configparser import RawConfigParser
import hostlist
from netaddr import IPNetwork, IPAddress
from jinja2 import Environment, meta, FileSystemLoader
from cryptography.fernet import Fernet
from utils.log import Log
from utils.database import Database
from utils.plugin_manager import PluginManager
from utils.template_manager import TemplateManager
from utils.plugin_tree import build_plugin_tree
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
        self.IPregex = re.compile(r"^((([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))|(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})))\/?[0-9]*$")



################### ---> Experiment to compare the logic

    def get_template_vars(self, template=None):
        """
        This method will return all the variables used in the templates.
        """
        dbcol = {}
        env = Environment(loader=FileSystemLoader('templates'))
        template_source = env.loader.get_source(env, template)[0]
        parsed_content = env.parse(template_source)
        variables = list(meta.find_undeclared_variables(parsed_content))
        for varn in variables:
            if varn in CONSTANT["TEMPLATES"]["VARS"]:
                varsplit = CONSTANT["TEMPLATES"]["VARS"][varn].split('.')
                dbrecord = Database().get_record(table=varsplit[0])
                if dbrecord:
                    dbcol[varn] = dbrecord[0][varsplit[1]]
        return dbcol

################### ---> Experiment to compare the logic

    def runcommand(self, command, return_exit_code=False, timeout_sec=7200):
        """
        Input - command, which need to be executed
        Process - Via subprocess, execute the command and wait to receive the complete output.
        Output - Detailed result.
        """
        kill = lambda process: process.kill()
        output = None
        self.logger.debug(f'Command Executed [{command}]')
        my_process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, shell=True)
        my_timer = threading.Timer(timeout_sec,kill,[my_process])
        try:
            my_timer.start()
            output = my_process.communicate()
            exit_code = my_process.wait()
        finally:
            my_timer.cancel()

        # with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as process:
        #     output = process.communicate()
        #     exit_code = process.wait()
        self.logger.debug(f'Output Of Command [{output[0]}], [{output[1]}]')
        if return_exit_code:
            return output,exit_code
        return output


    def proc_start_time(self, pid):
        """
        Return the kernel start-time (field 22 of /proc/<pid>/stat) as a string, or None when
        the pid has no /proc entry. Stored alongside a worker pid so a reused pid - same number,
        different process - can be told apart from the process we actually stamped.
        """
        try:
            with open(f"/proc/{int(pid)}/stat", "r", encoding="utf-8") as handle:
                data = handle.read()
            # comm (field 2) is parenthesised and may itself contain spaces or ')', so split
            # only what follows the final ')': starttime is field 22, i.e. index 19 after comm.
            rest = data[data.rfind(')') + 1:].split()
            return rest[19]
        except (FileNotFoundError, ProcessLookupError, ValueError, IndexError):
            return None

    def pid_alive(self, pid, started=None):
        """
        True only if pid currently exists AND - when started is supplied - its start-time still
        matches. A reused pid therefore reads as not alive, which is what keeps the reaper from
        mistaking an unrelated process for a worker and what keeps a kill off the wrong target.
        """
        if not pid:
            return False
        current = self.proc_start_time(pid)
        if current is None:
            return False
        if started is not None and str(started) != str(current):
            return False
        return True

    def safe_kill_worker(self, pid, started, sig=signal.SIGKILL):
        """
        Kill a stamped worker as safely as possible: only after confirming it is still the exact
        process we stamped (start-time match, via pid_alive), never a vital or our own pid, and only
        group-killing when it is its own session leader (setsid succeeded) so the signal can never
        reach the gunicorn worker, the master or the background owner. Returns True if a signal was
        delivered, False if refused or the worker was already gone.
        """
        if not self.pid_alive(pid, started):
            return False
        pid = int(pid)
        if pid <= 1 or pid == os.getpid():
            self.logger.warning(f"refusing to signal vital or self pid {pid}")
            return False
        try:
            pgid = os.getpgid(pid)
        except (ProcessLookupError, OSError):
            return False
        try:
            if pgid == pid:
                os.killpg(pgid, sig)      # isolated session leader: take the group and its children
                self.logger.warning(f"safe_kill_worker: signalled process group {pgid} with signal {sig}")
            else:
                os.kill(pid, sig)         # not isolated: signal only the worker, never its group
                self.logger.warning(f"safe_kill_worker: signalled pid {pid} (not session-isolated) with signal {sig}")
            return True
        except (ProcessLookupError, PermissionError, OSError) as exp:
            self.logger.warning(f"could not signal worker pid {pid}: {exp}")
            return False


    def stop(self, message=None):
        """
        Input - Error Message (String)
        Output - Stop The Daemon With Error Message .
        """
        self.logger.error(f'Daemon Stopped Because: {message}')
        return False


    def check_path_state(self, path=None):
        """
        Input - Directory
        Output - Directory if exists, readable or writable
        """
        state = False
        path_type = self.check_path_type(path)
        if path_type in('File', 'Directory'):
            if os.access(path, os.R_OK):
                if os.access(path, os.W_OK):
                    state = True
                else:
                    self.logger.debug(f'{path_type} {path} is not writable.')
            else:
                self.logger.debug(f'{path_type} {path} is not readable.')
        else:
            self.logger.debug(f'{path_type} {path} is not exists.')
        return state


    def check_path_type(self, path=None):
        """
        Input - Path of File or Directory
        Output - File or directory or Not Exists
        """
        path_status = self.check_path(path)
        if path_status:
            if os.path.isdir(path):
                response = 'Directory'
            elif os.path.isfile(path):
                response = 'File'
            else:
                response = 'socket or FIFO or device'
        else:
            response = 'Not exists'
        return response


    def check_path(self, path=None):
        """
        Input - Path of File or Directory
        Output - True or False Is exists or not
        """
        if os.path.exists(path):
            response = True
        else:
            response = None
        return response


    def check_jinja(self, template=None):
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
        # env.parse is here to catch a syntax error, and a jinja TemplateSyntaxError is not an
        # OSError - so catching only OSError meant the one thing this check exists for escaped
        # instead of returning False. templates are the customisation surface: an admin's typo
        # reached the housekeeper, where a raise blocks every queued task behind it.
        except Exception as exp:
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


    def compare_list(self, list1=None, list2=None):
        """
        Input - TWO LISTS
        Output - True or False For Errors
        """
        check = True
        for item in list1:
            if item not in list2:
                check = False
                self.logger.error(f"{item} not in {list2}")
        return check


    def check_if_ipv6(self, ipaddr=None):
        """
        just a simple check if the address is ipv6. defaults to ipv4.
        the colon is the whole test: an IPv4 address cannot carry one and neither can a host
        name, while no valid IPv6 address is without one. this also answered True on a leading
        [a-f], which reads any name starting with those letters - europe.pool.ntp.org,
        clock.example.com - as IPv6. that could only ever produce a false positive, and it did:
        it rejected the very server names ntp_server exists to accept, and bracketed host names
        into broken URLs. accepts a name as well as an address, so it is safe on either.
        """
        return bool(ipaddr and ':' in str(ipaddr))


    def check_ip(self, ipaddr=None):
        """
        Add blacklist filter;
        https://clustervision.atlassian.net/wiki/spaces/TRIX/pages/52461574/2022-11-11+Development+meeting
        """
        response = []
        try:
            ipaddr = ipaddr.replace(' ','')
            ipaddr_list = ipaddr.split(',')
            for ipaddr in ipaddr_list:
                if self.IPregex.match(ipaddr):
                    ip_address = IPNetwork(ipaddr)
                    response.append(str(ip_address.ip))
        except Exception as exp:
            self.logger.error(f'Invalid IP address: {ipaddr}, Exception is {exp}.')
            return None
        return ','.join(response)


    def check_cidr(self, value=None, ipv6=None):
        """
        Validate a CIDR prefix such as 10.144.35.0/24 or 2001:db8:35::/64. A prefix is required
        (a bare address is rejected). When ipv6 is True or False, the address family must match,
        so the caller can keep a v4-only or v6-only field honest. Returns True or False.
        """
        if not value or '/' not in str(value):
            return False
        try:
            net = ipaddress.ip_network(str(value), strict=False)
        except (ValueError, TypeError):
            return False
        if ipv6 is not None and (net.version == 6) != bool(ipv6):
            return False
        return True


    def get_network(self, ipaddr=None, subnet=None):
        """
        Input - IP Address + Subnet
        Output - Network such as 10.141.0.0/16
        """
        net = None
        if not ipaddr:
            return None
        try:
            if subnet:
                net = ipaddress.ip_network(ipaddr+'/'+subnet, strict=False)
            else:
                net = ipaddress.ip_network(ipaddr, strict=False)
        except (ValueError, TypeError) as exp:
            self.logger.error(f'Invalid IP address: {ipaddr}/{subnet}, Exception is {exp}.')
        return str(net)


    def get_network_details(self, ipaddr=None):
        """
        Input - IP Address such as 10.141.0.0/16
        Output - Network and Subnet such as 10.141.0.0 and 16
        (we settled for a cidr notation to be ipv6 compliant)
        """
        response = {}
        try:
            #net = IPNetwork(f"{ipaddr}")
            net = ipaddress.ip_network(ipaddr, strict=False)
            response['network'], response['subnet'] = str(net).split('/')
        except (ValueError, TypeError) as exp:
            self.logger.error(f'Invalid IP address: {ipaddr}, Exception is {exp}.')
        return response


    def get_netmask(self, ipaddr=None):
        """
        Input - IP Address
        Output - Subnet
        """
        response = None
        try:
            net = ipaddress.ip_network(ipaddr, strict=False)
            response = str(net.netmask)
        except (ValueError, TypeError) as exp:
            self.logger.error(f'Invalid subnet: {ipaddr}, Exception is {exp}.')
        return response


    def check_ip_range(self, ipaddr=None, network=None):
        """
        Check If IP is in range or not
        """
        try:
            if self.check_ip(ipaddr):
                if IPAddress(ipaddr) in IPNetwork(network):
                    return True
        except Exception as exp:
            self.logger.error(f'Invalid subnet: {ipaddr}, Exception is {exp}.')
        return False

    def check_ip_exist(self, data=None):
        """
        check if IP is valid or not
        check if IP address is in database or not True false
        """
        if 'ipaddress' in data:
            if self.check_ip(data['ipaddress']):
                ipaddr = data["ipaddress"]
                where = f'ipaddress = "{ipaddr}";'
                record = Database().get_record(table='ipaddress', where=where)
                if not record:
                    subnet = self.get_netmask(data['ipaddress'])
                    row = [
                            {"column": 'ipaddress', "value": data['ipaddress']},
                            {"column": 'network', "value": data['network']},
                            {"column": 'subnet', "value": subnet}
                            ]
                    Database().insert('ipaddress', row)
                    subnet_record = Database().get_record(table='ipaddress', where=where)
                    data['ipaddress'] = subnet_record[0]['id']
        return data

    def get_available_ip(self, network=None, subnet=None, takenips=[], ping=False):
        """
        This method will provide the available IP address list.
        Optionally we can ping it to just make sure...
        """
        if subnet:
            network+=str('/'+subnet)
        try:
            avail = None
            net = ipaddress.ip_network(f"{network}")
            if not ping:
                avail = (str(ip) for ip in net.hosts() if str(ip) not in takenips)
                return str(next(avail))
            # we try to ping for X ips, if none of these are free,
            # something else is going on (read: rogue devices)....
            ret = 0
            maximum = 5
            while(maximum > 0 and ret != 1):
                avail = (str(ip) for ip in net.hosts() if str(ip) not in takenips)
                takenips.append(avail)
                result, ret = self.runcommand(f"ping -w1 -c1 {avail}", True, 3)
                maximum -= 1
            return str(next(avail))
        except Exception as exp:
            return None

    def get_next_ip(self, ipaddr, takenips=[], ping=False):
        """
        This method will provide the next available IP address starting from offset ipaddr.
        Optionally we can ping it to just make sure...
        """
        try:
            avail = None
            tel = 1
            maximum = 10
            while maximum > 0:
                avail = str(ipaddress.ip_address(ipaddr) + tel)
                if avail not in takenips:
                    if ping:
                        result, ret = self.runcommand(f"ping -w1 -c1 {avail}", True, 3)
                        self.logger.debug(f"avail = {avail}, ret = {ret}, result = {result}")
                        if ret != 1:
                            takenips.append(avail)
                            continue
                    return avail
                self.logger.debug(f"avail {avail} is in takenips")
                tel += 1
                maximum -= 1
            return None
        except Exception as exp:
            return None

    def get_ip_range_size(self, start=None, end=None):
        """
        This method will provide the range size of IP.
        """
        try:
            if self.check_if_ipv6(start):
                start_ip = ipaddress.IPv6Address(start)
                end_ip = ipaddress.IPv6Address(end)
                count=int(end_ip)-int(start_ip)
                self.logger.debug(f"get_ip_range_size ipv6: {end_ip} - {start_ip} = {count}")
                return count
            else:
                start_ip = ipaddress.IPv4Address(start)
                end_ip = ipaddress.IPv4Address(end)
                count=int(end_ip)-int(start_ip)
                self.logger.debug(f"get_ip_range_size ipv4: {end_ip} - {start_ip} = {count}")
                return count
        except Exception as exp:
            return 0

    def get_ip_range_ips(self, start=None, end=None):
        """
        This method will provide the range size of IP.
        """
        try:
            ip_list=[]
            if self.check_if_ipv6(start):
                counter = 100000
                start_ip = ipaddress.IPv6Address(start)
                end_ip = ipaddress.IPv6Address(end)
                for ip in range(int(start_ip),(int(end_ip)+1)):
                    ip_list.append(str(ipaddress.IPv6Address(ip)))
                    if counter < 0:
                        break
                    counter -= 1
            else:
                start_ip = ipaddress.IPv4Address(start)
                end_ip = ipaddress.IPv4Address(end)
                for ip in range(int(start_ip),(int(end_ip)+1)):
                    ip_list.append(str(ipaddress.IPv4Address(ip)))
            return ip_list
        except Exception as exp:
            return []

    def get_network_size(self, network=None, subnet=None):
        """
        This method will provide the network size of IP.
        """
        try:
            if self.check_if_ipv6(network):
                self.logger.debug(f"get_network_size ipv6: {network} / {subnet}")
                if subnet:
                    nwk=ipaddress.IPv6Network(network+'/'+subnet)
                    return nwk.num_addresses-2
                else:
                    nwk=ipaddress.IPv6Network(network)
                    return nwk.num_addresses-2
            else:
                self.logger.info(f"get_network_size ipv4: {network} / {subnet}")
                if subnet:
                    nwk=ipaddress.IPv4Network(network+'/'+subnet)
                    return nwk.num_addresses-2
                else:
                    nwk=ipaddress.IPv4Network(network)
                    return nwk.num_addresses-2
        except Exception as exp:
            return 0

    def get_ip_range_first_last_ip(self, network=None, subnet=None, size=None, offset=None):
        """
        This method will provide the range of first and last IP.
        """
        try:
            nwk=None
            ipv6=False
            if self.check_if_ipv6(network):
                nwk = ipaddress.IPv6Network(network+'/'+subnet)
                ipv6=True
            else:
                nwk = ipaddress.IPv4Network(network+'/'+subnet)
            first = nwk[1]
            last  = nwk[(size+1)]
            if offset:
                first_int = int(first) + offset
                last_int = int(last) + offset
                if ipv6:
                    first = ipaddress.IPv6Address(first_int)
                    last = ipaddress.IPv6Address(last_int)
                else:
                    first = ipaddress.IPv4Address(first_int)
                    last = ipaddress.IPv4Address(last_int)
            return str(first),str(last)
        except Exception as exp:
            self.logger.error(f"something went wrong: {exp}")
            return None, None

    def get_quantity_occupied_ipaddress_in_network(self, network=None, ipversion='ipv4'):
        """
        This method will provide the quantity occupied in a network by ipaddress.
        """
        IPv6=""
        if ipversion == 'ipv6':
            IPv6="_ipv6"
        if network:
            ipaddress_list = Database().get_record_join(
                ['ipaddress.ipaddress'+IPv6],
                ['ipaddress.networkid=network.id'],
                [f"network.name='{network}'"]
            )
            return len(ipaddress_list)

    def get_controller_addresses_for_networks(self, every=False):
        """
        This method returns which of this controller's own addresses sits on each
        Luna network, as {'ipv4': {network: ip}, 'ipv6': {network: ip}} - or with
        every=True, {'ipv4': {network: [ip, ...]}, ...} keeping all of them.

        Both forms come off the one walk rather than being separate methods,
        because two methods answering the same question is what this file was
        rewritten to stop. A caller that needs one address wants the first; a
        caller publishing them wants all, since a machine can hold its own address
        and a floating one on the same network and nothing local can tell which is
        which.

        The database cannot answer this. A controller carries exactly one ipaddress
        row and it is the cluster one, so on a machine with an address per network -
        which is every controller - the rest are known only to the kernel. They are
        read from the interfaces and matched against the networks Luna already
        defines, so the answer is in Luna's own terms rather than the operating
        system's.

        Which of an address's own networks it belongs to is the question two
        different things need answered: what a BMC can reach the controller on, and
        which address a per-network DNS zone should publish. Both were getting it
        somewhere else, and somewhere else was wrong in both cases.
        """
        found = {'ipv4': {}, 'ipv6': {}}
        for family, addresses in self.walk_controller_networks():
            for network, interface, ip in addresses:
                if every:
                    if ip not in found[family].setdefault(network, []):
                        found[family][network].append(ip)
                elif network not in found[family]:
                    found[family][network] = ip
        return found


    # the NIC walk held for a moment, shared by every caller in the process, in the
    # same shape as owner_cache below. HA() reads this in its constructor and the
    # daemon builds an HA() per request on several routes, so during a boot storm the
    # same unchanged interfaces were being enumerated thousands of times a minute.
    #
    # Held for a moment and not for the life of the process, deliberately. Everything
    # asking is asking about NOW: a floating address moves on failover and find_me
    # decides who is master from it, so a stale answer is wrong exactly when it costs
    # most. A few seconds collapses a burst into one walk and still notices a
    # failover well inside one HA poll.
    address_cache = {}
    address_cache_ttl = 5

    def local_addresses(self):
        """
        This method returns every address this machine holds, as a list of
        (family, interface, ip). IPv6 comes before IPv4 within each interface.

        This is the only place the daemon reads its own NICs. Everything that
        needs to know something about this machine's addresses is a match on top
        of this list - which Luna network an address falls inside, which
        interface carries it, or which controller row it belongs to - and each of
        those used to walk the interfaces itself. Three copies of one walk is how
        the InfiniBand zone came to publish an ethernet address.

        The order is part of the contract, not an accident. A machine can hold
        several addresses that answer the same question and the caller takes the
        first, so reordering this silently changes which address they get.
        """
        now = time()
        cached = Helper.address_cache.get('local')
        if cached and now - cached[1] < Helper.address_cache_ttl:
            return cached[0]
        found = []
        for interface in ni.interfaces():
            for family, want in (('ipv6', ni.AF_INET6), ('ipv4', ni.AF_INET)):
                try:
                    assignments = ni.ifaddresses(interface)[want]
                except (KeyError, ValueError):
                    continue
                for assignment in assignments:
                    # a link-local IPv6 address carries its scope as '%eth0'
                    ip, *_ = str(assignment.get('addr') or '').split('%', 1) + [None]
                    if not ip:
                        continue
                    self.logger.debug(f"Interface {interface} has ip {ip}")
                    found.append((family, interface, ip))
        Helper.address_cache['local'] = (found, now)
        return found


    def walk_controller_networks(self):
        """
        This method pairs every local address with the Luna network it falls inside.

        One pass, shared by the callers that want different halves of the answer -
        the interface name and the address - so a machine's NICs are read once and
        matched by one rule.
        """
        networks = Database().get_record(table='network') or []
        matched = {'ipv4': [], 'ipv6': []}
        for family, interface, ip in self.local_addresses():
            key, subnet = (('network_ipv6', 'subnet_ipv6') if family == 'ipv6'
                           else ('network', 'subnet'))
            for network in networks:
                if not network[key] or not network[subnet]:
                    continue
                if Helper().check_ip_range(ip, f"{network[key]}/{network[subnet]}"):
                    matched[family].append((network['name'], interface, ip))
                    break
        return [('ipv6', matched['ipv6']), ('ipv4', matched['ipv4'])]


    def get_controller_interfaces_for_networks(self):
        """
        This method returns which interface carries each Luna network, as
        {'ipv4': {network: interface}, 'ipv6': {network: interface}}.

        The first interface found for a network wins, which is what it has always
        done: a machine can carry one network on two NICs and the answer has to be
        one of them.
        """
        interfaces = {'ipv4': {}, 'ipv6': {}}
        for family, addresses in self.walk_controller_networks():
            for network, interface, ip in addresses:
                if network in interfaces[family]:
                    continue
                interfaces[family][network] = interface
                self.logger.info(f"Controller {family} {ip} on interface {interface} "
                                 f"belongs to network {network}")
        for network in Database().get_record(table='network') or []:
            if (network['name'] not in interfaces['ipv6']
                    and network['name'] not in interfaces['ipv4']):
                self.logger.warning(
                    f"Network {network['name']} has no matching interface on controller")
        return interfaces


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


    def make_bool(self, variable=None, empty_is_none=False):
        """
        Input - string
        Output - Boolean
        """
        if isinstance(variable, bool):
            pass
        elif isinstance(variable, (str, int)):
            if variable in ('1', 1, 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'y'):
                variable = True
            elif variable in ('0', 0, 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'n'):
                variable = False
            elif empty_is_none and len(variable)==0:
                variable = None
        else:
            variable = None
        return variable


    def bool_to_string(self, variable=None, empty_is_none=False):
        """
        Input - string
        Output - Boolean
        """
        if isinstance(variable, bool):
            if variable is True:
                variable = '1'
            else:
                variable = '0'
        elif isinstance(variable, (str, int)):
            if variable in ('1', 1, 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES', 'y'):
                variable = '1'
            elif variable in ('0', 0, 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'n'):
                variable = '0'
            elif empty_is_none and len(variable)==0:
                variable = None
        else:
            variable = None
        return variable


    def make_bool_string(self, variable=None):
        """
        Input - bool-like value
        Output - '1'/'0' or None
        """
        return self.bool_to_string(variable)


    def _secret_cipher(self):
        """Build a Fernet from LUNAKEY, or return None if the key is unusable."""
        try:
            return Fernet(bytes(LUNAKEY, 'utf-8'))
        except Exception:
            return None


    def encrypt_string(self, string=None):
        """
        Input  - base64 secret string
        Output - Fernet token when [SECRETS] ENCRYPT_SECRETS is enabled and a usable
                 key exists; otherwise the input unchanged (legacy base64 at rest).
        """
        if not string:
            return string
        enabled = self.make_bool(CONSTANT.get('SECRETS', {}).get('ENCRYPT_SECRETS', ''))
        if not enabled:
            return string
        cipher = self._secret_cipher()
        if not cipher:
            return string
        return cipher.encrypt(string.encode()).decode()


    def decrypt_string(self, string=None):
        """
        Input  - stored secret (Fernet token or legacy base64/plain)
        Output - decrypted value for Fernet tokens; the input unchanged for
                 legacy values. Never raises on legacy data.
        """
        if not string:
            return string
        cipher = self._secret_cipher()
        if not cipher:
            return string
        try:
            return cipher.decrypt(string.encode()).decode()
        except Exception:
            return string


    # in-memory resolution cache shared by all callers in the process. installs come in
    # waves, so without it every node in a wave triggers the same lookups all over again.
    owner_cache = {}
    owner_cache_ttl = 60
    # NSS has no timeout of its own: an unreachable directory makes getpwnam block for
    # as long as its own client library allows, and this runs while a node waits for its
    # install payload. A bounded lookup degrades to the stored resolution instead.
    owner_lookup_timeout = 20

    def nss_lookup(self, function, key):
        """
        Run one NSS lookup with a deadline. Returns the entry, or None when the name
        is unknown OR the directory did not answer in time - the caller treats both
        as 'not resolvable right now', which is what they are.
        """
        outcome = {}

        def run():
            try:
                outcome['value'] = function(key)
            except KeyError:
                outcome['missing'] = True
            except Exception as exp:
                outcome['error'] = exp

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(Helper.owner_lookup_timeout)
        if worker.is_alive():
            self.logger.warning(
                f"NSS lookup for {key} did not answer within "
                f"{Helper.owner_lookup_timeout}s; treating it as unresolvable")
            return None
        if 'error' in outcome:
            self.logger.error(f"NSS lookup for {key} failed: {outcome['error']}")
            return None
        return outcome.get('value')

    def resolve_owner(self, owner=None):
        """
        Input  - owner as stored with a secret or profile file: 'user' or 'user:group',
                 numeric parts allowed
        Output - the numeric 'uid' or 'uid:gid' form when resolvable, the last stored
                 resolution when the lookup fails (e.g. directory unreachable), or the
                 input unchanged when it was never resolvable.
        Resolution goes through glibc NSS (pwd/grp), the same stack getent uses: local
        files, sssd/ldap, nis - whatever nsswitch.conf lists. The installer's chroot
        cannot resolve directory users, which is why it receives numbers instead.
        """
        if not owner:
            return owner
        now = time()
        cached = Helper.owner_cache.get(owner)
        if cached and now - cached[1] < Helper.owner_cache_ttl:
            return cached[0]
        user, _, group = owner.partition(':')
        resolved = None
        uid, gid = user, group
        if not user.isdigit():
            entry = self.nss_lookup(pwd.getpwnam, user)
            uid = str(entry.pw_uid) if entry else None
        if group and not group.isdigit():
            entry = self.nss_lookup(grp.getgrnam, group)
            gid = str(entry.gr_gid) if entry else None
        if uid and (gid or not group):
            resolved = f"{uid}:{gid}" if group else uid
        record = Database().get_record(table='ownercache', where=f'name = "{owner}"')
        if resolved:
            if record:
                if record[0]['resolved'] != resolved:
                    where = [{"column": "name", "value": owner}]
                    row = self.make_rows({'resolved': resolved, 'updated': 'NOW'})
                    Database().update('ownercache', row, where)
            else:
                row = self.make_rows({'name': owner, 'resolved': resolved, 'updated': 'NOW'})
                Database().insert('ownercache', row)
        elif record:
            resolved = record[0]['resolved']
            self.logger.warning(f"could not resolve owner {owner}; using stored {resolved}")
        else:
            resolved = owner
            self.logger.warning(f"could not resolve owner {owner}; passing it on as is")
        Helper.owner_cache[owner] = (resolved, now)
        return resolved


    def check_owner(self, owner=None):
        """
        True when every non-numeric part of 'user' or 'user:group' is known to NSS
        right now. Unlike resolve_owner this never falls back to a stored value:
        it is the write-time typo check, and a fallback would mask exactly the
        mistake it exists to catch.
        """
        if not owner:
            return True
        user, _, group = owner.partition(':')
        if user and not user.isdigit() and not self.nss_lookup(pwd.getpwnam, user):
            return False
        if group and not group.isdigit() and not self.nss_lookup(grp.getgrnam, group):
            return False
        return True


    def check_section(self, filename=None, parent_dict=None):
        """
        Compare the bootstrap/constants section with the predefined dictionary sections.
        """
        check = True
        parser = RawConfigParser()
        parser.read(filename)
        for item in list(parent_dict.keys()):
            if item not in parser.sections():
                self.logger.error(f'{item} is missing, please check {filename}.')
                check = False
        return check


    def check_option(self, filename=None, section=None, option=None, parent_dict=None):
        """
        Compare the bootstrap/constants option with the predefined dictionary options.
        """
        check = True
        parser = RawConfigParser()
        parser.read(filename)
        for item in list(parent_dict[section].keys()):
            if item.lower() not in list(dict(parser.items(section)).keys()):
                self.logger.error(f'{section} does not have {option}, please check {filename}.')
                check = False
        return check


    def nodes_and_groups(self):
        """
        function that generates node/group key/value pairs
        """
        response=[]
        records = Database().get_record_join(
                ['node.name','group.name as groupname'],
                ['group.id=node.groupid'],
                [])
        if records:
            for node in records:
                row = {'name': node['name'], 'group': node['groupname']}
                response.append(row)
        return response


    def chunks(self, lst, num):
        """
        Yield successive n-sized chunks from lst.
        """
        for i in range(0, len(lst), num):
            yield lst[i:i + num]


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


    def update_node_state(self, nodeid=None, state=None):
        """
        This method will update the node status
        while booting.
        """
        row = [{"column": "status", "value": state}]
        where = [{"column": "id", "value": nodeid}]
        status = Database().update('node', row, where)
        return status

    """
    Below Classes/Functions maintained by Antoine antoine.schonewille@clustervision.com
    """

    class Pipeline():
        """
        Class to allow a single element pipeline between main thread and child.
        Antoine Jan 2023
        """
        def __init__(self):
            self.message = {}
            self.nodes   = {}
            self._lock = threading.Lock()


        def get_messages(self):
            """
            This method will retrieve the message.
            """
            with self._lock:
                message = self.message
            return message


        def add_message(self, message=None):
            """
            This method will add the message.
            """
            with self._lock:
                self.message.update(message)


        def del_message(self, _key=None):
            """
            This method will delete the message.
            """
            with self._lock:
                self.message.pop(_key, None)


        def get_node(self):
            """
            This method will retrieve the node.
            """
            with self._lock:
                if len(self.nodes)>0:
                    node = self.nodes.popitem()
                    return (node[0],node[1])
                return


        def add_nodes(self, nodes=[]):
            """
            This method will add the node.
            """
            with self._lock:
                self.nodes.update(nodes)


        def get_nodes(self):
            """
            This method will add the nodes.
            """
            with self._lock:
                return self.nodes


        def has_nodes(self):
            """
            This method will check the node.
            """
            with self._lock:
                if len(self.nodes) > 0:
                    return True
                return False

    # ---------------------------------------------------------
    # not sure if below is still being used

    def insert_mesg_in_status(self, request_id=None, username_initiator=None, message=None):
        """
        This method will insert the message in the status table.
        """
        # current_datetime=datetime.now().replace(microsecond=0)
        current_datetime = "NOW"
        row = [
            {"column": "request_id", "value": f"{request_id}"},
            {"column": "created", "value": str(current_datetime)},
            {"column": "username_initiator", "value": f"{username_initiator}"},
            {"column": "read", "value": "0"},
            {"column": "message", "value": f"{message}"}
        ]
        Database().insert('status', row)


    # -----------------------------------------------------------------

    def convert_list_to_dict(self, mylist=[], byname=None):
        """
        This method will convert list into the dictionary.
        """
    # This def receives a 'Database().get_record' list of dicts
    # and converts it into a dictionary where the main key is the value of 'byname' of the dict objects inside the list
    # eg group[0]{id:'1',....} with a byname of 'id' makes a dict like group{'1':{.....

        mydict={}
        if not byname:
            byname='name'
        if mylist:
            for element in mylist:
                if type(element) is dict:
                    if byname not in element:
                        return None
                    myname=element[byname]
                    mydict[myname]={}
                    for item in element:
                        mydict[myname][item]=element[item]
        return mydict

    def dedupe_adjacent(self, mylist=[]):
        new_mylist = []
        mylist_track = {}
        for item in mylist:
            if item not in mylist_track:
                new_mylist.append(item)
                mylist_track[item]=True
        return new_mylist

    # -----------------------------------------------------------------

    def add_padding(self, inp=None):
        islist = True
        if isinstance(inp, str):
            islist = False
        if islist is False:
            lines = inp.splitlines()
        else:
            lines = inp
        line = 0
        while line < len(lines):
            lines[line] = "    "+lines[line]
            line+=1
        if islist is False:
            return "\n".join(lines)
        return lines

    # -----------------------------------------------------------------

    def get_more_info(self, key=None):
        if key:
            if key in ['initrdfile','kernelfile']:
                return f"{key}: Make sure to have a packed osimage and/or correct osimage (tag) set"
            elif key in ['cleartoboot']:
                return f"{key}: Booting has been temporarily paused due to constraints"
        return None

    # -----------------------------------------------------------------

    def plugin_finder(self, startpath=None):
        """
        This method will find the plugin.
        """
        return build_plugin_tree(startpath=startpath, logger=self.logger)


    def plugin_load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name=None):
        """
        This method will load the plugin.
        """
        manager = PluginManager(logger=self.logger)
        return manager.load(
            plugins=plugins,
            root=root,
            levelone=levelone,
            leveltwo=leveltwo,
            class_name=class_name,
        )

    # -----------------------------------------------------------------------------------

    def template_find(self, plugins=None, root=None, levelone=None, leveltwo=None):
        """
        This method will find the desired template in the same style as plugin_load
        """
        manager = TemplateManager(logger=self.logger)
        return manager.find(
            plugins=plugins,
            root=root,
            levelone=levelone,
            leveltwo=leveltwo,
        )


    # -----------------------------------------------------------------------------------

    def get_access_code(self,status,response=None):
        # this def is not suitable for 200 reponses
        access_code=404
        if status is True:
            access_code=201
            if 'update' in response or 'remove' in response or 'delete' in response:
                access_code=204
        else:
            if 'nvalid request' in response or 'ad request' in response or ' invalid ' in response:
                access_code=400
            elif 'uthentication error' in response:
                access_code=401
            elif 'nternal error' in response:
                access_code=500
            elif 'ervice unavailable' in response:
                access_code=503
        return access_code

