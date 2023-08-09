#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the default OS Push plugin, which takes care of pushing an image to a node

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

import random
from time import sleep

class Plugin():
    """
    Class for grabbing a life filesystem
    """
    """
    This plugin class requires 1 mandatory method:
    -- grab
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
            exit_code=0
            for grab in grab_filesystems:
                if exit_code == 0:
                    if nodry is True: # nodry is True means it's for real
                        command=f"rsync -aH --one-file-system {exclude_string} {image_path}/{grab} {node}:/"
                    else:
                        command=f"rsync -aHvn --one-file-system {exclude_string} {image_path}/{grab} {node}:/ > /tmp/ospush.out"
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
            return False, f"{message}"

        # not entirely accurate but good enough
        kernel_version, stderr = Helper().runcommand(f"ls -tr {image_path}/lib/modules/|tail -n1")
        kernel_version=kernel_version.strip()
        kernel_version=kernel_version.decode('utf-8')
        self.logger.debug(f"{kernel_version} {stderr}")
        if kernel_version:
            return True, "Success", kernel_version
        return True, "Success"
