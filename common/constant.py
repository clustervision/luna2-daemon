#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is responsible to fetch each variable configured in config/luna.ini.
Import this file will provide all variables which is fetched here.

"""

import os
import argparse
import configparser
from pathlib import Path

parser = argparse.ArgumentParser(prog='luna2-daemon', description='Manage Luna2 Daemon')
parser.add_argument("-d", "--debug", action="store_true", help='Run Application on Debug Mode.')
parser.add_argument("-i", "--ini", default="/trinity/local/luna/config/luna.ini", help='Overright the Default Configuration.')
args = vars(parser.parse_args())
override = None
if args["ini"]:
    override = args["ini"]


CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
SECRET_KEY = '004f2af45d3a4e161a7dd2d17fdae47f'
configParser = configparser.RawConfigParser()


############### LUNA CONFIGURATION FILE ###################

configParser.read('config/luna.ini')
if configParser.has_section("CONNECTION"):
	if configParser.has_option("CONNECTION", "SERVERIP"):
		SERVERIP = configParser.get("CONNECTION", "SERVERIP")
	if configParser.has_option("CONNECTION", "SERVERPORT"):
		SERVERPORT = configParser.get("CONNECTION", "SERVERPORT")

if configParser.has_section("LOGGER"):
	if configParser.has_option("LOGGER", "LEVEL"):
		LEVEL = configParser.get("LOGGER", "LEVEL")
	if configParser.has_option("LOGGER", "LOGFILE"):
		LOGFILE = configParser.get("LOGGER", "LOGFILE")

if configParser.has_section("API"):
	if configParser.has_option("API", "USERNAME"):
		USERNAME = configParser.get("API", "USERNAME")
	if configParser.has_option("API", "PASSWORD"):
		PASSWORD = configParser.get("API", "PASSWORD")
	if configParser.has_option("API", "EXPIRY"):
		EXPIRY = configParser.get("API", "EXPIRY")

if configParser.has_section("FILES"):
	if configParser.has_option("FILES", "TARBALL"):
		TARBALL = configParser.get("FILES", "TARBALL")

if configParser.has_section("DATABASE"):
	if configParser.has_option("DATABASE", "DRIVER"):
		DRIVER = configParser.get("DATABASE", "DRIVER")
	if configParser.has_option("DATABASE", "DATABASE"):
		DATABASE = configParser.get("DATABASE", "DATABASE")
	if configParser.has_option("DATABASE", "DBUSER"):
		DBUSER = configParser.get("DATABASE", "DBUSER")
	if configParser.has_option("DATABASE", "DBPASSWORD"):
		DBPASSWORD = configParser.get("DATABASE", "DBPASSWORD")
	if configParser.has_option("DATABASE", "HOST"):
		HOST = configParser.get("DATABASE", "HOST")
	if configParser.has_option("DATABASE", "PORT"):
		PORT = configParser.get("DATABASE", "PORT")

if configParser.has_section("LOGGER"):
	if configParser.has_option("LOGGER", "LEVEL"):
		LEVEL = configParser.get("LOGGER", "LEVEL")
	if configParser.has_option("LOGGER", "LOGFILE"):
		LOGFILE = configParser.get("LOGGER", "LOGFILE")

if configParser.has_section("SERVICES"):
	if configParser.has_option("SERVICES", "DHCP"):
		DHCP = configParser.get("SERVICES", "DHCP")
	if configParser.has_option("SERVICES", "DNS"):
		DNS = configParser.get("SERVICES", "DNS")
	if configParser.has_option("SERVICES", "CONTROL"):
		CONTROL = configParser.get("SERVICES", "CONTROL")
	if configParser.has_option("SERVICES", "COOLDOWN"):
		COOLDOWN = configParser.get("SERVICES", "COOLDOWN")
	if configParser.has_option("SERVICES", "COMMAND"):
		COMMAND = configParser.get("SERVICES", "COMMAND")

############### LUNA CONFIGURATION FILE ###################


############### LUNA OVERRIDE CONFIGURATION FILE ###################
if override:
	configParser.read(override)
	if configParser.has_section("CONNECTION"):
		if configParser.has_option("CONNECTION", "SERVERIP"):
			SERVERIP = configParser.get("CONNECTION", "SERVERIP")
		if configParser.has_option("CONNECTION", "SERVERPORT"):
			SERVERPORT = configParser.get("CONNECTION", "SERVERPORT")

	if configParser.has_section("LOGGER"):
		if configParser.has_option("LOGGER", "LEVEL"):
			LEVEL = configParser.get("LOGGER", "LEVEL")
		if configParser.has_option("LOGGER", "LOGFILE"):
			LOGFILE = configParser.get("LOGGER", "LOGFILE")

	if configParser.has_section("API"):
		if configParser.has_option("API", "USERNAME"):
			USERNAME = configParser.get("API", "USERNAME")
		if configParser.has_option("API", "PASSWORD"):
			PASSWORD = configParser.get("API", "PASSWORD")
		if configParser.has_option("API", "EXPIRY"):
			EXPIRY = configParser.get("API", "EXPIRY")

	if configParser.has_section("FILES"):
		if configParser.has_option("FILES", "TARBALL"):
			TARBALL = configParser.get("FILES", "TARBALL")

	if configParser.has_section("DATABASE"):
		if configParser.has_option("DATABASE", "DRIVER"):
			DRIVER = configParser.get("DATABASE", "DRIVER")
		if configParser.has_option("DATABASE", "DATABASE"):
			DATABASE = configParser.get("DATABASE", "DATABASE")
		if configParser.has_option("DATABASE", "DBUSER"):
			DBUSER = configParser.get("DATABASE", "DBUSER")
		if configParser.has_option("DATABASE", "DBPASSWORD"):
			DBPASSWORD = configParser.get("DATABASE", "DBPASSWORD")
		if configParser.has_option("DATABASE", "HOST"):
			HOST = configParser.get("DATABASE", "HOST")
		if configParser.has_option("DATABASE", "PORT"):
			PORT = configParser.get("DATABASE", "PORT")

	if configParser.has_section("LOGGER"):
		if configParser.has_option("LOGGER", "LEVEL"):
			LEVEL = configParser.get("LOGGER", "LEVEL")
		if configParser.has_option("LOGGER", "LOGFILE"):
			LOGFILE = configParser.get("LOGGER", "LOGFILE")

	if configParser.has_section("SERVICES"):
		if configParser.has_option("SERVICES", "DHCP"):
			DHCP = configParser.get("SERVICES", "DHCP")
		if configParser.has_option("SERVICES", "DNS"):
			DNS = configParser.get("SERVICES", "DNS")
		if configParser.has_option("SERVICES", "CONTROL"):
			CONTROL = configParser.get("SERVICES", "CONTROL")
		if configParser.has_option("SERVICES", "COOLDOWN"):
			COOLDOWN = configParser.get("SERVICES", "COOLDOWN")
		if configParser.has_option("SERVICES", "COMMAND"):
			COMMAND = configParser.get("SERVICES", "COMMAND")

############### LUNA OVERRIDE CONFIGURATION FILE ###################


######################## POST CALCULATION ###########################

if EXPIRY:
	EXPIRY = int(EXPIRY.replace("h", ""))
	EXPIRY = EXPIRY*60*60
else:
	EXPIRY = 24*60*60

if COOLDOWN:
	COOLDOWN = int(COOLDOWN.replace("s", ""))
else:
	COOLDOWN = 2

if args["debug"]:
    LEVEL = "debug"

######################## POST CALCULATION ###########################


######################## SET CRON JOB TO MONITOR ###########################
# cronfile = "/etc/cron.d/luna2-daemon.monitor"
# crondata = "0 * * * * root curl http://127.0.0.1:7050/monitor/service/luna2"
# with open(cronfile, "w") as file:
#     file.write(crondata)
######################## SET CRON JOB TO MONITOR ###########################