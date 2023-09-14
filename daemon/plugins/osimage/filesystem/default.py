
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Default OS Image filesystem related plugin. Supports any generic filesystem
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import pwd
import subprocess
import shutil
from time import sleep, time
import sys
import uuid
# from datetime import datetime
# import json
from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    Class for operating with osimages records.
    """

    def __init__(self):
        """
        two defined methods are mandatory:
        - clone  
        - getpath
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def clone(self, source=None, destination=None):
        command=f"tar -C \"{source}\"/ --one-file-system --exclude=/proc/* --exclude=/sys/* --xattrs --acls --selinux -cf - . | (cd \"{destination}\"/ && tar -xf -)"
        mesg,exit_code = Helper().runcommand(command,True,3600)
        if exit_code == 0:
            return True, "Success"
        return False,mesg

    # ---------------------------------------------------------------------------

    def getpath(self, image_directory=None, osimage=None, tag=None):
        if tag:
            self.logger.info(f"Filesystem tag {tag} requested for {osimage}")
            #return True,image_directory+'/'+osimage+'@'+tag
        return True,image_directory+'/'+osimage


