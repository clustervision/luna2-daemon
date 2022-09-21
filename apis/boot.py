#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point of Every Boot Related Activity.

"""

from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *

logger = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__)

"""
/boot will serve the template from boot_ipxe.cfg
Template should be modified via Jinja2 with correct fields. 
"""
@boot_blueprint.route("/boot", methods=['GET'])
@validate_access
def boot(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Boot API. It will start render boot_ipxe.cfg")
    response = {"message": "This is Boot API."}
    code = 200
    return json.dumps(response), code


"""
/boot search receive MAC Address 
Check if SNMP port-detection has been enabled.
Return the hostname
"""
@boot_blueprint.route("/boot/search/mac/<string:mac>", methods=['GET'])
@validate_access
def boot_search_mac(mac=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if mac:
        logger.info("This is Boot Search API MACID is. {}".format(mac))
        response = {"message": "This is Boot Search API MACID is. {}".format(mac)}
        code = 200
    else:
        logger.error("MacID is Missing.")
        response = {"message": "MacID is Missing."}
        code = 200
    return json.dumps(response), code


"""
/boot search receive NodeName or NodeID 
Return Call the installation script for the Node.
"""
@boot_blueprint.route("/boot/install/<string:node>", methods=['GET'])
@validate_access
def boot_install(node=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if node:
        logger.info("This is Boot Install API NodeID is: {}".format(node))
        response = {"message": "This is Boot Install API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code
