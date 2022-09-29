#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
Files Class is reponsible to validate the TARBALL directory and it's files.
It can provvide the list of file and a specific file.
It can only provide files ending with tar.gz and tar.bz2

"""

import os
from common.constants import *
from utils.log import *
logger = Log.get_logger()


class Files(object):

    def __init__(self):
        pass

    """
    Input - filename
    Process - It will check if file is available or not 
    Output - filepath
    """
    def check_file(self, filename):
        filepath = TARBALL+"/"+filename
        if os.path.exists(filepath):
            logger.debug("File Path {} Is exists.".format(filepath))
            return filepath
        else:
            logger.debug("File Path {} Is Not exists.".format(filepath))
            return False


    """
    Input - None
    Process - It will collect *tar.gz and *tar.bz2 files from TARBALL directory
    Output - List Of Available Files
    """
    def list_files(self):
        files = []
        filepath = TARBALL+"/"
        if os.path.exists(filepath):
            for file in os.listdir(filepath):
                if file.endswith(".tar.gz") or file.endswith(".tar.bz2"):
                    files.append(file)
        return files