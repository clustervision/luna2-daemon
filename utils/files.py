#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""

"""
import os
from pathlib import Path
from utils.constants import *

class Files(object):

    def __init__(self):
        pass


    def check_file(self, filename):
        filepath = BASE_DIR+"/files/"+filename
        if os.path.exists(filepath):
            return filepath
        else:
            return False


    def list_files(self):
        files = []
        filepath = BASE_DIR+"/files/"
        if os.path.exists(filepath):
            for file in os.listdir(filepath):
                if file.endswith(".tar.gz") or file.endswith(".tar.bz2"):
                    files.append(file)
        return files

