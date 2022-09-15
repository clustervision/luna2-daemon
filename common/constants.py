#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is responsible to fetch each variable configured in config/luna.conf.
Import this file will provide all variables which is fetched here.

"""


import os
import configparser
from pathlib import Path
CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)

############### LUNA CONFIGURATION FILE ###################
configParser = configparser.RawConfigParser()
configParser.read('config/luna.conf')

TOKEN = configParser.get("CONNECTION", "TOKEN")
SERVERIP = configParser.get("CONNECTION", "SERVERIP")
SERVERPORT = configParser.get("CONNECTION", "SERVERPORT")

LEVEL = configParser.get("LOGGER", "LEVEL")
LOGFILE = configParser.get("LOGGER", "LOGFILE")

############### LUNA CONFIGURATION FILE ###################