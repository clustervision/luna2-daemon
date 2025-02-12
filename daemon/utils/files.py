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
Files Class is reponsible to validate the IMAGE_FILES directory and it's files.
It can provvide the list of file and a specific file.
It can only provide files ending with tar.gz and tar.bz2.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
from utils.log import Log
from common.constant import CONSTANT

class Files(object):
    """
    Files Class take care all Operations related to files.
    """

    def __init__(self):
        """
        Constructor - For Files Operations.
        """
        self.logger = Log.get_logger()


    def check_file(self, filename):
        """
        Input - filename
        Process - It will check if file is available or not
        Output - filepath
        """
        filepath = f'{CONSTANT["FILES"]["IMAGE_FILES"]}/{filename}'
        response = False
        if os.path.exists(filepath):
            self.logger.debug(f'Filepath {filepath} exists.')
            response = filepath
        else:
            self.logger.debug(f'Filepath {filepath} does not exist.')
        return response


    def list_files(self):
        """
        Input - None
        Process - It will collect *tar.gz and *tar.bz2 files from IMAGE_FILES directory
        Output - List Of Available Files.
        """
        files = []
        filepath = f'{CONSTANT["FILES"]["IMAGE_FILES"]}/'
        try:
            if os.path.exists(filepath):
                for file in os.listdir(filepath):
                    if file.endswith('.tar.gz') or file.endswith('.tar.bz2'):
                        files.append(file)
            response = files
        except FileNotFoundError:
            self.logger.debug(f'Filepath {filepath} is not exists.')
            response = None
        return response
