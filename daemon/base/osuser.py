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
from utils.log import Log
from common.constant import CONSTANT


class OsUser():
    """
    This class will be used for all OS User related operations.
    """

    def __init__(self):
        """
        Default Constructor
        """
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]
        self.osuser_plugins = Helper().plugin_finder(f'{plugins_path}/osuser')
        # needs to be with constants. pending
        self.OsUserPlugin = Helper().plugin_load(self.osuser_plugins, 'osuser', ['obol'])


    def list_users(self):
        """
        This method will list all OS users.
        """
        try:
            results = self.OsUserPlugin().list_users()
            ret = results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while listing Os Users: {exp}'


    def list_groups(self):
        """
        This method will list all OS user groups.
        """
        try:
            results = OsUserPlugin().list_groups()
            ret = results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while listing Os Groups: {exp}'


    def update_user(self, username, request):
        """
        This method will update a OS users.
        """
        request_data = request.data
        data = None
        if request_data and name in request_data['config']['user']:
            data = request_data['config']['osuser'][name] 
        if not data:
            return False, "user details not provided"
        try:
            userinfo={}
            userinfo['username']=username
            for item in ['userid', 'primarygroup', 'groups', 'fullname', 'homedir', 'shell']:
                userinfo[item]=None
                if item in data:
                    userinfo[item] = data[item]
            
            results = OsUserPlugin().update_user(
                username = userinfo['username'],
                userid = userinfo['userid'],
                pimarygroup = userinfo['primarygroup'],
                groups = userinfo['groups'],
                fullname = userinfo['fullname'],
                homedir = userinfo['homedir'],
                shell = userinfo['shell']
            )
            ret=results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while updating Os Users: {exp}'


    def delete_user(self, name):
        """
        This method will delete a OS users.
        """
        try:
            results = OsUserPlugin().delete_user(name)
            ret = results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while deleting Os Users: {exp}'


    def update_group(self, groupname, request):
        """
        This method will update a OS user group.
        """
        request_data = request.data
        data = None
        if request_data and name in request_data['config']['user']:
            data = request_data['config']['osgroup'][name]           
        if not data:
            return False, "user details not provided" 
        try:
            groupinfo = {}
            groupinfo['groupname'] = groupname
            for item in ['groupid','users']:
                groupinfo[item] = None
                if item in data:
                    groupinfo[item] = data[item]
            
            results = OsUserPlugin().update_groups(
                groupname = groupinfo['groupname'],
                groupid = groupinfo['groupid'],
                users = groupinfo['users']
            )
            ret = results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while updating Os Groups: {exp}'


    def delete_group(self, name):
        """
        This method will delete a OS user group.
        """
        try:
            results = OsUserPlugin().delete_group(name)
            ret = results[0]
            mesg = None
            if len(results) > 1:
                mesg = results[1]
            return ret, mesg
        except Exception as exp:
            return False, f'problem while deleting Os Groups: {exp}'
