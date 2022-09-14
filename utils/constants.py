#!/usr/bin/env python3

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