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
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import sys
import subprocess
import threading
import re
import queue
import json
import ipaddress
from configparser import RawConfigParser
import hostlist
from netaddr import IPNetwork, IPAddress
from jinja2 import Environment, meta, FileSystemLoader
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT


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
                dbrecord = Database().get_record(None, varsplit[0], None)
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
                    self.logger.debug(f'{path_type} {path} is writable.')
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
                response = 'File'
            elif os.path.isfile(path):
                response = 'Directory'
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
        just a simple check if the address is ipv6. defaults to ipv4
        """
        if ipaddr and ":" in ipaddr:
            return True
        IPv6regex = re.compile(r"[a-f]+")
        try:
            if IPv6regex.match(ipaddr):
                return True
        except:
            pass
        return False


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
                where = f' WHERE `ipaddress` = "{ipaddr}";'
                record = Database().get_record(None, 'ipaddress', where)
                if not record:
                    subnet = self.get_netmask(data['ipaddress'])
                    row = [
                            {"column": 'ipaddress', "value": data['ipaddress']},
                            {"column": 'network', "value": data['network']},
                            {"column": 'subnet', "value": subnet}
                            ]
                    Database().insert('ipaddress', row)
                    subnet_record = Database().get_record(None, 'ipaddress', where)
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


    def make_bool(self, variable=None):
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
        else:
            variable = None
        return variable


    def bool_to_string(self, variable=None):
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
        else:
            variable = None
        return variable


    def encrypt_string(self, string=None):
        """
        Input - string
        Output - Encrypt String
        """
        return string
        # fernetobj = Fernet(bytes(LUNAKEY, 'utf-8'))
        # response = fernetobj.encrypt(string.encode()).decode()
        # return response


    def decrypt_string(self, string=None):
        """
        Input - string
        Output - Decrypt Encoded String
        """
        return string
        # fernetobj = Fernet(bytes(LUNAKEY, 'utf-8'))
        # response = fernetobj.decrypt(string).decode()
        # return response


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
        # command =
        # ipmitool -U {username} -P {password} chassis power {action} -H {hostname} -I lanplus -C3
        self.logger.info(f'hostname: {hostname}.')
        command = f'ipmitool -U {username} -P {password} chassis power {action} -H 127.0.0.1 -I lanplus -C3'
        self.logger.info(f'IPMI command to be executed: {command}.')
        output,exit_code = self.runcommand(command,True,10)
        if output and exit_code == 0:
            response = str(output[0].decode())
            response = response.replace('Chassis Power is ', '')
            response = response.replace('\n', '')
        else:
            response = f"Command execution failed with exit code {exit_code}"
        self.logger.info(f'response: [{response}]')
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
        # plugin_finder traverses a path to find python 'plugin' files in nested directories

        def set_leaf(tree=None, branches=None, leaf=None):
            """
            Set a terminal element to *leaf* within nested dictionaries.              
            *branches* defines the path through dictionaries.                            
            Example:                                                                      
            >>> t = {}                                                                    
            >>> set_leaf(t, ['b1','b2','b3'], 'new_leaf')                                 
            >>> print t                                                                   
            {'b1': {'b2': {'b3': 'new_leaf'}}}                                             
            """
            if len(branches) == 1:
                tree[branches[0]] = leaf
                return
            if not branches[0] in tree.keys():
                tree[branches[0]] = {}
            set_leaf(tree[branches[0]], branches[1:], leaf)

        tree = {}
        for root, dirs, files in os.walk(startpath):
            # branches = [startpath]
            branches = [os.path.basename(startpath)]
            if root != startpath:
                branches.extend(os.path.relpath(root, startpath).split(os.sep))
            set_leaf(tree, branches, dict([(d,{}) for d in dirs]+[(f,None) for f in files]))
        self.logger.debug(f"PLUGIN TREE {startpath}: {tree}")
        return tree


    def plugin_load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name=None):
        """
        This method will load the plugin.
        """
        roottree = root.split('/')
        root = root.replace('/','.')
        self.logger.debug(f"Loading module {class_name}/Plugin from plugins.{root}.{levelone}.{leveltwo} / {plugins}")
        if not plugins: # or (root and root not in plugins):
            self.logger.error(f"Provided Plugins tree is empty or is missing root. plugins = [{plugins}], root = [{root}]")
            return None
        module = None
        class_name = class_name or 'Plugin'
        levelones = []
        try:
            myplugin = plugins
            for treestep in roottree:
                if treestep in myplugin:
                    myplugin = myplugin[treestep]
            self.logger.debug(f"myplugin = [{myplugin}]")
        except Exception as exp:
            self.logger.error(f"Loading module caused a problem in roottree: {exp}")
            return None
        if type(levelone) == type('string'):
            levelones.append(levelone)
        else:
            levelones = levelone
        try:
            for levelone in levelones:
                if leveltwo and levelone+leveltwo+'.py' in myplugin:
                    self.logger.debug(f"loading plugins.{root}.{levelone}{leveltwo}")
                    module = __import__('plugins.'+root+'.'+levelone+leveltwo,fromlist=[class_name])
                    break
                elif levelone in myplugin.keys():
                    if leveltwo and leveltwo in myplugin[levelone]:
                        plugin = leveltwo.rsplit('.',1)
                        self.logger.debug(f"loading plugins.{root}.{levelone}.{plugin[0]}")
                        module = __import__('plugins.'+root+'.'+levelone+'.'+plugin[0],fromlist=[class_name])
                        break
                    elif 'default.py' in myplugin[levelone]:
                        self.logger.debug(f"loading plugins.{root}.{levelone}.default")
                        module = __import__('plugins.'+root+'.'+levelone+'.default',fromlist=[class_name])
                        break
                elif levelone+'.py' in myplugin:
                    self.logger.debug(f"loading plugins.{root}.{levelone}")
                    module = __import__('plugins.'+root+'.'+levelone,fromlist=[class_name])
                    break
            if not module:
                self.logger.debug(f"loading plugins.{root}.default")
                module = __import__('plugins.'+root+'.default',fromlist=[class_name])
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            #print(exc_type, fname, exc_tb.tb_lineno)
            self.logger.error(f"Loading module caused a problem during selection: {exp}, {exc_type} in {exc_tb.tb_lineno}]")
            return None

        try:
            if module:
                self.logger.debug(vars(module))
                self.logger.debug(dir(module))
                my_class = getattr(module,class_name)
                return my_class
            return None
        except Exception as exp:
            self.logger.error(f"Getattr caused a problem: {exp}")
            return None

    # -----------------------------------------------------------------------------------

    def template_find(self, plugins=None, root=None, levelone=None, leveltwo=None):
        """
        This method will find the desired template in the same style as plugin_load
        """
        roottree = root.split('/')
        self.logger.debug(f"Finding template in plugins.{root}.{levelone}.{leveltwo} / {plugins}")
        if not plugins: # or (root and root not in plugins):
            self.logger.error(f"Provided Plugins tree is empty or is missing root. plugins = [{plugins}], root = [{root}]")
            return None
        levelones = []
        try:
            myplugin = plugins
            for treestep in roottree:
                if treestep in myplugin:
                    myplugin = myplugin[treestep]
            self.logger.debug(f"myplugin = [{myplugin}]")
        except Exception as exp:
            self.logger.error(f"Loading template caused a problem in roottree: {exp}")
            return None
        if type(levelone) == type('string'):
            levelones.append(levelone)
        else:
            levelones = levelone
        try:
            for levelone in levelones:
                if leveltwo and levelone+leveltwo+'.templ' in myplugin:
                    self.logger.debug(f"found plugins.{root}.{levelone}{leveltwo}")
                    return root+'/'+levelone+leveltwo+'.templ'
                elif levelone in myplugin.keys():
                    if leveltwo and leveltwo in myplugin[levelone]:
                        template = leveltwo.rsplit('.',1)
                        self.logger.debug(f"found plugins.{root}.{levelone}.{template[0]}")
                        return root+'/'+levelone+'/'+template[0]+'.templ'
                    elif 'default.py' in myplugin[levelone]:
                        self.logger.debug(f"found plugins.{root}.{levelone}.default")
                        return root+'/'+levelone+'/default.templ'
                elif levelone+'.templ' in myplugin:
                    self.logger.debug(f"found plugins.{root}.{levelone}")
                    return root+'/'+levelone+'.templ'
            #self.logger.debug(f"loading plugins.{root}.default")
            #return root+'/default.templ'
            return None
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"Loading module caused a problem during selection: {exp}, {exc_type} in {exc_tb.tb_lineno}]")
            return None


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

