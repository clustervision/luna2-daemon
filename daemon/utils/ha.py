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
Journal class tracks incoming requests that requires replication to other controllers.
It also receives requests that need to be dealt with by the controller itself.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import re
from time import sleep, time
from random import randint
from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

class HA():
    """
    This class is responsible for all H/A related business
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.insync=False
        self.hastate=None

    def set_insync(self,state):
        ha_state={}
        ha_state['insync']=0
        if state is True:
            ha_state['insync']=1
        self.logger.info(f"set_insync ha_state: {ha_state}")
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            where = [{"column": "insync", "value": ha_data[0]['insync']}]
            row = Helper().make_rows(ha_state)
            Database().update('ha', row, where)
        return self.get_insync()

    def get_insync(self):
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            self.logger.debug(f"get_insync new ha_state: {ha_data}")
            self.insync=Helper().make_bool(ha_data[0]['insync'])
            self.logger.debug(f"get_insync new_self.insync: {self.insync}")
        else:
            return False
        return self.insync

    def get_hastate(self):
        if self.hastate is None:
            ha_data = Database().get_record(None, 'ha')
            if ha_data:
                self.logger.info(f"get_hastate new ha_state: {ha_data}")
                self.hastate=Helper().make_bool(ha_data[0]['enabled'])
                self.logger.debug(f"get_hastate new_self.hastate: {self.hastate}")
        return self.hastate

    def set_hastate(self,state):
        ha_state={}
        ha_state['enabled']=0
        if state is True:
            ha_state['enabled']=1
        self.logger.info(f"set_hastate ha_state: {ha_state}")
        ha_data = Database().get_record(None, 'ha')
        if ha_data:
            where = [{"column": "enabled", "value": ha_data[0]['enabled']}]
            row = Helper().make_rows(ha_state)
            Database().update('ha', row, where)
        return self.get_hastate()

