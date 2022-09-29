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
from flask import Blueprint, request, json, render_template
from utils.log import *

logger = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__, template_folder='../ipxe') # , template_folder='templates'


"""
Input - None
Process - Via Jinja2 filled data in template boot_ipxe.cfg 
Output - boot_ipxe.cfg
"""
@boot_blueprint.route("/boot", methods=['GET'])
def boot():
    nodes = ["node001", "node002", "node003", "node004"]
    data = {"protocol": "http", "serverip": "10.141.255.254", "serverport": "7051", "nodes": nodes}
    Template = "boot_ipxe.cfg"
    logger.info("Boot API Serving the {}".format(Template))
    return render_template(Template, data=data), 200


"""
Input - MacID
Process - Discovery on MAC address, Server will lookup the MAC if SNMP port-detection has been enabled
Output - hostname
"""
@boot_blueprint.route("/boot/search/mac/<string:mac>", methods=['GET'])
def boot_search_mac(mac=None):
    hostname = "HOSTNAME"
    if hostname:
        logger.info("hostname is {}".format(hostname))
        response = {"message": hostname}
        code = 200
    else:
        logger.error("Hostname Not Found For MacID {}.".format(mac))
        response = {"message": "Hostname Not Found For MacID {}.".format(mac)}
        code = 404
    return json.dumps(response), code


"""
Input - NodeID or Node Name
Process - Call the installation script for this node.
Output - Success or Failure
"""
@boot_blueprint.route("/boot/install/<string:node>", methods=['GET'])
def boot_install(node=None):
    install = True
    if install:
        logger.info("Installation Script is Started For  NodeID: {}".format(node))
        response = {"message": "Installation Script is Started For  NodeID: {}".format(node)}
        code = 200
    else:
        logger.error("Not Able To Find The NodeID: {}".format(node))
        response = {"message": "Not Able To Find The NodeID: {}".format(node)}
        code = 404
    return json.dumps(response), code