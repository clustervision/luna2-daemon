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


"""
/config/node Return the list of all nodes
"""
@config_blueprint.route("/config/node", methods=['GET'])
@validate_access
def config_node(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Config Node API.")
    response = {"message": "This is Node Node API."}
    code = 200
    return json.dumps(response), code


"""
/config/node will receive the Node Name or ID.
Return the complete information of the Node
"""
@config_blueprint.route("/config/node/<string:node>", methods=['GET'])
@validate_access
def config_node_get(node=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        logger.info("access: {}".format(access))
    if node:
        logger.info("This is Config Node GET API NodeID is: {}".format(node))
        response = {"message": "This is Config Node GET API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code

"""
/config/node will receive the Node Name or ID.
Do update or create depends on the payload.
"""
@config_blueprint.route("/config/node/<string:node>", methods=['POST'])
@token_required
def config_node_post(node=None):
    if node:
        logger.info("This is Config Node POST API NodeID is: {}".format(node))
        response = {"message": "This is Config Node POST API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/node/NODE/remove will receive the Node Name or ID.
And Delete The Node.
"""
@config_blueprint.route("/config/node/<string:node>/remove", methods=['POST'])
@token_required
def config_node_remove(node=None):
    if node:
        logger.info("This is Config Node Remove API NodeID is: {}".format(node))
        response = {"message": "This is Config Node Remove API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code

"""
/config/node/NODE/interfaces will receive the NODE ID or Name.
Return the network interface list of the Node
"""
@config_blueprint.route("/config/node/<string:node>/interfaces", methods=['GET'])
@validate_access
def config_node_interfaces_get(node=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if node:
        logger.info("This is Config Node Interfaces GET API NodeID is: {}".format(node))
        response = {"message": "This is Config Node Interfaces GET API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/node/NODE/interfaces will receive the NODE ID or Name.
Return update the node interface list.
"""
@config_blueprint.route("/config/node/<string:node>/interfaces", methods=['POST'])
@token_required
def config_node_interfaces_post(node=None):
    if node:
        logger.info("This is Config Node Interfaces POST API NodeID is: {}".format(node))
        response = {"message": "This is Config Node Interfaces POST API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/group will provide a list of groups.
"""
@config_blueprint.route("/config/group", methods=['GET'])
@validate_access
def config_group(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Config Group API.")
    response = {"message": "This is Group API."}
    code = 200
    return json.dumps(response), code


"""
/config/group will receive a group name or id.
Return the information of provided group.
"""
@config_blueprint.route("/config/group/<string:group>", methods=['GET'])
@validate_access
def config_group_get(group=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if group:
        logger.info("This is Config Group GET API Group is: {}".format(group))
        response = {"message": "This is Config Group GET API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/group will do update or create a group, depends on the payload.
"""
@config_blueprint.route("/config/group/<string:group>", methods=['POST'])
@token_required
def config_group_post(group=None):
    if group:
        logger.info("This is Config Group POST API Group is: {}".format(group))
        response = {"message": "This is Config Group POST API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/group/GROUP/remove will receive the group name or ID.
Return Delete the group.
"""
@config_blueprint.route("/config/group/<string:group>/remove", methods=['POST'])
@token_required
def config_group_remove(group=None):
    if group:
        logger.info("This is Config Group Remove API Group is: {}".format(group))
        response = {"message": "This is Config Group Remove API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/group/GROUP/interfaces will receive the group name or ID.
Return List the network interfaces of the individual group.
"""
@config_blueprint.route("/config/group/<string:group>/interfaces", methods=['GET'])
@validate_access
def config_group_interfaces_get(group=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if group:
        logger.info("This is Config Group Interfaces GET API Group is: {}".format(group))
        response = {"message": "This is Config Group Interfaces GET API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/group/GROUP/interfaces will receive the group name or ID.
Return Create or update the network interface. Primary is the interface name. Note reserved names such as BOOTIF and BMC
"""
@config_blueprint.route("/config/group/<string:group>/interfaces", methods=['POST'])
@token_required
def config_group_interfaces_post(group=None):
    if group:
        logger.info("This is Config Group Interfaces POST API Group is: {}".format(group))
        response = {"message": "This is Config Group Interfaces POST API Group is: {}".format(group)}
        code = 200
    else:
        logger.error("Group is Missing.")
        response = {"message": "Group is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage will receive the OS Image Name or ID.
Return the OSImage All Information
"""
@config_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
@validate_access
def config_osimage_get(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if name:
        logger.info("This is Config OSImage GET API OSImage is: {}".format(name))
        response = {"message": "This is Config OSImage GET API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage will receive the OS Image Name or ID.
Return create a new OSImage.
"""
@config_blueprint.route("/config/osimage/<string:name>", methods=['POST'])
@token_required
def config_osimage_post(name=None):
    if name:
        logger.info("This is Config OSImage POST API OSImage Name is: {}".format(name))
        response = {"message": "This is Config OSImage POST API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage/OSIMAGE/remove will receive the OS Image Name or ID.
Return delete the OSImage.
"""
@config_blueprint.route("/config/osimage/<string:name>/remove", methods=['GET'])
@validate_access
def config_osimage_remove(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if name:
        logger.info("This is Config OSImage Remove API OSImage Name is: {}".format(name))
        response = {"message": "This is Config OSImage Remove API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage/OSIMAGE/pack will receive the OS Image Name or ID.
Return Manually pack osimage.
"""
@config_blueprint.route("/config/osimage/<string:name>/pack", methods=['GET'])
@validate_access
def config_osimage_pack(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if name:
        logger.info("This is Config OSImage Pack GET API OSImage is: {}".format(name))
        response = {"message": "This is Config OSImage Pack GET API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage/OSIMAGE/kernel will receive the OS Image Name or ID.
Return the OSImage Kernel Version.
"""
@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['GET'])
@validate_access
def config_osimage_kernel_get(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if name:
        logger.info("This is Config OSImage Kernel GET API OSImage is: {}".format(name))
        response = {"message": "This is Config OSImage Kernel GET API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/osimage/OSIMAGE/kernel will receive the OS Image Name or ID.
Return update the OSImage Kernel Version.
"""
@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
@token_required
def config_osimage_kernel_post(name=None):
    if name:
        logger.info("This is Config OSImage Kernel POST API OSImage Name is: {}".format(name))
        response = {"message": "This is Config OSImage Kernel POST API OSImage Name is: {}".format(name)}
        code = 200
    else:
        logger.error("OSImage Name is Missing.")
        response = {"message": "OSImage Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/cluster Show cluster information.
"""
@config_blueprint.route("/config/cluster", methods=['GET'])
@validate_access
def config_cluster(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Config Cluster GET API.")
    response = {"message": "This is Config Cluster GET API."}
    code = 200
    return json.dumps(response), code


"""
/config/bmcsetup revert with List Of Configured BMC Setup Settings.
"""
@config_blueprint.route("/config/bmcsetup", methods=['GET'])
@validate_access
def config_bmcsetup(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Config BMC Setup API.")
    response = {"message": "This is BMC Setup API."}
    code = 200
    return json.dumps(response), code


"""
/config/bmcsetup receive BMC Name.
Return the BMC Setup Settings.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['GET'])
@validate_access
def config_bmcsetup_get(bmcname=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if bmcname:
        logger.info("This is Config BMC Setup GET API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup GET API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/bmcsetup receive BMC Name.
Return create or update the BMC Setup depends upon the Payload.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['POST'])
@token_required
def config_bmcsetup_post(bmcname=None):
    if bmcname:
        logger.info("This is Config BMC Setup POST API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup POST API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/bmcsetup/BMCNAME/credentials receive BMC Name.
Return BMC name and get Credentials.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/credentials", methods=['GET'])
@validate_access
def config_bmcsetup_credentials_get(bmcname=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if bmcname:
        logger.info("This is Config BMC Setup Credentials GET API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup Credentials GET API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/bmcsetup/BMCNAME/credentials receive BMC Name.
Return Update the BMC Credentials.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/credentials", methods=['POST'])
@token_required
def config_bmcsetup_credentials_post(bmcname=None):
    if bmcname:
        logger.info("This is Config BMC Setup Credentials POST API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup Credentials POST API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/bmcsetup/BMCNAME/remove receive BMC Name.
Return Delete the BMC Setup.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/remove", methods=['GET'])
@validate_access
def config_bmcsetup_remove(bmcname=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if bmcname:
        logger.info("This is Config BMC Setup Remove API BMC Setup Name is: {}".format(bmcname))
        response = {"message": "This is Config BMC Setup Remove API BMC Setup Name is: {}".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/switch Returns the List of All switches.
"""
@config_blueprint.route("/config/switch", methods=['GET'])
@validate_access
def config_switch(**kwargs):
    if "access" in kwargs:
        access = "admin"
    logger.info("This is Config Switch API.")
    response = {"message": "This is Switch API."}
    code = 200
    return json.dumps(response), code


"""
/config/switch receive the Switch Name or ID.
Returns the information of given Switch.
"""
@config_blueprint.route("/config/switch/<string:switch>", methods=['GET'])
@validate_access
def config_switch_get(switch=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if switch:
        logger.info("This is Config Switch GET API Switch: {}".format(switch))
        response = {"message": "This is Config Switch GET API Switch: {}".format(switch)}
        code = 200
    else:
        logger.error("Switch is Missing.")
        response = {"message": "Switch is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/switch receive the Switch Name or ID.
Returns Delete the Switch.
"""
@config_blueprint.route("/config/switch/<string:switch>/remove", methods=['GET'])
@validate_access
def config_switch_remove(switch=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if switch:
        logger.info("This is Config Switch Remove API Switch is: {}".format(switch))
        response = {"message": "This is Config Switch Remove API Switch is: {}".format(switch)}
        code = 200
    else:
        logger.error("Switch is Missing.")
        response = {"message": "Switch is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/otherdev receive the Device Name or ID.
Returns the list of other Devices..
"""
@config_blueprint.route("/config/otherdev/<string:device>", methods=['GET'])
@validate_access
def config_otherdev_get(device=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if device:
        logger.info("This is Config Other Device GET API Device: {}".format(device))
        response = {"message": "This is Config Other Device GET API Device: {}".format(device)}
        code = 200
    else:
        logger.error("Device is Missing.")
        response = {"message": "Device is Missing."}
        code = 200
    return json.dumps(response), code


"""
/config/otherdev receive the Device Name or ID.
Returns Delete the Device.
"""
@config_blueprint.route("/config/otherdev/<string:device>/remove", methods=['GET'])
@validate_access
def config_otherdev_remove(device=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if device:
        logger.info("This is Config Other Device Remove API Device is: {}".format(device))
        response = {"message": "This is Config Other Device Remove API Device is: {}".format(device)}
        code = 200
    else:
        logger.error("Device is Missing.")
        response = {"message": "Device is Missing."}
        code = 200
    return json.dumps(response), code