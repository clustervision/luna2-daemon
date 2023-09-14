
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Default OS Image Filesystem related Plugin.
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
        three defined methods are mandatory:
        - copy   
        - cleanup
        - getpath
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

        # osimage = just the name of the image
        # image_path = is the location where the image resides
        # files_path = is the location where the imagefile will be copied.
        # packed_image_file = the name of the actual imagefile
        # kernel_modules = list of drivers to be included/excluded
        # ramdisk_modules = list of ramdisk modules to be included/excluded

    # ---------------------------------------------------------------------------

    def cleanup(self, osimage=None, files_path=None, current_packed_image_files=[], current_kernel_files=[], current_ramdisk_files=[]):
        # files_path = is the location where the imagefile will be copied.
        # current_packed_image_file is the currently used packed image
        # same goes for kernel + ramdisk file
        message = ''
        if current_packed_image_files:
            grep = '|'.join(current_packed_image_files)
            command = f"cd {files_path} && ls {osimage}-*.tar.bz2 | grep -vwE \"{grep}\" | xargs rm -f"
            self.logger.info(f"I will run: {command}")
            message, exit_code = Helper().runcommand(command, True, 300)
            if exit_code == 0:
                grep = '|'.join(current_kernel_files)
                command = f"cd {files_path} && ls {osimage}-*-vmlinuz* | grep -vwE \"{grep}\" | xargs rm -f"
                self.logger.info(f"I will run: {command}")
                message, exit_code = Helper().runcommand(command, True, 300)
                if exit_code == 0:
                    grep = '|'.join(current_ramdisk_files)
                    command = f"cd {files_path} && ls {osimage}-*-initramfs* | grep -vwE \"{grep}\" | xargs rm -f"
                    self.logger.info(f"I will run: {command}")
                    message, exit_code = Helper().runcommand(command, True, 300)
            if exit_code == 0:
                return True, message
        return False, message

    # ---------------------------------------------------------------------------

    def clone(self,source,destination):
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


