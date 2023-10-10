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
System user+group related activities
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from utils.helper import Helper
from common.constant import CONSTANT


class OsUser():
    """
    This class will be used for all OS User related operations.
    """

    def __init__(self):
        """
        Default Constructor
        """
        plugins_path = CONSTANT["PLUGINS"]["PLUGINS_DIR"]
        osuser_plugins = Helper().plugin_finder(f'{plugins_path}/osuser')
        Plugin = Helper().plugin_load(osuser_plugins, 'osuser', ['obol'])
        self.plugin = Plugin()


    def list_users(self):
        """
        This method will list all OS Users.
        """
        try:
            result_state, result_msg = self.plugin.list_users()
            if result_state is True:
                return True, {"config": {"osuser": result_msg}}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'Problem while listing OS Users: {exp}'

    def get_user(self, name):
        """
        This method will get data of a OS User.
        """
        try:
            result_state, result_msg = self.plugin.get_user(name)
            if result_state is True:
                return True, {"config": {"osuser": {name: result_msg}}}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'Problem while getting Os User: {exp}'

    def update_user(self, name, **kwargs):
        """
        This method will update data of a OS User.
        """
        try:
            result_state, result_msg = self.plugin.update_user(name, **kwargs)
            return result_state, result_msg
        except Exception as exp:
            return False, f'Problem while updating Os User: {exp}'

    def delete_user(self, name):
        """
        This method will delete a OS User.
        """
        try:
            result_state, result_msg = self.plugin.delete_user(name)
            return result_state, result_msg
        except Exception as exp:
            return False, f'Problem while deleting Os User: {exp}'

    def list_groups(self):
        """
        This method will list all OS Groups.
        """
        try:
            result_state, result_msg = self.plugin.list_groups()
            if result_state is True:
                return True, {"config": {"osgroup": result_msg}}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'Problem while listing OS Groups: {exp}'

    def get_group(self, name):
        """
        This method will get data of a OS Group.
        """
        try:
            result_state, result_msg = self.plugin.get_group(name)
            if result_state is True:
                return True, {"config": {"osgroup": {name: result_msg}}}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'Problem while getting Os Group: {exp}'

    def update_group(self, name, **kwargs):
        """
        This method will update data of a OS Group.
        """
        try:
            result_state, result_msg = self.plugin.update_group(name, **kwargs)
            return result_state, result_msg
        except Exception as exp:
            return False, f'Problem while updating Os Group: {exp}'

    def delete_group(self, name):
        """
        This method will delete a OS Group.
        """
        try:
            result_state, result_msg = self.plugin.delete_group(name)
            return result_state, result_msg
        except Exception as exp:
            return False, f'Problem while deleting Os Group: {exp}'
