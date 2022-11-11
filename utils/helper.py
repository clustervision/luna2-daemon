#!/usr/bin/env python3

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

"""
This Is a Helper Class, which help the project to provide the common Methods.

"""
import os
import sys
import subprocess
from jinja2 import Environment
from utils.log import *
import json
import ipaddress
from utils.database import *


class Helper(object):

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()

    
    def runcommand(self, command):
        """
        Input - command, which need to be executed
        Process - Via subprocess, execute the command and wait to receive the complete output.
        Output - Detailed result.
        """
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.logger.debug("Command Executed {}".format(command))
        output = process.communicate()
        process.wait()
        self.logger.debug("Output Of Command {} ".format(str(output)))
        return output


    def stop(self, message=None):
        """
        Input - Error Message (String)
        Output - Stop The Daemon With Error Message .
        """
        self.logger.error(f'Daemon Stopped Because: {message}')
        sys.exit(-1)
        return False

    
    def checkpathstate(self, path=None):
        """
        Input - Directory
        Output - Directory Existence, Readability and Writable
        """
        pathtype = self.checkpathtype(path)
        if pathtype == 'File' or pathtype == 'Directory':
            if os.access(path, os.R_OK):
                if os.access(path, os.W_OK):
                    return True
                else:
                    print(f'{pathtype} {path} Is Writable.')
            else:
                print(f'{pathtype} {path} Is Not readable.')
        else:
            print(f'{pathtype} {path} Is Not exists.')
        return False


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
                response = 'socket orFIFO or device'
        else:
            response = 'Not Exists'
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
        env = Environment()
        try:
            with open(template) as template:
                env.parse(template.read())
            return True
        except Exception as e:
            print(f'{template} Have Errors.')
            print(e)
            return False


    def check_json(self, request=None):
        """
        Input - JSON
        Output - True or False For Errors
        Usecase - switchcolumn = Database().get_columns('switch')
        """
        try:
            json.loads(request)
        except Exception as e:
            return False
        return True
    

    def checkin_list(self, list1=None, list2=None):
        """
        Input - TWO LISTS 
        Output - True or False For Errors
        """
        CHECK = True
        for ITEM in list1:
            if ITEM not in list2:
                CHECK = False
        return CHECK


    def get_subnet(self, ipaddr=None):
        """
        Input - IP Address 
        Output - Subnet
        """
        net = ipaddress.ip_network(ipaddr, strict=False)
        return net.netmask


    def check_ip_exist(self, DATA=None):
        """
        check if IP is valid or not 
        check if IP address is in database or not True false 
        """
        if 'ipaddress' in DATA:
            IPRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
            if IPRECORD:
                return None
            else:
                SUBNET = self.get_subnet(DATA['ipaddress'])
                row = [
                        {"column": 'ipaddress', "value": DATA['ipaddress']},
                        {"column": 'network', "value": DATA['network']},
                        {"column": 'subnet', "value": SUBNET}
                        ]
                result = Database().insert('ipaddress', row)
                SUBNETRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                DATA['ipaddress'] = SUBNETRECORD[0]['id']
        return DATA

    def make_rows(self, data=None):
        """
        Input - IP Address 
        Output - Subnet
        """
        row = []
        for KEY, VALUE in data.items():
            row.append({"column": KEY, "value": VALUE})
        return row