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
This Log Class is responsible to start the Logger depend on the Level.
Level Should be configured in config/luna.ini or by the argument --debug.
Default Loggin level is set to the INFO.
Method get_logger will provide a logging object, which is helpful to write the log messages.
Logger Object have basic mathods: debug, error, info, critical and warnings.

"""
__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import sys
import logging


class Log:
    """This Log Class is responsible to start the Logger depend on the Level."""
    __logger = None


    @classmethod
    def init_log(cls, log_level=None, logfile=None):
        """
        Input - log_level
        Process - Validate the Log Level, Set it to INFO if not correct.
        Output - Logger Object.
        """
        levels = {'NOTSET': 0, 'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
        log_level = levels[log_level.upper()]
        thread_level = '[%(levelname)s]:[%(asctime)s]:[%(threadName)s]:'
        message = '[%(filename)s:%(funcName)s@%(lineno)d] - %(message)s'
        log_format = f'{thread_level}{message}'
        logging.basicConfig(filename=logfile, format=log_format, filemode='a', level=log_level)
        urllib3 = logging.getLogger('urllib3')
        urllib3.setLevel(logging.CRITICAL)
        cls.__logger = logging.getLogger('luna2-daemon')
        cls.__logger.setLevel(log_level)
        formatter = logging.Formatter(log_format)
        cnsl = logging.StreamHandler(sys.stdout)
        cnsl.setLevel(log_level)
        cnsl.setFormatter(formatter)
        cls.__logger.addHandler(cnsl)
        #cnsl.propagate = False
        levels = {0: 'NOTSET', 10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR', 50: 'CRITICAL'}
        cls.__logger.info(f'######### Luna Logging Level IsSet To [{levels[log_level]}] #########')
        return cls.__logger


    @classmethod
    def get_logger(cls):
        """
        Input - None
        Output - Logger Object.
        """
        return cls.__logger

    @classmethod
    def set_logger(cls, log_level=None):
        """
        Input - None
        Process - Update the exsisting Log Level
        Output - Logger Object.
        """
        levels = {'NOTSET': 0, 'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
        log_level = levels[log_level.upper()]
        cls.__logger.setLevel(log_level)
        return cls.__logger

    @classmethod
    def check_loglevel(cls):
        """
        Input - None
        Process - Update the exsisting Log Level
        Output - Logger Object.
        """
        return logging.root.level
