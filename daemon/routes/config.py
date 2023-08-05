#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is a A Entry Point of Every Configuration Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required, agent_check
from common.validate_input import input_filter, validate_name
from base.node import Node
from base.group import Group
from base.interface import Interface
from base.osimage import OSImage
from base.cluster import Cluster
from base.bmcsetup import BMCSetup
from base.switch import Switch
from base.otherdev import OtherDev
from base.network import Network
from base.secret import Secret
from base.osuser import OsUser
from utils.helper import Helper

LOGGER = Log.get_logger()
config_blueprint = Blueprint('config', __name__)


@config_blueprint.route('/config/node', methods=['GET'])
# @token_required
def config_node():
    """
    This api will send all the nodes in details.
    """
    # TODO
    # we collect all needed info from all tables at once and use dicts to collect data/info
    # A join is not really suitable as there are too many permutations in where the below
    # is way more efficient. -Antoine
    access_code = 404
    status, response = Node().get_all_nodes()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/node/<string:name>', methods=['GET'])
# @token_required
@validate_name
@agent_check
def config_node_get(cli=None, name=None):
    """
    This api will send a requested node in details.
    """
    access_code = 404
    status, response = Node().get_node(cli, name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/node/<string:name>', methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_post(name=None):
    """
    This api will create or update a node depends on the availability of the node name.
    """
    status, response = Node().update_node(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/node/<string:name>/_clone', methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_clone(name=None):
    """
    This api will clone a node depends on the availability of the node name.
    """
    status, response = Node().clone_node(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@config_blueprint.route('/config/node/<string:name>/_delete', methods=['GET'])
@token_required
@validate_name
def config_node_delete(name=None):
    """
    Input - Node Name
    Process - Delete the Node and it's interfaces.
    Output - Success or Failure.
    """
    status, response = Node().delete_node(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# NEW API call.
@config_blueprint.route("/config/node/<string:name>/_osgrab", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_osgrab(name=None):
    """
    Input - OS Image name
    Process - Grab the OS from a node into an image. node inside json.
    Output - Success or Failure.
    """
    access_code=404
    returned = OSImage().grab(name, request)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


# NEW API call.
@config_blueprint.route("/config/node/<string:name>/_ospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_ospush(name=None):
    """
    Input - OS Image name
    Process - Push the OS from an image to a node. node inside json
    Output - Success or Failure.
    """
    access_code=404
    returned = OSImage().push(name, request)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/node/<string:name>/interfaces', methods=['GET'])
# @token_required
@validate_name
def config_node_get_interfaces(name=None):
    """
    Input - Node Name
    Process - Fetch the Node Interface List.
    Output - Node Interface List.
    """
    access_code=404
    status, response = Interface().get_all_node_interface(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/node/<string:name>/interfaces", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_node_post_interfaces(name=None):
    """
    Input - Node Name
    Process - Create Or Update The Node Interface.
    Output - Node Interface.
    """
    status, response = Interface().change_node_interface(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
# @token_required
@validate_name
def config_node_interface_get(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Get the Node Interface.
    Output - Success or Failure.
    """
    access_code=404
    status, response = Interface().get_node_interface(name, interface)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code



@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
@validate_name
def config_node_delete_interface(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Delete the Node Interface.
    Output - Success or Failure.
    """
    status, response = Interface().delete_node_interface(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Group configuration #############################

# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group", methods=['GET'])
# @token_required
def config_group():
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    access_code=404
    status, response = Group().get_all_group()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>", methods=['GET'])
# @token_required
@validate_name
@agent_check
def config_group_get(cli=None, name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    access_code = 404
    status, response = Group().get_group(cli, name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/_list", methods=['GET'])
@token_required
@validate_name
def config_group_member(name=None):
    """
    This method will fetch all the nodes, which is connected to
    the provided group.
    """
    access_code=404
    status, response = Group().get_group_member(name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_post(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    status, response = Group().update_group(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# NEW API call.
@config_blueprint.route("/config/group/<string:name>/_ospush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_ospush(name=None):
    """
    Input - OS Image name
    Process - Push the OS from an image to a all nodes in the group. node inside json
    Output - Success or Failure.
    """
    access_code=404
    returned = OSImage().push(name, request)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_clone(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    status, response = Group().clone_group(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@config_blueprint.route("/config/group/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_group_delete(name=None):
    """
    Input - Group Name
    Process - Delete the Group and it's interfaces.
    Output - Success or Failure.
    """
    status, response = Group().delete_group(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['GET'])
# @token_required
@validate_name
def config_group_get_interfaces(name=None):
    """
    Input - Group Name
    Process - Fetch the Group Interface List.
    Output - Group Interface List.
    """
    access_code=404
    status, response = Interface().get_all_group_interface(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_group_post_interfaces(name=None):
    """
    Input - Group Name
    Process - Create Or Update The Group Interface.
    Output - Group Interface.
    """
    status, response = Interface().change_group_interface(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>", methods=['GET'])
# @token_required
@validate_name
def config_group_interface_get(name=None, interface=None):
    """
    Input - Group Name & Interface Name
    Process - Get the Group Interface.
    Output - Success or Failure.
    """
    access_code=404
    status, response = Interface().get_group_interface(name, interface)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
@validate_name
def config_group_delete_interface(name=None, interface=None):
    """
    Input - Group Name & Interface Name
    Process - Delete the Group Interface.
    Output - Success or Failure.
    """
    status, response = Interface().delete_group_interface(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# OSimage configuration #############################

@config_blueprint.route("/config/osimage", methods=['GET'])
def config_osimage():
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    access_code=404
    status, response = OSImage().get_all_osimages()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
@validate_name
def config_osimage_get(name=None):
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    access_code=404
    status, response = OSImage().get_osimage(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>/_list", methods=['GET'])
@token_required
@validate_name
def config_osimage_member(name=None):
    """
    This method will fetch all the nodes, which is connected to
    the provided osimage.
    """
    access_code=404
    status, response = OSImage().get_osimage_member(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osimage'], skip=None)
def config_osimage_post(name=None):
    """
    Input - OS Image Name
    Process - Create or Update the OS Image information.
    Output - OSImage Info.
    """
    status, response = OSImage().update_osimage(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 5 2023
@config_blueprint.route("/config/osimage/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osimage'], skip=None)
def config_osimage_clone(name=None):
    """
    Input - OS Image Name
    Process - Clone OS Image information.
    Output - OSImage Info.
    """
    access_code=404
    returned = OSImage().clone_osimage(name, request)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_osimage_delete(name=None):
    """
    Input - OS Image ID or Name
    Process - Delete the OS Image.
    Output - Success or Failure.
    """
    status, response = OSImage().delete_osimage(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/osimage/<string:name>/_pack", methods=['GET'])
@token_required
@validate_name
def config_osimage_pack(name=None):
    """
    Input - OS Image ID or Name
    Process - Manually Pack the OS Image.
    Output - Success or Failure.
    """
    access_code=404
    returned = OSImage().pack(name)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osimage'], skip=None)
def config_osimage_kernel_post(name=None):
    """
    Input - OS Image Name
    Process - Manually change kernel version.
    Output - Kernel Version.
    """
    status, response = OSImage().change_kernel(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# Cluster configuration #############################


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/cluster", methods=['GET'])
# @token_required
def config_cluster():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    access_code=404
    status, response = Cluster().information()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/cluster", methods=['POST'])
@token_required
@input_filter(checks=['config:cluster'], skip=None)
def config_cluster_post():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    status, response = Cluster().update_cluster(request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# BMC setup configuration #############################

@config_blueprint.route("/config/bmcsetup", methods=['GET'])
# @token_required
def config_bmcsetup():
    """
    This route will provide all the BMC Setup's.
    """
    access_code=404
    status, response = BMCSetup().get_all_bmcsetup()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/bmcsetup/<string:name>", methods=['GET'])
# @token_required
@validate_name
def config_bmcsetup_get(name=None):
    """
    This route will provide a requested BMC Setup.
    """
    access_code=404
    status, response = BMCSetup().get_bmcsetup(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/bmcsetup/<string:name>/_list", methods=['GET'])
@token_required
@validate_name
def config_bmcsetup_member(name=None):
    """
    This route will provide the list of nodes which is connected to the requested BMC Setup.
    """
    access_code=404
    status, response = BMCSetup().get_bmcsetup_member(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/bmcsetup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:bmcsetup'], skip=None)
def config_bmcsetup_post(name=None):
    """
    This route will create or update requested BMC Setup.
    """
    status, response = BMCSetup().update_bmcsetup(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/bmcsetup/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:bmcsetup'], skip=None)
def config_bmcsetup_clone(name=None):
    """
    This route will clone a requested BMC Setup.
    """
    status, response = BMCSetup().clone_bmcsetup(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/bmcsetup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_bmcsetup_delete(name=None):
    """
    This route will delete a requested BMC Setup.
    """
    status, response = BMCSetup().delete_bmcsetup(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# Switch configuration #############################

@config_blueprint.route("/config/switch", methods=['GET'])
# @token_required
def config_switch():
    """
    This route will provide all the Switches.
    """
    access_code=404
    status, response = Switch().get_all_switches()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/switch/<string:name>", methods=['GET'])
# @token_required
@validate_name
def config_switch_get(name=None):
    """
    This route will provide a requested Switch.
    """
    access_code=404
    status, response = Switch().get_switch(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/switch/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:switch'], skip=None)
def config_switch_post(name=None):
    """
    This route will create or update a requested Switch.
    """
    status, response = Switch().update_switch(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/switch/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:switch'], skip=None)
def config_switch_clone(name=None):
    """
    This route will clone a requested Switch.
    """
    status, response = Switch().clone_switch(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/switch/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_switch_delete(name=None):
    """
    This route will delete a requested Switch.
    """
    status, response = Switch().delete_switch(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Other Devices configuration #############################

@config_blueprint.route("/config/otherdev", methods=['GET'])
# @token_required
def config_otherdev():
    """
    This route will provide all the Other Devices.
    """
    access_code=404
    status, response = OtherDev().get_all_otherdev()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/otherdev/<string:name>", methods=['GET'])
# @token_required
@validate_name
def config_otherdev_get(name=None):
    """
    This route will provide a requested Other Device.
    """
    access_code=404
    status, response = OtherDev().get_otherdev(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/otherdev/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:otherdev'], skip=None)
def config_otherdev_post(name=None):
    """
    This route will create or update a requested Other Device.
    """
    status, response = OtherDev().update_otherdev(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/otherdev/<string:name>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:otherdev'], skip=None)
def config_otherdev_clone(name=None):
    """
    This route will clone a requested Other Device.
    """
    status, response = OtherDev().clone_otherdev(name, request)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/otherdev/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_otherdev_delete(name=None):
    """
    This route will delete a requested Other Device.
    """
    status, response = OtherDev().delete_otherdev(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Network configuration #############################

@config_blueprint.route("/config/network", methods=['GET'])
# @token_required
def config_network():
    """
    Input - None
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    response, access_code = Network().get_all_networks()
    return response, access_code


@config_blueprint.route("/config/network/<string:name>", methods=['GET'])
# @token_required
@validate_name
def config_network_get(name=None):
    """
    Input - Network Name
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    response, access_code = Network().get_network(name)
    return response, access_code


@config_blueprint.route("/config/network/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:network'], skip=None)
def config_network_post(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    response, access_code = Network().update_network(name, request)
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_network_delete(name=None):
    """
    Input - Network Name
    Process - Delete The Network.
    Output - Success or Failure.
    """
    response, access_code = Network().delete_network(name)
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/<string:ipaddress>", methods=['GET'])
@token_required
@validate_name
def config_network_ip(name=None, ipaddress=None):
    """
    Input - Network Name And IP Address
    Process - Delete The Network.
    Output - Success or Failure.
    """
    response, access_code = Network().network_ip(name, ipaddress)
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/_list", methods=['GET'])
@token_required
@validate_name
def config_network_taken(name=None):
    """
    Input - Network Name
    Process - Find out all the ipaddress which is taken by the provided network.
    Output - List all taken ipaddress by the network.
    """
    response, access_code = Network().taken_ip(name)
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
# @token_required
@validate_name
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Network.
    Output - Next Available IP on the Network.
    """
    response, access_code = Network().next_free_ip(name)
    return response, access_code

############################# Secrets configuration #############################

@config_blueprint.route("/config/secrets", methods=['GET'])
@token_required
def config_secrets_get():
    """
    Input - None
    Output - Return the List Of All Secrets.
    """
    response, access_code = Secret().get_all_secrets()
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_node(name=None):
    """
    Input - Node Name
    Output - Return the Node Secrets And Group Secrets for the Node.
    """
    response, access_code = Secret().get_node_secrets(name)
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_post_secrets_node(name=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    response, access_code = Secret().update_node_secrets(name, request)
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_node_secret(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Return the Node Secret
    """
    response, access_code = Secret().get_node_secret(name, secret)
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_post_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    response, access_code = Secret().update_node_secret(name, secret, request)
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:node'], skip=None)
def config_clone_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    response, access_code = Secret().clone_node_secret(name, secret, request)
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
@token_required
@validate_name
def config_node_secret_delete(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Success or Failure
    """
    response, access_code = Secret().delete_node_secret(name, secret)
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_group(name=None):
    """
    Input - Group Name
    Output - Return the Group Secrets.
    """
    response, access_code = Secret().get_group_secrets(name)
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_post_secrets_group(name=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    response, access_code = Secret().update_group_secrets(name, request)
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_group_secret(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Return the Group Secret
    """
    response, access_code = Secret().get_group_secret(name, secret)
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_post_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    response, access_code = Secret().update_group_secret(name, secret, request)
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:secrets:group'], skip=None)
def config_clone_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Clone Group Secrets.
    Output - None.
    """
    response, access_code = Secret().clone_group_secret(name, secret, request)
    return response, access_code


@config_blueprint.route('/config/secrets/group/<string:name>/<string:secret>/_delete', methods=['GET'])
@token_required
@validate_name
def config_group_secret_delete(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Success or Failure
    """
    response, access_code = Secret().delete_group_secret(name, secret)
    return response, access_code


@config_blueprint.route("/config/osuser", methods=['GET'])
@token_required
def config_get_os_user_list():
    """
    Input - None
    Process - List OSystem (ldap/ssd/pam) group.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().list_users()
    if ret is True:
        access_code=200
        return dumps(message), access_code
    else:
        response={'message': message}
    return response, access_code


@config_blueprint.route("/config/osgroup", methods=['GET'])
@token_required
def config_get_os_group_list():
    """
    Input - None
    Process - List OSystem (ldap/ssd/pam) group.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().list_groups()
    if ret is True:
        access_code=200
        return dumps(message), access_code
    else:
        response={'message': message}
    return response, access_code


@config_blueprint.route("/config/osuser/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osuser'], skip=None)
def config_post_os_user(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update System (ldap/ssd/pam) users.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().update_user(name, request)
    response={'message': message}
    if ret is True:
        access_code=204
    return response, access_code


@config_blueprint.route("/config/osuser/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_user_delete(name=None):
    """
    Input - User Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().delete_user(name)
    response={'message': message}
    if ret is True:
        access_code=204
    return response, access_code


@config_blueprint.route("/config/osgroup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osgroup'], skip=None)
def config_post_os_group(name=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update System (ldap/ssd/pam) group.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().update_group(name, request)
    response={'message': message}
    if ret is True:
        access_code=204
    return response, access_code


@config_blueprint.route("/config/osgroup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_group_delete(name=None):
    """
    Input - Group Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    response, access_code = None, 404
    ret, message = OsUser().delete_group(name)
    response={'message': message}
    if ret is True:
        access_code=204
    return response, access_code


@config_blueprint.route('/config/status/<string:request_id>', methods=['GET'])
@validate_name
def control_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """
    response, access_code = OSImage().get_status(request_id)
    return response, access_code
