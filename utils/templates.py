#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


import json
from utils.log import Log
from utils.helper import Helper
from common.constant import CONSTANT

class Templates(object):
    """
    This class will handle all the operations related to templates.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()


    def validate(self):
        """
        Input - command, which need to be executed
        Process - Via subprocess, execute the command and wait to receive the complete output.
        Output - Detailed result.
        """
        if CONSTANT['TEMPLATES']['TEMPLATES_DIR']:
            templatedir = Helper().checkpathstate(CONSTANT['TEMPLATES']['TEMPLATES_DIR'])
            if templatedir:
                if CONSTANT['TEMPLATES']['TEMPLATELIST']:
                    tempdirstatus = Helper().checkpathstate(CONSTANT['TEMPLATES']['TEMPLATELIST'])
                    if tempdirstatus:
                        file = open(CONSTANT['TEMPLATES']['TEMPLATELIST'], encoding='utf-8')
                        data = json.load(file)
                        file.close()
                        if data:
                            if 'files' in data.keys():
                                Helper().runcommand('rm -rf /var/tmp/luna2')
                                Helper().runcommand('mkdir /var/tmp/luna2')
                                for templatefiles in data['files']:
                                    templfilestatus = Helper().checkpathstate(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles}')
                                    if templfilestatus:
                                        Helper().runcommand(f'cp {CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} /var/tmp/luna2/')
                                    else:
                                        self.logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} is Not Present.')
                            else:
                                self.logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} Do Not have file list.')
                        else:
                            self.logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} Is Empty.')
                    else:
                        self.logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATELIST"]} is Not Present.')
                else:
                    self.logger.error('TEMPLATELIST Not Present in the INI File.')
            else:
                self.logger.error(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]} is Not Present.')
        else:
            self.logger.error('TEMPLATES_DIR Not Present in the INI File.')
        return True
