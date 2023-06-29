#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This plugin is the default plugin that uses obol to manage users.

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    Class for operating with regular http provisioning
    """
    """
    This plugin class requires 6 mandatory methods:
    -- list_users
    -- update_user
    -- delete_user
    -- list_groups
    -- update_group
    -- delete_group
    """

    def __init__(self):
        self.logger = ""

    def list_users():
        users={}
        users['testuser']={}
        users['testuser']['fullname']='my Fullname'
        return True, users

    def update_user(username,userid,pimarygroup,groups,fullname,homedir,shell):
        userinfo={}
        userinfo[username]={}
        userinfo[username]['userid']=userid
        userinfo[username]['primarygroup']=primarygroup
        userinfo[username]['groups']=groups
        userinfo[username]['fullname']=fullname
        userinfo[username]['homedir']=homedir
        userinfo[username]['shell']=shell
        return True, userinfo

    def delete_user(username):
        return True,f"user {username} deleted"

    def list_groups():
        groups={}
        groups['testgroup']={}
        groups['testgroup']['groupid']='12343321'
        groups['testgroup']['users']='testuser1, testuser2'
        return True, groups

    def update_group(groupname,groupid,users):
        # if users is a list.... else we treat it as a string
        groupinfo={}
        groupinfo[groupname]={}
        groupinfo[groupname]['groupid']=groupid
        groupinfo[groupname]['users']=users
        return True, groupinfo

    def delete_group(groupname):
        return True,f"group {groupname} deleted"


