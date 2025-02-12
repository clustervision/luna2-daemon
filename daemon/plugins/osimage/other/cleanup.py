
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
Plugin Class ::  Standard image clean up plugin
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

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

    def cleanup(self, files_path=None, file_to_remove=None):
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
