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

from flask import Blueprint, request, json, render_template
from utils.log import *
from utils.database import *

logger = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__, template_folder='../templates') # , template_folder='templates'


"""
Input - None
Process - Via Jinja2 filled data in template templ_boot_ipxe.cfg 
Output - templ_boot_ipxe.cfg
"""
@boot_blueprint.route("/boot", methods=['GET'])
def boot():
    nodes = ["node001", "node002", "node003", "node004"]
    data = {"protocol": "http", "server_ip": "10.141.255.254", "server_port": "7051", "nodes": nodes}
    Template = "templ_boot_ipxe.cfg"
    logger.info("Boot API Serving the {}".format(Template))
    return render_template(Template, p=data), 200


"""
Input - None
Process - Via Jinja2 filled data in template templ_boot_ipxe_short.cfg 
Output - templ_boot_ipxe_short.cfg
"""
@boot_blueprint.route("/boot/short", methods=['GET'])
def boot_short():
    nodes = ["node001", "node002", "node003", "node004"]
    data = {"protocol": "http", "server_ip": "10.141.255.254", "server_port": "7051", "nodes": nodes}
    Template = "templ_boot_ipxe_short.cfg"
    logger.info("Boot API Serving the {}".format(Template))
    return render_template(Template, p=data), 200


"""
Input - None
Process - Via Jinja2 filled data in template templ_boot_disk.cfg 
Output - templ_boot_disk.cfg
"""
@boot_blueprint.route("/boot/disk", methods=['GET'])
def boot_disk():
    nodes = ["node001", "node002", "node003", "node004"]
    data = {"protocol": "http", "server_ip": "10.141.255.254", "server_port": "7051", "nodes": nodes}
    Template = "templ_boot_disk.cfg"
    logger.info("Boot API Serving the {}".format(Template))
    return render_template(Template, p=data), 200

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


    ## TODO TRIX-39 [Waiting for confirmation]
    ## Validate Node from Node Table
    ## Validate BootMenu and NetBoot from group table
    # node, bootmenu, netboot = check_node_state(nodeparam)
    # if node == True and bootmenu == False and netboot == True:
    #     Template = "boot_ipxe_short.cfg"
    # elif node == True and bootmenu == True and netboot == True:
    #     Template = "boot_ipxe.cfg"
    # elif node == True and bootmenu == True and netboot == False:
    #     Template = "boot_ipxe_disk.cfg"
    # elif node == False and bootmenu == False and netboot == True:
    #     Template = "boot_ipxe.cfg"
    # else:
    #     Template = "boot_ipxe.cfg"
# def check_node_state(nodeparam):
#     node, bootmenu, netboot = False, False, False
#     table = "node"
#     where = f' WHERE id = "{nodeparam}" OR name = "{nodeparam}" OR macaddr = "{nodeparam}"'
#     NODE = Database().get_record(None, table, where)
#     if NODE:
#         node = True
#         logger.info(f'Node {nodeparam} is a Registered Node.')
#     else:
#         logger.info(f'Node {nodeparam} is Not a Registered Node.')
#     GROUP = Database().get_record(None, 'group', None)
#     if GROUP:
#         bootmenu = GROUP[0]["bootmenu"]
#         netboot = GROUP[0]["netboot"]
#         logger.info(f'Node {nodeparam} Have BootMenu {bootmenu} and NetBoot {netboot}.')
#     else:
#         logger.info(f'Node {nodeparam} Do not have the BootMenu and the NetBoot.')
#     return node, bootmenu, netboot