#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Default Power Control
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.helper import Helper

class Plugin():
    """
    This is default class for power control plugin.
    """

    def __init__(self):
        """
        on,off,reset,status,cycle,identify,noidentify are required methods
        """

    def on(self, device=None, username=None, password=None, position=None):
        try:
            return self.execute(device,'on',username,password)
        except Exception as exp:
            return False, f"{exp}"


    def off(self, device=None, username=None, password=None, position=None):
        try:
            return self.execute(device,'off',username,password)
        except Exception as exp:
            return False, f"{exp}"


    def reset(self, device=None, username=None, password=None, position=None):
        try:
            return self.execute(device,'reset',username,password)
        except Exception as exp:
            return False, f"{exp}"


    def status(self, device=None, username=None, password=None, position=None):
        try:
            return self.execute(device,'status',username,password)
        except Exception as exp:
            return False, f"{exp}"

    def cycle(self, device=None, username=None, password=None, position=None):
        try:
            return self.execute(device,'status',username,password)
        except Exception as exp:
            return False, f"{exp}"

    def identify(self, device=None, username=None, password=None, position=None):
        return True, "success"

    def noidentify(self, device=None, username=None, password=None, position=None):
        return True, "success"

    # ------------------ private method below -----------------------

    def execute(self,device,action,username,password):
        command = f'ipmitool -I lanplus -C3 -U {username} -P {password} -H {device} chassis power {action}'
        output, exit_code = Helper().runcommand(command,True,10)
        if output and exit_code == 0:
            response = str(output[0].decode())
            response = response.replace('Chassis Power is ', '')
            response = response.replace('Chassis Power Control: ', '')
            response = response.replace('\n', '')
            response = response.lower()
            if not response:
                response=action
            return True, response
        response = f"Command execution failed with exit code {exit_code}"
        return False, response


