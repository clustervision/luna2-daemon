#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is responsible to Check & Perform all bootstrap related activity.

"""

from common.dbcheck import *

Bootstrap = False
BootStrapFile = "/trinity/local/luna/config/bootstrap.ini"
BootStrapFilePath = Path(BootStrapFile)


def bootstrap():
	Nodes = []
	configParser.read(BootStrapFile)
	if configParser.has_section("HOSTS"):
		if configParser.has_option("HOSTS", "CONTROLLER1"):
			CONTROLLER1 = configParser.get("HOSTS", "CONTROLLER1")
		else:
			logger.error("In HOSTS, CONTROLLER1 is Unavailable in {}.".format(BootStrapFile))
		if configParser.has_option("HOSTS", "CONTROLLER2"):
			CONTROLLER2 = configParser.get("HOSTS", "CONTROLLER2")
		else:
			logger.error("In HOSTS, CONTROLLER2 is Unavailable in {}.".format(BootStrapFile))
		if configParser.has_option("HOSTS", "NODELIST"):
			NODELIST = configParser.get("HOSTS", "NODELIST")
			if NODELIST:
				nodename = NODELIST.split("[",1)[0]
				nodecount = NODELIST.replace(nodename, "").replace("[", "").replace("]", "")
				nodecount = nodecount.split("-")
				length = nodecount[1].count('0')
				for x in range(int(nodecount[1])):
					Nodes.append(nodename+str(x+1).zfill(length+1))				
		else:
			logger.error("In HOSTS, NODELIST is Unavailable in {}.".format(BootStrapFile))
	else:
		logger.error("Section Name HOSTS is Unavailable in {}.".format(BootStrapFile))

	if configParser.has_section("NETWORKS"):
		if configParser.has_option("NETWORKS", "INTERNAL"):
			INTERNAL = configParser.get("NETWORKS", "INTERNAL")
		else:
			logger.error("In NETWORKS, INTERNAL is Unavailable in {}.".format(BootStrapFile))
		if configParser.has_option("NETWORKS", "BMC"):
			BMC = configParser.get("NETWORKS", "BMC")
		else:
			logger.error("In NETWORKS, BMC is Unavailable in {}.".format(BootStrapFile))
		if configParser.has_option("NETWORKS", "IB"):
			IB = configParser.get("NETWORKS", "IB")			
		else:
			logger.error("In NETWORKS, IB is Unavailable in {}.".format(BootStrapFile))
	else:
		logger.error("Section Name NETWORKS is Unavailable in {}.".format(BootStrapFile))

	if configParser.has_section("GROUPS"):
		if configParser.has_option("GROUPS", "NAME"):
			GROUPNAME = configParser.get("GROUPS", "NAME")
		else:
			logger.error("In GROUPS, NAME is Unavailable in {}.".format(BootStrapFile))
	else:
		logger.error("Section Name GROUPS is Unavailable in {}.".format(BootStrapFile))

	if configParser.has_section("OSIMAGE"):
		if configParser.has_option("OSIMAGE", "NAME"):
			OSIMAGENAME = configParser.get("OSIMAGE", "NAME")
		else:
			logger.error("In OSIMAGE, NAME is Unavailable in {}.".format(BootStrapFile))
	else:
		logger.error("Section Name OSIMAGE is Unavailable in {}.".format(BootStrapFile))


	if configParser.has_section("BMCSETUP"):
		if configParser.has_option("BMCSETUP", "USERNAME"):
			BMCUSERNAME = configParser.get("BMCSETUP", "USERNAME")
		else:
			logger.error("In BMCSETUP, USERNAME is Unavailable in {}.".format(BootStrapFile))
		if configParser.has_option("BMCSETUP", "PASSWORD"):
			BMCPASSWORD = configParser.get("BMCSETUP", "PASSWORD")
		else:
			logger.error("In BMCSETUP, PASSWORD is Unavailable in {}.".format(BootStrapFile))
	else:
		logger.error("Section Name BMCSETUP is Unavailable in {}.".format(BootStrapFile))

	print(Nodes)




if BootStrapFilePath.is_file():
	logger.info("Bootstrp file is present {}.".format(BootStrapFile))
	if os.access(BootStrapFile, os.R_OK):
		logger.info("Bootstrp file is readable {}.".format(BootStrapFile))
		checkdb, code = checkdbstatus()
		if checkdb["read"] == True and checkdb["write"] == True:
			logger.info("Database {} READ WRITE Check TRUE.".format(checkdb["database"]))
			table = ["cluster", "bmcsetup", "group", "groupinterface", "groupsecrets", "network", "osimage", "switch", "tracker", "node", "nodeinterface", "nodesecrets"]
			num = 0
			for x in table:
				result = Database().get_record(None, x, None)
				if result is None:
					sys.exit(0)
				if result:
					num = num+1
			num = 0 ##############>>>>>>>>>>>>>>>>>>>..... REMOVE THIS LINE AFTER DEVELOPMENT
			if num == 0:
				logger.info("Database {} Is Empty and Daemon Ready for BootStrapping.".format(checkdb["database"]))
				bootstrap()
			else:
				logger.info("Database {} Already Filled with Data.".format(checkdb["database"]))
		else:
			logger.error("Database {} READ {} WRITE {} Check TRUE file is not readable {}.".format(checkdb["database"], checkdb["read"], checkdb["write"]))

	else:
		logger.error("Bootstrp file is not readable {}.".format(BootStrapFile))
else:
	logger.error("Bootstrp file is abesnt {}.".format(BootStrapFile))


sys.exit(0)