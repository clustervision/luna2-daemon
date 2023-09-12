#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        This method will list all OS users.
        """
        try:
            result_state, result_msg = self.plugin.list_users()
            if result_state:
                return True, {item: data.dict() for item, data in result_msg.items()}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while listing Os Users: {exp}'


    def get_user(self, name):
        """
        This method will list all OS users.
        """
        try:
            result_state, result_msg = self.plugin.get_user(name)
            if result_state:
                return True, result_msg.dict()
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while getting Os User: {exp}'

    def update_user(self, name, **kwargs):
        """
        This method will list all OS users.
        """
        try:
            osuserdata = self.plugin.osuserdata(**kwargs)
            result_state, result_msg = self.plugin.update_user(name, osuserdata)
            if result_state:
                return True, result_msg
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while updating Os User: {exp}'


    def delete_user(self, name):
        """
        This method will list all OS users.
        """
        try:
            result_state, result_msg = self.plugin.delete_user(name)
            print(result_state, result_msg)
            if result_state:
                return True, result_msg
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while deleting Os User: {exp}'
        

    def list_groups(self):
        """
        This method will list all OS groups.
        """
        try:
            result_state, result_msg = self.plugin.list_groups()
            if result_state:
                return True, {item: data.dict() for item, data in result_msg.items()}
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while listing Os Users: {exp}'


    def get_group(self, name):
        """
        This method will list all OS groups.
        """
        try:
            result_state, result_msg = self.plugin.get_group(name)
            if result_state:
                return True, result_msg.dict()
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while getting Os User: {exp}'

    def update_group(self, name, **kwargs):
        """
        This method will list all OS groups.
        """
        try:
            osgroupdata = self.plugin.osgroupdata(**kwargs)
            result_state, result_msg = self.plugin.update_group(name, osgroupdata)
            if result_state:
                return True, result_msg
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while updating Os User: {exp}'


    def delete_group(self, name):
        """
        This method will list all OS groups.
        """
        try:
            result_state, result_msg = self.plugin.delete_group(name)
            if result_state:
                return True, result_msg
            else:
                return False, result_msg
        except Exception as exp:
            return False, f'problem while deleting Os User: {exp}'

