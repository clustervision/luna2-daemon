
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

#import os
#import pwd
#import sys
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
        - syncimage
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def clone(self, source=None, destination=None):
        """
        Method that does the actual copy task
        """
        if (not destination) or (not source):
            return False,"source/destination not provided"
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

    # ---------------------------------------------------------------------------

    def syncimage(self,remote_host=None, remote_image_directory=None, osimage=None, local_image_directory=None):
        """
        Method to rsync image data from remote host to local.
        """
        if remote_host and remote_image_directory and osimage and local_image_directory:
            command=f"mkdir -p {local_image_directory}"
            message,exit_code = Helper().runcommand(command,True,60)
            command=f"rsync -aHv --one-file-system --delete-after {remote_host}:{remote_image_directory}/* {local_image_directory}/ > /tmp/syncimage.out"
            self.logger.info(command)
            message,exit_code = Helper().runcommand(command,True,3600)
            self.logger.debug(f"exit_code = {exit_code}")
            if exit_code != 0:
                if len(message) > 0:
                    message=message[1]
                return False,f"{message}"
            return True, "Success"
        else:
            return False, "missing information to handle request"

