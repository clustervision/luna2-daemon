#!/usr/bin/env python3

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

"""
This Is a Helper Class, which help the project to provide the common Methods.

"""
import subprocess
from utils.log import *


class Helper(object):


    """
    Constructor - As of now, nothing have to initialize.
    """
    def __init__(self):
        self.logger = Log.get_logger()


    """
    Input - command, which need to be executed
    Process - Via subprocess, execute the command and wait to receive the complete output.
    Output - Detailed result.
    """
    def runcommand(self, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.logger.debug("Command Executed {}".format(command))
        output = process.communicate()
        process.wait()
        self.logger.debug("Output Of Command {} ".format(str(output)))
        return output