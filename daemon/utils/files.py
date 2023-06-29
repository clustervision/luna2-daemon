#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Files Class is reponsible to validate the IMAGE_FILES directory and it's files.
It can provvide the list of file and a specific file.
It can only provide files ending with tar.gz and tar.bz2.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
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
        try:
            if os.path.exists(filepath):
                self.logger.debug(f'Filepath {filepath} is exists.')
                response = filepath
        except FileNotFoundError:
            self.logger.debug(f'Filepath {filepath} is not exists.')
            response = False
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
