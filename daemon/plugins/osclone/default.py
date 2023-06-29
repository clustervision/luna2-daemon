#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the default OS clone/copy plugin, which takes care of the actual copying of src->dst image

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
    Class for cloning an image filesystem
    """
    """
    This plugin class requires 1 mandatory method:
    -- clone
    """

    def __init__(self):
        self.logger = Log.get_logger()

    def clone(self,source,destination):
        command=f"tar -C \"{source}\"/ --one-file-system --exclude=/proc/* --exclude=/sys/* --xattrs --acls --selinux -cf - . | (cd \"{destination}\"/ && tar -xf -)"
        mesg,exit_code = Helper().runcommand(command,True,3600)
        if exit_code == 0:
            return True, "Success"
        return False,mesg

