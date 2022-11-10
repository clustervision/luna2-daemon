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


class Helper(object):


    """
    Constructor - As of now, nothing have to initialize.
    """
    def __init__(self):
        self.logger = Log.get_logger()


    """
    Input - command, which need to be executed
    Process - Via subprocess, execute the command and wait to receive the complete output.
    Output - Detailed result.
    """
    def runcommand(self, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.logger.debug("Command Executed {}".format(command))
        output = process.communicate()
        process.wait()
        self.logger.debug("Output Of Command {} ".format(str(output)))
        return output


    """
    Input - Error Message (String)
    Output - Stop The Daemon With Error Message .
    """
    def stop(self, message=None):
        self.logger.error(f'Daemon Stopped Because: {message}')
        sys.exit(-1)
        return False

    """
    Input - Directory
    Output - Directory Existence, Readability and Writable
    """
    def checkpathstate(self, path=None):
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


    """
    Input - Path of File or Directory
    Output - File or directory or Not Exists
    """
    def checkpathtype(self, path=None):
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


    """
    Input - Path of File or Directory
    Output - True or False Is exists or not
    """
    def checkpath(self, path=None):
        if os.path.exists(path):
            response = True
        else:
            response = None
        return response


    """
    Input - Path of Template
    Output - True or False For Errors
    """
    def checkjinja(self, template=None):
        env = Environment()
        try:
            with open(template) as template:
                env.parse(template.read())
            return True
        except Exception as e:
            print(f'{template} Have Errors.')
            print(e)
            return False


    """
    Input - JSON
    Output - True or False For Errors
    Usecase - switchcolumn = Database().get_columns('switch')
    """
    def check_json(self, request=None):
        try:
            json.loads(request)
        except Exception as e:
            return False
        return True
    

    """
    Input - TWO LISTS 
    Output - True or False For Errors
    """
    def checkin_list(self, list1=None, list2=None):
        CHECK = True
        for ITEM in list1:
            if ITEM not in list2:
                CHECK = False
        return CHECK


    """
    Input - IP Address 
    Output - Subnet
    """
    def get_subnet(self, ipaddr=None):
        net = ipaddress.ip_network(ipaddr, strict=False)
        return net.netmask