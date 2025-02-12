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
This Is the default OS Push plugin, which takes care of pushing an image to a node

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.helper import Helper

#import random
#from time import sleep

class Plugin():
    """
    Class for grabbing a life filesystem
    """
    """
    This plugin class requires 1 mandatory method:
    -- push
    """

    def __init__(self):
        self.logger = Log.get_logger()

    def push(self,osimage,image_path,node,grab_filesystems=[],grab_exclude=[],nodry=False):

#        sleep(10)
#        if random.randrange(1,10) > 5:
#            return False,f"test for [{node}] with [{image_path}] - [{grab_filesystems}], [{grab_exclude}] [{nodry}]"
#        return True,"Success"

        # let's build the rsync command line parameters
        excludes=[]
        exclude_string=""
        if len(grab_exclude)>0:
            for ex in grab_exclude:
                excludes.append(f"--exclude={ex}")
            exclude_string=' '.join(excludes)

        self.logger.debug(f"excludes = {excludes}, grab_filesystems = {grab_filesystems}, grab_exclude = {grab_exclude}")
        exit_code,message=1,None
        if len(grab_filesystems)>0:
            Helper().runcommand("truncate -s 0 /tmp/ospush.out")
            exit_code=0
            for grab in grab_filesystems:
                if exit_code == 0:
                    if nodry is True: # nodry is True means it's for real
                        command=f"rsync -aH --one-file-system {exclude_string} {image_path}/{grab} {node}:/"
                    else:
                        command=f"rsync -aHvn --one-file-system {exclude_string} {image_path}/{grab} {node}:/ >> /tmp/ospush.out"
                    self.logger.info(command)
                    message,exit_code = Helper().runcommand(command,True,3600)
                    self.logger.debug(f"exit_code = {exit_code}")
        else:
            if nodry is True: # nodry is True means it's for real
                command=f"rsync -aH --delete-after {exclude_string} {image_path}/* {node}:/"
            else:
                command=f"rsync -aHnv --delete-after {exclude_string} {image_path}/* {node}:/ &> /tmp/ospush.out"
            self.logger.info(command)
            message,exit_code = Helper().runcommand(command,True,3600)

        if exit_code != 0:
            if len(message) > 0:
                message=message[1]
            return False, f"{message}. See /tmp/ospush.out for details"

        return True, "Success. See /tmp/ospush.out for details"
