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
        on, off, reset, status, cycle, identify, no_identify are required methods
        """

    def power_on(self, device=None, username=None, password=None):
        """
        This method will be used for power on.
        """
        try:
            return self.execute(device, 'power on', username, password)
        except Exception as exp:
            return False, f"{exp}"


    def power_off(self, device=None, username=None, password=None):
        """
        This method will be used for power off.
        """
        try:
            return self.execute(device, 'power off', username, password)
        except Exception as exp:
            return False, f"{exp}"


    def power_reset(self, device=None, username=None, password=None):
        """
        This method will be used for power reset.
        """
        try:
            return self.execute(device, 'power reset', username, password)
        except Exception as exp:
            return False, f"{exp}"


    def power_status(self, device=None, username=None, password=None):
        """
        This method will be used to check power status.
        """
        try:
            return self.execute(device, 'power status', username, password)
        except Exception as exp:
            return False, f"{exp}"

    def power_cycle(self, device=None, username=None, password=None):
        """
        This method will be used for power cycle.
        """
        try:
            return self.execute(device, 'power status', username, password)
        except Exception as exp:
            return False, f"{exp}"

    def identify(self, device=None, username=None, password=None):
        """
        This method will be used to get identify device.
        """
        try:
            return self.execute(device, 'identify', username, password)
        except Exception as exp:
            return False, f"{exp}"
        return True, "success"

    def no_identify(self, device=None, username=None, password=None):
        """
        This method will be used to get identify device.
        """
        try:
            return self.execute(device, 'noidentify', username, password)
        except Exception as exp:
            return False, f"{exp}"
        return True, "success"

    def sel_clear(self, device=None, username=None, password=None):
        """
        This method will be used to clear sel logs on device.
        """
        try:
            return self.execute(device, 'sel clear', username, password)
        except Exception as exp:
            return False, f"{exp}"
        return True, "success"

    def sel_list(self, device=None, username=None, password=None):
        """
        This method will be used to get sel logs from device.
        """
        try:
            return self.execute(device, 'sel list', username, password)
        except Exception as exp:
            return False, f"{exp}"
        return True, "success"


    def execute(self, device=None, action=None, username=None, password=None):
        """
        This is an private method.
        """
        status = False
        response = ''
        command = f'ipmitool -I lanplus -C3 -U {username} -P {password} -H {device} '
        command += f'chassis {action}'
        output, exit_code = Helper().runcommand(command,True,10)
        if output and exit_code == 0:
            response = str(output[0].decode())
            response = response.replace('Chassis Power is ', '')
            response = response.replace('Chassis Power Control: ', '')
            response = response.replace('\n', '')
            response = response.lower()
            if not response:
                response = action
            status = True
        else:
            if len(output)>1:
                response = str(output[1].decode())
            response = f"Command execution failed with exit code {exit_code}: {response}"
        return status, response

