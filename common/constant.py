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
import sys
# import socket
import ipaddress
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

ConfigFile = "/trinity/local/luna/config/luna.ini"


"""
Input - Message and Default File True or False  
Output - Print Message; If Error from Default, then Stop the Code.
"""
def ini_error(message, default):
	print(message)
	if default:
		sys.exit(0)

"""
Input - Section And Option From INI File  
Output - Set the Global Variable
"""
def set_variable(section, option):
	globals()[option] = configParser.get(section, option)


"""
Input - Filename and Default File True or False
Output - Retrive Configuration
"""
def getconfig(filename=None, default=None):
	configParser.read(filename)
	if configParser.has_section("CONNECTION"):
		if configParser.has_option("CONNECTION", "SERVERIP"):
			set_variable("CONNECTION", "SERVERIP")
		else:
			message = "ERROR :: In CONNECTION, SERVERIP is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("CONNECTION", "SERVERPORT"):
			set_variable("CONNECTION", "SERVERPORT")
		else:
			message = "ERROR :: In CONNECTION, SERVERPORT is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name CONNECTION is Unavailable in {}.".format(filename)
		ini_error(message, default)


	if configParser.has_section("LOGGER"):
		if configParser.has_option("LOGGER", "LEVEL"):
			set_variable("LOGGER", "LEVEL")
		else:
			message = "ERROR :: In LOGGER, LEVEL is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("LOGGER", "LOGFILE"):
			set_variable("LOGGER", "LOGFILE")
		else:
			message = "ERROR :: In LOGGER, LOGFILE is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name LOGGER is Unavailable in {}.".format(filename)
		ini_error(message, default)


	if configParser.has_section("API"):
		if configParser.has_option("API", "USERNAME"):
			set_variable("API", "USERNAME")
		else:
			message = "ERROR :: In API, USERNAME is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("API", "PASSWORD"):
			set_variable("API", "PASSWORD")
		else:
			message = "ERROR :: In API, PASSWORD is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("API", "EXPIRY"):
			set_variable("API", "EXPIRY")
		else:
			message = "ERROR :: In API, EXPIRY is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name API is Unavailable in {}.".format(filename)
		ini_error(message, default)

	if configParser.has_section("FILES"):
		if configParser.has_option("FILES", "TARBALL"):
			set_variable("FILES", "TARBALL")
		else:
			message = "ERROR :: In FILES, TARBALL is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name FILES is Unavailable in {}.".format(filename)
		ini_error(message, default)

	if configParser.has_section("DATABASE"):
		if configParser.has_option("DATABASE", "DRIVER"):
			set_variable("DATABASE", "DRIVER")
		else:
			message = "ERROR :: In DATABASE, DRIVER is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("DATABASE", "DATABASE"):
			set_variable("DATABASE", "DATABASE")
		else:
			message = "ERROR :: In DATABASE, DATABASE is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("DATABASE", "DBUSER"):
			set_variable("DATABASE", "DBUSER")
		else:
			message = "ERROR :: In DATABASE, DBUSER is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("DATABASE", "DBPASSWORD"):
			set_variable("DATABASE", "DBPASSWORD")
		else:
			message = "ERROR :: In DATABASE, DBPASSWORD is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("DATABASE", "HOST"):
			set_variable("DATABASE", "HOST")
		else:
			message = "ERROR :: In DATABASE, HOST is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("DATABASE", "PORT"):
			set_variable("DATABASE", "PORT")
		else:
			message = "ERROR :: In DATABASE, PORT is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name DATABASE is Unavailable in {}.".format(filename)
		ini_error(message, default)

	if configParser.has_section("SERVICES"):
		if configParser.has_option("SERVICES", "DHCP"):
			set_variable("SERVICES", "DHCP")
		else:
			message = "ERROR :: In SERVICES, DHCP is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("SERVICES", "DNS"):
			set_variable("SERVICES", "DNS")
		else:
			message = "ERROR :: In SERVICES, DNS is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("SERVICES", "CONTROL"):
			set_variable("SERVICES", "CONTROL")
		else:
			message = "ERROR :: In SERVICES, CONTROL is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("SERVICES", "COOLDOWN"):
			set_variable("SERVICES", "COOLDOWN")
		else:
			message = "ERROR :: In SERVICES, COOLDOWN is Unavailable in {}.".format(filename)
			ini_error(message, default)
		if configParser.has_option("SERVICES", "COMMAND"):
			set_variable("SERVICES", "COMMAND")
		else:
			message = "ERROR :: In SERVICES, COMMAND is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name SERVICES is Unavailable in {}.".format(filename)
		ini_error(message, default)

	if configParser.has_section("TEMPLATES"):
		if configParser.has_option("TEMPLATES", "TEMPLATES_DIR"):
			set_variable("TEMPLATES", "TEMPLATES_DIR")
		else:
			message = "ERROR :: In TEMPLATES, TEMPLATES_DIR is Unavailable in {}.".format(filename)
			ini_error(message, default)
	else:
		message = "ERROR :: Section Name TEMPLATES is Unavailable in {}.".format(filename)
		ini_error(message, default)


"""
Input - Filename
Output - Check File Existence And Readability
"""
def checkfile(filename=None):
	ConfigFilePath = Path(filename)
	if ConfigFilePath.is_file():
		if os.access(filename, os.R_OK):
			return True
		else:
			print("File {} Is Not readable.".format(filename))
	else:
		print("File {} Is Abesnt.".format(filename))
	return False

"""
Input - Directory
Output - Directory Existence, Readability and Writable
"""
def checkdir(directory=None):
	if os.path.exists(directory):
		if os.access(directory, os.R_OK):
			if os.access(directory, os.W_OK):
				return True
			else:
				print("Directory {} Is Writable.".format(directory))
		else:
			print("Directory {} Is Not readable.".format(directory))
	else:
	    print("Directory {} Is Not exists.".format(directory))
	return False


"""
Input - Filename and Default File True or False
Output - Check If File Writable
"""
def checkwritable(filename=None):
	write = False
	try:
	    file = open(filename, "a")
	    if file.writable():
	        write = True
	except Exception as e:
	    print("File {} is Not Writable.".format(filename))
	return write

"""
Calling Methods with INI File and Default Option.
"""
file_check = checkfile(ConfigFile)
if file_check:
	getconfig(ConfigFile, True)
else:
	sys.exit(0)
if override:
	file_check_override = checkfile(override)
	if file_check_override:
		getconfig(override, False)


"""
Post Retrieval Calculation
"""
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


"""
Sanity Checks On SERVERIP, SERVERPORT, LOGFILE, TARBALL, TEMPLATES_DIR
"""

def check_ip(ipaddr):
	try:
	    ip = ipaddress.ip_address(ipaddr)
	except Exception as e:
	    print("Invalid IP Address: {} ".format(ipaddr))
	    sys.exit(0)
check_ip(SERVERIP)


def check_port(ipaddr, port):
	if int(port) < 0 or int(port) > 65535:
		return True
    # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # 	return s.connect_ex((ipaddr, int(port))) == 0

port_check = check_port(SERVERIP, SERVERPORT)
if port_check:
	print("Port: {} Is In Use, Kindly Free This Port OR Use Other Port.".format(SERVERPORT))
	sys.exit(0)

check_log_read = checkfile(LOGFILE)
if check_log_read is not True:
	print("Log File: {} Is Not Readable.".format(LOGFILE))
	sys.exit(0)

check_log_write = checkwritable(LOGFILE)
if check_log_write is not True:
	print("Log File: {} Is Not Writable.".format(LOGFILE))
	sys.exit(0)

check_dir_read = checkdir(TARBALL)
if check_dir_read is not True:
	print("TARBALL Directory: {} Is Not Readable.".format(TARBALL))
	sys.exit(0)

check_dir_write = checkdir(TARBALL)
if check_dir_write is not True:
	print("TARBALL Directory: {} Is Not Writable.".format(TARBALL))
	sys.exit(0)

check_dir_read = checkdir(TEMPLATES_DIR)
if check_dir_read is not True:
	print("TEMPLATES_DIR Directory: {} Is Not Readable.".format(TEMPLATES_DIR))
	sys.exit(0)

check_dir_write = checkdir(TEMPLATES_DIR)
if check_dir_write is not True:
	print("TEMPLATES_DIR Directory: {} Is Not Writable.".format(TEMPLATES_DIR))
	sys.exit(0)

check_boot_ipxe_read = checkfile(TEMPLATES_DIR+"/boot_ipxe.cfg")
if check_boot_ipxe_read is not True:
    print("Boot PXE File: {} Is Not Readable.".format(TEMPLATES_DIR+"/boot_ipxe.cfg"))
    sys.exit(0)

check_boot_ipxe_write = checkwritable(TEMPLATES_DIR+"/boot_ipxe.cfg")
if check_boot_ipxe_write is not True:
    print("Boot PXE File: {} Is Not Writable.".format(TEMPLATES_DIR+"/boot_ipxe.cfg"))
    sys.exit(0)

if check_boot_ipxe_read and check_boot_ipxe_write:
	with open(TEMPLATES_DIR+"/boot_ipxe.cfg", "r") as bootfile:
		bootfile = bootfile.readlines()
	# print(bootfile)
	
######################## SET CRON JOB TO MONITOR ###########################
# cronfile = "/etc/cron.d/luna2-daemon.monitor"
# crondata = "0 * * * * root curl http://127.0.0.1:7050/monitor/service/luna2"
# with open(cronfile, "w") as file:
#     file.write(crondata)
######################## SET CRON JOB TO MONITOR ###########################