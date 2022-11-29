#!/usr/bin/env python3
"""
This Is a Template Class.
It will help to validate the templates.
It will responsible to create the tmp dir for templates
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import json
import subprocess
from utils.log import *
from utils.helper import Helper


class Templates(object):


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
    def validate(self):
        if CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]:
            TEMPLDIRSTATE = Helper().checkpathstate(CONSTANT["TEMPLATES"]["TEMPLATES_DIR"])
            if TEMPLDIRSTATE:
                if CONSTANT["TEMPLATES"]["TEMPLATELIST"]:
                    tempdirstatus = Helper().checkpathstate(CONSTANT["TEMPLATES"]["TEMPLATELIST"])
                    if tempdirstatus:
                        file = open(CONSTANT["TEMPLATES"]["TEMPLATELIST"])
                        data = json.load(file)
                        file.close()
                        if data:
                            if 'files' in data.keys():
                                Helper().runcommand(f'rm -rf /var/tmp/luna2')
                                Helper().runcommand(f'mkdir /var/tmp/luna2')
                                for templatefiles in data['files']:
                                    templfilestatus = Helper().checkpathstate(CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]+'/'+templatefiles)
                                    if templfilestatus:
                                        Helper().runcommand(f'cp {CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} /var/tmp/luna2/')
                                    else:
                                        logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} is Not Present.')
                            else:
                                logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} Do Not have file list.')
                        else:
                            logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} Is Empty.')
                    else:
                        logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} is Not Present.')
                else:
                    logger.error(f'TEMPLATELIST Not Present in the INI File.')
            else:
                logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]} is Not Present.')
        else:
            logger.error(f'TEMPLATES_DIR Not Present in the INI File.')
        return True
