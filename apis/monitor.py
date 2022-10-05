#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point to Monitor the services.

"""

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
    else:
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
    status = True
    if status:
        logger.info("Node {} is UP And Running".format(node))
        response = {"message": "Node {} is UP And Running".format(node)}
        code = 200
    else:
        logger.info("Node {} is Down And Not Running".format(node))
        response = {"message": "Node {} is Down And Not Running".format(node)}
        code = 404
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Update the Node Status
Output - Status.
"""
@monitor_blueprint.route("/monitor/status/<string:node>", methods=['POST'])
def monitor_status_post(node=None):
    status = True
    if status:
        logger.info("Node {} is Updated.".format(node))
        response = {"message": "Node {} is Updated.".format(node)}
        code = 200
    else:
        logger.info("Node {} is Down And Not Running".format(node))
        response = {"message": "Node {} is Down And Not Running".format(node)}
        code = 404
    return json.dumps(response), code


"""
Input - None
Process - Check the Current Database condition.
Output - Status of Read & Write.
"""
def checkdbstatus():
    sqlite, read, write = False, False, False
    code = 503
    if os.path.isfile(DATABASE):
        sqlite = True
        if os.access(DATABASE, os.R_OK): 
            read = True
            code = 500
            try:
                file = open(DATABASE, "a")
                if file.writable():
                    write = True
                    code = 200
                    file.close()
            except Exception as e:
                logger.error("DATABASE {} is Not Writable.".format(DATABASE))
            
            with open(DATABASE,'r', encoding = "ISO-8859-1") as f:
                header = f.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                else:
                    read, write = False, False
                    code = 503
                    logger.error("DATABASE {} is Not a SQLite3 Database.".format(DATABASE))
        else:
            logger.error("DATABASE {} is Not Readable.".format(DATABASE))
    else:
        logger.info("DATABASE {} is Not a SQLite Database.".format(DATABASE))
    if not sqlite:
        try:
            Database().get_cursor()
            read, write = True, True
            code = 200
        except pyodbc.Error as error:
            logger.error("Error While connecting to Database {} is: {}.".format(DATABASE, str(error)))
    response = {"database": DRIVER, "read": read, "write": write}
    return response, code
