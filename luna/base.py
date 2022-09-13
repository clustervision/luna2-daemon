#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""

"""

import sys
import os
import configparser
from pathlib import Path
import logging
from dotenv import load_dotenv
from argparse import ArgumentParser

from luna.service import *
from webserver import *

CurrentDir = os.path.dirname(os.path.realpath(__file__))
path = Path(CurrentDir)
base_dir = str(path.parent)

load_dotenv(base_dir+'/config/.env', override=False)
CONFIGFILE = os.getenv('CONFIGFILE')

configParser = configparser.RawConfigParser()
configParser.read(base_dir+'/config/config.ini')


try:
    SERVICES = configParser.get("SERVICES", "service")
    log_level = configParser.get("LOGGER", "level")
except Exception as e:
    SERVICES = ""
    log_level = ""
    print("No Services are defined to Use. Kindly define the services to use.")


class Base(object):

    def __init__(self):
        pass

    def main(self):
        self.CONFIGFILE = CONFIGFILE
        self.SERVICES = SERVICES
        self.base_dir = base_dir
        parser = ArgumentParser(prog='luna2-daemon', description='Manage Luna Cluster')
        parser.add_argument('--debug', '-d', action='store_true', help='Show debug information')
        subparsers = parser.add_subparsers(dest="command", help='See Details by --help')
        Serviceparser = Service.getarguments(self, parser, subparsers)

        self.args = vars(parser.parse_args())
        
        self.set_loglevel()
        self.callclass()
        return True
        

    def callclass(self):
        if self.args:
            if self.args["command"] == "service":
                Service(self)

        else:
            self.logger.warning("Please pass -h to see help menu.")


    def set_loglevel(self):
        if self.args:
            if self.args["debug"]:
                self.log_level = logging.DEBUG
            else:
                self.log_level = log_level
                match log_level:
                    case "debug":
                        self.log_level = logging.DEBUG
                    case "info":
                        self.log_level = logging.INFO
                    case "warning":
                        self.log_level = logging.WARNING
                    case "error":
                        self.log_level = logging.ERROR
                    case "critical":
                        self.log_level = logging.CRITICAL
                    case _:
                        self.log_level = logging.NOTSET
        logging.basicConfig(filename=self.base_dir+"/log/luna2-daemon.log", format='%(asctime)s %(levelname)s: %(message)s', filemode='a', level=self.log_level)
        self.logger = logging.getLogger("luna2-daemon")
        self.logger.setLevel(self.log_level)

        self.formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        self.cnsl = logging.StreamHandler(sys.stdout)
        self.cnsl.setLevel(self.log_level)
        self.cnsl.setFormatter(self.formatter)
        self.logger.addHandler(self.cnsl)
        levels = {0: "NOTSET", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        self.logger.info('=============== Logger Level Set To [{}]==============='.format(levels[self.log_level]))
        return self.logger

        