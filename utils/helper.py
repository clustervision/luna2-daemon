#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This Is a Helper Class, which help the project to provide the common tasks.

"""
 
import subprocess
from common.constants import *


class Helper(object):

    def __init__(self):
        pass


    def runcommand(command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output = process.communicate()
        process.wait()
        return output