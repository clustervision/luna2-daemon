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
Plugin Class ::  Default Power Control
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
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
       
        example code that can be used in below methods/functions: 
        ----------------------------
        bash_command = f'script.sh "{nodename}" "{groupname}"'
        output, exit_code = Helper().runcommand(bash_command,True,10)
        response = str(output[0].decode())
        if exit_code == 0:
            return True, response
        else:
            if len(output)>1:
                response = str(output[1].decode())
            response = f"Command execution failed with exit code {exit_code}: {response}"
            return False, response
        """

    def power_on(self, nodename=None, groupname=None):
        """
        This method will be used for power on events.
        """
        return True, "success"

    def power_off(self, nodename=None, groupname=None):
        """
        This method will be used for power off events.
        """
        return True, "success"

    def power_reset(self, nodename=None, groupname=None):
        """
        This method will be used for power reset.
        """
        return True, "success"

    def power_status(self, nodename=None, groupname=None):
        """
        This method will be used to check power status events.
        """
        return True, "success"

    def power_cycle(self, nodename=None, groupname=None):
        """
        This method will be used for power cycle event.
        """
        return True, "success"

    def identify(self, nodename=None, groupname=None):
        """
        This method will be used to get identify device events.
        """
        return True, "success"

    def no_identify(self, nodename=None, groupname=None):
        """
        This method will be used to get identify device events.
        """
        return True, "success"

    def sel_clear(self, nodename=None, groupname=None):
        """
        This method will be used to clear sel logs on device events.
        """
        return True, "success"

    def sel_list(self, nodename=None, groupname=None):
        """
        This method will be used to get sel logs from device events.
        """
        return True, "success"

