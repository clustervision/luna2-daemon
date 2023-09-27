
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Standard image clean up plugin
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
        one defined method is mandatory:
        - cleanup
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def cleanup(self, osimage=None, files_path=None, file_to_remove=None):
        # files_path = is the location where the imagefile will be copied.
        # file_to_remove is the file that needs to be removed
        message = 'No file found'
        if files_path and file_to_remove:
            command = f"cd {files_path} && rm -f {file_to_remove}"
            self.logger.info(f"I will run: {command}")
            message, exit_code = Helper().runcommand(command, True, 300)
            if exit_code == 0:
                return True, message
        return False, message

