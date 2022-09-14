#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""
Luna Logger

"""
import sys
import logging
from common.constants import *

class Log:
    __logger = None

    @classmethod
    def init_log(cls, log_level):
        if not log_level:
            log_level = 0
        else:
            levels = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            log_level = levels[log_level.upper()]
        logging.basicConfig(filename=BASE_DIR+"/"+LOGFILE, format='[%(levelname)s]:[%(asctime)s]:[%(threadName)s]:[%(filename)s:%(funcName)s@%(lineno)d] - %(message)s', filemode='a', level=log_level)
        # logging.basicConfig(filename=BASE_DIR+"/"+LOGFILE, format='%(asctime)s %(levelname)s: %(message)s', filemode='a', level=logging.DEBUG)
        cls.__logger = logging.getLogger("luna2-daemon")
        cls.__logger.setLevel(log_level)
        formatter = logging.Formatter('[%(levelname)s]:[%(asctime)s]:[%(threadName)s]:[%(filename)s:%(funcName)s@%(lineno)d] - %(message)s')
        # formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        cnsl = logging.StreamHandler(sys.stdout)
        cnsl.setLevel(log_level)
        cnsl.setFormatter(formatter)
        cls.__logger.addHandler(cnsl)
        levels = {0: "NOTSET", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        cls.__logger.info('=============== Luna Logging Level IsSet To [{}] ==============='.format(levels[log_level]))
        return cls.__logger

    @classmethod
    def get_logger(cls):
        return cls.__logger

    # @classmethod
    # def luna_logging(cls, message, log_level):
    #     match log_level:
    #         case "debug" | 10:
    #             return cls.__logger.debug(message)
    #         case "info" | 20:
    #             return cls.__logger.info(message)
    #         case "warning" | 30:
    #             return cls.__logger.warning(message)
    #         case "error" | 40:
    #             return cls.__logger.error(message)
    #         case "critical" | 50:
    #             return cls.__logger.critical(message)
    #         case _:
    #             return cls.__logger.critical("Log Level isn't set, Kinldy choose debug or info or warning or error or critical")