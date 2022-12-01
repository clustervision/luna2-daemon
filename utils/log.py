#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Log Class is responsible to start the Logger depend on the Level.
Level Should be configured in config/luna.ini or by the argument --debug.
Default Loggin level is set to the INFO.
Method get_logger will provide a logging object, which is helpful to write the log messages.
Logger Object have basic mathods: debug, error, info, critical and warnings.

"""
__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import sys
import logging
from common.constant import CONSTANT, BASE_DIR

class Log:
    """This Log Class is responsible to start the Logger depend on the Level."""
    __logger = None



    @classmethod
    def init_log(cls, log_level):
        """
        Input - log_level
        Process - Validate the Log Level, Set it to INFO if not correct.
        Output - Logger Object.
        """
        if not log_level:
            log_level = 20
        else:
            levels = {'NOTSET': 0, 'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
            log_level = levels[log_level.upper()]
        logging.basicConfig(filename=BASE_DIR+"/"+CONSTANT['LOGGER']['LOGFILE'], format='[%(levelname)s]:[%(asctime)s]:[%(threadName)s]:[%(filename)s:%(funcName)s@%(lineno)d] - %(message)s', filemode='a', level=log_level)
        cls.__logger = logging.getLogger('luna2-daemon')
        cls.__logger.setLevel(log_level)
        formatter = logging.Formatter('[%(levelname)s]:[%(asctime)s]:[%(threadName)s]:[%(filename)s:%(funcName)s@%(lineno)d] - %(message)s')
        cnsl = logging.StreamHandler(sys.stdout)
        cnsl.setLevel(log_level)
        cnsl.setFormatter(formatter)
        cls.__logger.addHandler(cnsl)
        levels = {0: 'NOTSET', 10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR', 50: 'CRITICAL'}
        cls.__logger.info(f'########## Luna Logging Level IsSet To [{levels[log_level]}] ##########')
        return cls.__logger


    @classmethod
    def get_logger(cls):
        """
        Input - None
        Output - Logger Object.
        """
        return cls.__logger
