#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point of Every Configuration Related Activity.

"""

from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *

logger = Log.get_logger()

config_blueprint = Blueprint('config', __name__)


@config_blueprint.route("/<string:token>/config", methods=['GET'])
@login_required
def config(token):
    logger.info("This is Config API.")
    response = {"message": "This is Config API."}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/node", methods=['GET'])
@login_required
def config_node(token):
    logger.info("This is Config Node API.")
    response = {"message": "This is Node Node API."}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/node/<string:node>", methods=['GET','POST'])
@login_required
def config_node_get(token, node=None):
    if node:
        if request.method == 'POST':
            logger.info("This is Config Node POST API NodeID is: {}".format(node))
            response = {"message": "This is Config Node POST API NodeID is: {}".format(node)}
            code = 200
        else:
            logger.info("This is Config Node GET API NodeID is: {}".format(node))
            response = {"message": "This is Config Node GET API NodeID is: {}".format(node)}
            code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/node/<string:node>/remove", methods=['GET'])
@login_required
def config_node_remove(token, node=None):
    if node:
        logger.info("This is Config Node Remove API NodeID is: {}".format(node))
        response = {"message": "This is Config Node Remove API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/node/<string:node>/interfaces", methods=['GET','POST'])
@login_required
def config_node_interfaces(token, node=None):
    if node:
        if request.method == 'POST':
            logger.info("This is Config Node Interfaces POST API NodeID is: {}".format(node))
            response = {"message": "This is Config Node Interfaces POST API NodeID is: {}".format(node)}
            code = 200
        else:
            logger.info("This is Config Node Interfaces GET API NodeID is: {}".format(node))
            response = {"message": "This is Config Node Interfaces GET API NodeID is: {}".format(node)}
            code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/group", methods=['GET'])
@login_required
def config_group(token):
    logger.info("This is Config Group API.")
    response = {"message": "This is Group API."}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/group/<string:group>", methods=['GET','POST'])
@login_required
def config_group_get(token, group=None):
    if group:
        if request.method == 'POST':
            logger.info("This is Config Group POST API Group is: {}".format(group))
            response = {"message": "This is Config Group POST API Group is: {}".format(group)}
            code = 200
        else:
            logger.info("This is Config Group GET API Group is: {}".format(group))
            response = {"message": "This is Config Group GET API Group is: {}".format(group)}
            code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/group/<string:group>/remove", methods=['GET'])
@login_required
def config_group_remove(token, group=None):
    if group:
        logger.info("This is Config Group Remove API Group is: {}".format(group))
        response = {"message": "This is Config Group Remove API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/group/<string:group>/interfaces", methods=['GET','POST'])
@login_required
def config_group_interfaces(token, group=None):
    if group:
        if request.method == 'POST':
            logger.info("This is Config Group Interfaces POST API Group is: {}".format(group))
            response = {"message": "This is Config Group Interfaces POST API Group is: {}".format(group)}
            code = 200
        else:
            logger.info("This is Config Group Interfaces GET API Group is: {}".format(group))
            response = {"message": "This is Config Group Interfaces GET API Group is: {}".format(group)}
            code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code




@config_blueprint.route("/<string:token>/config/osimage/<string:name>", methods=['GET','POST'])
@login_required
def config_osimage(token, name=None):
    if name:
        if request.method == 'POST':
            logger.info("This is Config OSImage POST API OSImage Name is: {}".format(name))
            response = {"message": "This is Config OSImage POST API OSImage Name is: {}".format(name)}
            code = 200
        else:
            logger.info("This is Config OSImage GET API OSImage is: {}".format(name))
            response = {"message": "This is Config OSImage GET API OSImage Name is: {}".format(name)}
            code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/osimage/<string:name>/remove", methods=['GET'])
@login_required
def config_osimage_remove(token, name=None):
    if name:
        logger.info("This is Config OSImage Remove API OSImage Name is: {}".format(name))
        response = {"message": "This is Config OSImage Remove API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/osimage/<string:name>/pack", methods=['GET','POST'])
@login_required
def config_osimage_pack(token, name=None):
    if name:
        if request.method == 'POST':
            logger.info("This is Config OSImage Pack POST API OSImage Name is: {}".format(name))
            response = {"message": "This is Config OSImage Pack POST API OSImage Name is: {}".format(name)}
            code = 200
        else:
            logger.info("This is Config OSImage Pack GET API OSImage is: {}".format(name))
            response = {"message": "This is Config OSImage Pack GET API OSImage Name is: {}".format(name)}
            code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/osimage/<string:name>/kernel", methods=['GET','POST'])
@login_required
def config_osimage_kernel(token, name=None):
    if group:
        if request.method == 'POST':
            logger.info("This is Config OSImage Kernel POST API OSImage Name is: {}".format(name))
            response = {"message": "This is Config OSImage Kernel POST API OSImage Name is: {}".format(name)}
            code = 200
        else:
            logger.info("This is Config OSImage Kernel GET API OSImage is: {}".format(name))
            response = {"message": "This is Config OSImage Kernel GET API OSImage Name is: {}".format(name)}
            code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code



@config_blueprint.route("/<string:token>/config/clusrer", methods=['GET','POST'])
@login_required
def config_clusrer(token):
    if request.method == 'POST':
        logger.info("This is Config Cluster POST API.")
        response = {"message": "This is Config Cluster POST API."}
        code = 200
    else:
        logger.info("This is Config Cluster GET API.")
        response = {"message": "This is Config Cluster GET API."}
        code = 200
    return json.dumps(response), code





@config_blueprint.route("/<string:token>/config/bmcsetup", methods=['GET'])
@login_required
def config_bmcsetup(token):
    logger.info("This is Config BMC Setup API.")
    response = {"message": "This is BMC Setup API."}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/bmcsetup/<string:bmcname>", methods=['GET','POST'])
@login_required
def config_bmcsetup_get(token, bmcname=None):
    if bmcname:
        if request.method == 'POST':
            logger.info("This is Config BMC Setup POST API BMC Setup Name is: {}".format(bmcname))
            response = {"message": "This is Config BMC Setup POST API BMC Setup Name is: {}".format(bmcname)}
            code = 200
        else:
            logger.info("This is Config BMC Setup GET API BMC Setup Name is: {}".format(bmcname))
            response = {"message": "This is Config BMC Setup GET API BMC Setup Name is: {}".format(bmcname)}
            code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/bmcsetup/<string:bmcname>/remove", methods=['GET'])
@login_required
def config_bmcsetup_remove(token, bmcname=None):
    if bmcname:
        logger.info("This is Config BMC Setup Remove API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup Remove API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code



@config_blueprint.route("/<string:token>/config/switch", methods=['GET'])
@login_required
def config_switch(token):
    logger.info("This is Config Switch API.")
    response = {"message": "This is Switch API."}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/switch/<string:switch>", methods=['GET'])
@login_required
def config_switch_get(token, switch=None):
    if switch:
        logger.info("This is Config Switch GET API Switch: {}".format(switch))
        response = {"message": "This is Config Switch GET API Switch: {}".format(switch)}
        code = 200
    else:
        logger.error("Switch is Missing.")
        response = {"message": "Switch is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/switch/<string:switch>/remove", methods=['GET'])
@login_required
def config_switch_remove(token, switch=None):
    if switch:
        logger.info("This is Config Switch Remove API Switch is: {}".format(switch))
        response = {"message": "This is Config Switch Remove API Switch is: {}".format(switch)}
        code = 200
    else:
        logger.error("Switch is Missing.")
        response = {"message": "Switch is Missing."}
        code = 200
    return json.dumps(response), code



@config_blueprint.route("/<string:token>/config/otherdev/<string:device>", methods=['GET'])
@login_required
def config_otherdev_get(token, device=None):
    if device:
        logger.info("This is Config Other Device GET API Device: {}".format(device))
        response = {"message": "This is Config Other Device GET API Device: {}".format(device)}
        code = 200
    else:
        logger.error("Device is Missing.")
        response = {"message": "Device is Missing."}
        code = 200
    return json.dumps(response), code


@config_blueprint.route("/<string:token>/config/otherdev/<string:device>/remove", methods=['GET'])
@login_required
def config_otherdev_remove(token, device=None):
    if device:
        logger.info("This is Config Other Device Remove API Device is: {}".format(device))
        response = {"message": "This is Config Other Device Remove API Device is: {}".format(device)}
        code = 200
    else:
        logger.error("Device is Missing.")
        response = {"message": "Device is Missing."}
        code = 200
    return json.dumps(response), code