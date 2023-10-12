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
BMC Setup Class will handle all bmc setup operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.model import Model


class BMCSetup():
    """
    This class is responsible for all operations for bmc setup.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'bmcsetup'
        self.table_cap = 'BMC Setup'


    def get_all_bmcsetup(self):
        """
        This method will return all the bmcsetup in detailed format.
        """
        status, response = Model().get_record(
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def get_bmcsetup(self, name=None):
        """
        This method will return requested bmcsetup in detailed format.
        """
        status, response = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def get_bmcsetup_member(self, name=None):
        """
        This method will return all the list of all the member node names for a bmcsetup.
        """
        status, response = Model().get_member(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response

    def update_bmcsetup(self, name=None, request_data=None):
        """
        This method will create or update a bmcsetup.
        """
        new_name = 'newbmcname'
        status, response = Model().change_record(
            name = name,
            new_name = new_name,
            table = self.table,
            table_cap = self.table_cap,
            request_data = request_data
        )
        return status, response


    def clone_bmcsetup(self, name=None, request_data=None):
        """
        This method will clone a bmcsetup.
        """
        new_name = 'newbmcname'
        status, response = Model().clone_record(
            name = name,
            new_name = new_name,
            table = self.table,
            table_cap = self.table_cap,
            request_data = request_data
        )
        return status, response


    def delete_bmcsetup(self, name=None):
        """
        This method will delete a bmcsetup.
        """
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response
