#!/usr/bin/env python3
"""
This File is a A Entry Point to Monitor the services.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


import os
import sys
from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *
from utils.service import *
from utils.database import *

logger = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)


"""
Input - name of service
Process - With the help of Serive Class, we can get the exact status of the service. which is DHCP, DNS and luna2
Output - Status.
"""
@monitor_blueprint.route("/monitor/service/<string:name>", methods=['GET'])
def monitor_service(name=None):
    if name == "luna2":
        response, code = checkdbstatus()
        logger.info("Database Status is: {}.".format(str(response)))
    action = "status"
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Validate if the Node is Exists and UP
Output - Status.
"""
@monitor_blueprint.route("/monitor/status/<string:node>", methods=['GET'])
def monitor_status_get(node=None):
    NODE = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
    if not NODE:
        logger.info(f'Node {node} is Down And Not Running')
        response = {"monitor": {"status": { node: { "status": "Luna installer: Errors", "state": "installer.fail"} } } }
        code = 500
    else:
        logger.info("Node {} is UP And Running".format(node))
        # response = {"monitor": {"status": { node: { "status": NODE[0]['status'], "state": NODE[0]['state']} } } }
        response = {"monitor": {"status": { node: { "status": "Luna installer: No errors", "state": "installer.ok"} } } }
        code = 200
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Update the Node Status
Output - Status.
"""
@monitor_blueprint.route("/monitor/status/<string:node>", methods=['POST'])
def monitor_status_post(node=None):
    NODE = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
    if not NODE:
        logger.info(f'Node {node} is Down And Not Running')
        response = {"monitor": {"status": { node: { "status": "Luna installer: Errors", "state": "installer.fail"} } } }
        code = 500
    else:
        logger.info("Node {} is UP And Running".format(node))
        # response = {"monitor": {"status": { node: { "status": NODE[0]['status'], "state": NODE[0]['state']} } } }
        response = {"monitor": {"status": { node: { "status": "Luna installer: No errors", "state": "installer.ok"} } } }
        code = 200
    return json.dumps(response), code


"""
Input - None
Process - Check the Current Database condition.
Output - Status of Read & Write.
"""
def checkdbstatus():
    sqlite, read, write = False, False, False
    code = 503
    if os.path.isfile(CONSTANT['DATABASE']['DATABASE']):
        sqlite = True
        if os.access(CONSTANT['DATABASE']['DATABASE'], os.R_OK):
            read = True
            code = 500
            try:
                file = open(CONSTANT['DATABASE']['DATABASE'], "a")
                if file.writable():
                    write = True
                    code = 200
                    file.close()
            except Exception as e:
                logger.error("DATABASE {} is Not Writable.".format(CONSTANT['DATABASE']['DATABASE']))

            with open(CONSTANT['DATABASE']['DATABASE'],'r', encoding = "ISO-8859-1") as f:
                header = f.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                else:
                    read, write = False, False
                    code = 503
                    logger.error("DATABASE {} is Not a SQLite3 Database.".format(CONSTANT['DATABASE']['DATABASE']))
        else:
            logger.error("DATABASE {} is Not Readable.".format(CONSTANT['DATABASE']['DATABASE']))
    else:
        logger.info("DATABASE {} is Not a SQLite Database.".format(CONSTANT['DATABASE']['DATABASE']))
    if not sqlite:
        try:
            Database().get_cursor()
            read, write = True, True
            code = 200
        except pyodbc.Error as error:
            logger.error("Error While connecting to Database {} is: {}.".format(CONSTANT['DATABASE']['DATABASE'], str(error)))
    response = {"database": CONSTANT['DATABASE']['DRIVER'], "read": read, "write": write}
    return response, code
