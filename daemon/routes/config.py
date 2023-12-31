#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

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
from common.validate_auth import token_required
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
from base.dns import DNS
from base.secret import Secret
from base.osuser import OsUser
from utils.journal import Journal
from utils.helper import Helper
from utils.status import Status
from utils.ha import HA

LOGGER = Log.get_logger()
config_blueprint = Blueprint('config', __name__)


@config_blueprint.route('/config/node', methods=['GET'])
@token_required
def config_node():
    """
    This api will send all the nodes in details.
    """
    access_code = 404
    status, response = Node().get_all_nodes()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/node/<string:name>', methods=['GET'])
@token_required
@validate_name
def config_node_get(name=None):
    """
    This api will send a requested node in details.
    """
    access_code = 404
    status, response = Node().get_node(name)
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
    status, response = Journal().add_request(function="Node.update_node",object=name,payload=request.data)
    if status is True:
        status, response = Node().update_node(name, request.data)
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
    status, response = Journal().add_request(function="Node.clone_node",object=name,payload=request.data)
    if status is True:
        status, response = Node().clone_node(name, request.data)
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
    status, response = Journal().add_request(function="Node.delete_node_by_name",object=name)
    if status is True:
        status, response = Node().delete_node_by_name(name)
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
    osimage=None
    hastate=HA().get_hastate()
    if hastate is True:
        master=HA().get_role()
        if master is False:
            response={'message': 'something went wrong.....'}
            request_id = Status().gen_request_id()
            status, message = Journal().add_request(function="OSImage.grab",object=name,payload=request.data,masteronly=True,misc=request_id)
            if status is True:
                Status().add_message(request_id,"luna","request submitted to master...")
                Status().mark_messages_read(request_id)
                access_code=200
                response = {"message": "request submitted to master...", "request_id": request_id}
            else:
                response={'message': message}
            return response, access_code
    # below only when we are master
    returned = OSImage().grab(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            if hastate is True:
                Journal().queue_source_sync_by_node_name(name, request_id)
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
    returned = OSImage().push(name, request.data)
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
@token_required
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
    status, response = Journal().add_request(function="Interface.change_node_interface_by_name",object=name,payload=request.data)
    if status is True:
        status, response = Interface().change_node_interface_by_name(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
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
    status, response = Journal().add_request(function="Interface.delete_node_interface_by_name",object=name,param=interface)
    if status is True:
        status, response = Interface().delete_node_interface_by_name(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Group configuration #############################

# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group", methods=['GET'])
@token_required
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
@token_required
@validate_name
def config_group_get(name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    access_code = 404
    status, response = Group().get_group(name)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/_member", methods=['GET'])
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
    status, response = Journal().add_request(function="Group.update_group",object=name,payload=request.data)
    if status is True:
        status, response = Group().update_group(name, request.data)
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
    returned = OSImage().push(name, request.data)
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
    status, response = Journal().add_request(function="Group.clone_group",object=name,payload=request.data)
    if status is True:
        status, response = Group().clone_group(name, request.data)
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
    status, response = Journal().add_request(function="Group.delete_group_by_name",object=name)
    if status is True:
        status, response = Group().delete_group_by_name(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['GET'])
@token_required
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
    status, response = Journal().add_request(function="Interface.change_group_interface",object=name,payload=request.data)
    if status is True:
        status, response = Interface().change_group_interface(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
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
    status, response = Journal().add_request(function="Interface.delete_group_interface",object=name,param=interface)
    if status is True:
        status, response = Interface().delete_group_interface(name, interface)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# OSimage configuration #############################

@config_blueprint.route("/config/osimage", methods=['GET'])
@token_required
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
@token_required
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


@config_blueprint.route("/config/osimage/<string:name>/_member", methods=['GET'])
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


@config_blueprint.route("/config/osimagetag", methods=['GET'])
@token_required
def config_osimagetag():
    """
    Input - OS Imagetag ID or Name
    Process - Fetch the OS Image tag information.
    Output - OSImage tag Info.
    """
    access_code=404
    status, response = OSImage().get_all_osimagetags()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimagetag/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_osimagetag_get(name=None):
    """
    Input - OS Image tag ID or Name
    Process - Fetch the OS Image tag information.
    Output - OSImage tag Info.
    """
    access_code=404
    #status, response = OSImage().get_osimagetag(name)
    status, response = OSImage().get_all_osimagetags(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


# luna osimage tag already shows members. commented out for now. Antoine
#@config_blueprint.route("/config/osimagetag/<string:name>/_member", methods=['GET'])
#@token_required
#@validate_name
#def config_osimagetag_member(name=None):
#    """
#    This method will fetch all the nodes+groups, which is connected to
#    the provided osimagetag.
#    """
#    access_code=404
#    status, response = OSImage().get_osimagetag_member(name)
#    if status is True:
#        access_code = 200
#        response = dumps(response)
#    else:
#        response = {'message': response}
#    return response, access_code


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
    status, response = Journal().add_request(function="OSImage.update_osimage",object=name,payload=request.data)
    if status is True:
        status, response = OSImage().update_osimage(name, request.data)
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
    hastate=HA().get_hastate()
    if hastate is True:
        master=HA().get_role()
        if master is False:
            response={'message': 'something went wrong.....'}
            request_id = Status().gen_request_id()
            status, message = Journal().add_request(function="OSImage.clone_osimage",object=name,payload=request.data,masteronly=True,misc=request_id)
            if status is True:
                Status().add_message(request_id,"luna","request submitted to master...")
                Status().mark_messages_read(request_id)
                access_code=200
                response = {"message": "request submitted to master...", "request_id": request_id}
            else:
                response={'message': message}
            return response, access_code
    # below only when we are master
    returned = OSImage().clone_osimage(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            if hastate is True:
                Journal().queue_target_sync(name,request.data,request_id)
            response = {"message": response, "request_id": request_id}
        else:
            access_code = 201
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
    status, response = Journal().add_request(function="OSImage.delete_osimage",object=name)
    if status is True:
        status, response = OSImage().delete_osimage(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>/osimagetag/<string:tagname>/_delete", methods=['GET'])
@token_required
@validate_name
def config_osimagetag_delete(name=None, tagname=None):
    """
    Input - OS Image Name and osimagetag name
    Process - Delete the OS Imagetag belonging to osimage.
    Output - Success or Failure.
    """
    status, response = Journal().add_request(function="OSImage.delete_osimagetag",object=name,param=tagname)
    if status is True:
        status, response = OSImage().delete_osimagetag(name,tagname)
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
    hastate=HA().get_hastate()
    if hastate is True:
        master=HA().get_role()
        if master is False:
            response={'message': 'something went wrong.....'}
            request_id = Status().gen_request_id()
            status, message = Journal().add_request(function="OSImage.pack",object=name,masteronly=True,misc=request_id)
            if status is True:
                Status().add_message(request_id,"luna","request submitted to master...")
                Status().mark_messages_read(request_id)
                access_code=200
                response = {"message": "request submitted to master...", "request_id": request_id}
            else:
                response={'message': message}
            return response, access_code
    # below only when we are master
    returned = OSImage().pack(name)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            if hastate is True:
                Journal().queue_source_sync(name,request_id)
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
    access_code=404
    hastate=HA().get_hastate()
    if hastate is True:
        master=HA().get_role()
        if master is False:
            response={'message': 'something went wrong.....'}
            request_id = Status().gen_request_id()
            status, message = Journal().add_request(function="OSImage.change_kernel",object=name,payload=request.data,masteronly=True,misc=request_id)
            if status is True:
                Status().add_message(request_id,"luna","request submitted to master...")
                Status().mark_messages_read(request_id)
                access_code=200
                response = {"message": "request submitted to master...", "request_id": request_id}
            else:
                response={'message': message}
            return response, access_code
    # below only when we are master
    returned = OSImage().change_kernel(name, request.data)
    status=returned[0]
    response=returned[1]
    if status is True:
        access_code=200
        if len(returned)==3:
            request_id=returned[2]
            response = {"message": response, "request_id": request_id}
        else:
            access_code = 204
            response = {'message': response}
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osimage/<string:name>/tag", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osimage'], skip=None)
def config_osimage_tag_post(name=None):
    """
    Input - OS Image Name
    Process - Manually add/assign a tag to an image.
    Output - Tag name.
    """
    access_code=404
    status, response = Journal().add_request(function="OSImage.set_tag",object=name,payload=request.data)
    if status is True:
        status, response = OSImage().set_tag(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# Cluster configuration #############################


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/cluster", methods=['GET'])
@token_required
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
    status, response = Journal().add_request(function="Cluster.update_cluster",payload=request.data)
    if status is True:
        status, response = Cluster().update_cluster(request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# BMC setup configuration #############################

@config_blueprint.route("/config/bmcsetup", methods=['GET'])
@token_required
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
@token_required
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


@config_blueprint.route("/config/bmcsetup/<string:name>/_member", methods=['GET'])
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
    status, response = Journal().add_request(function="BMCSetup.update_bmcsetup",object=name,payload=request.data)
    if status is True:
        status, response = BMCSetup().update_bmcsetup(name, request.data)
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
    status, response = Journal().add_request(function="BMCSetup.clone_bmcsetup",object=name,payload=request.data)
    if status is True:
        status, response = BMCSetup().clone_bmcsetup(name, request.data)
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
    status, response = Journal().add_request(function="BMCSetup.delete_bmcsetup",object=name)
    if status is True:
        status, response = BMCSetup().delete_bmcsetup(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


############################# Switch configuration #############################

@config_blueprint.route("/config/switch", methods=['GET'])
@token_required
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
@token_required
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
    status, response = Journal().add_request(function="Switch.update_switch",object=name,payload=request.data)
    if status is True:
        status, response = Switch().update_switch(name, request.data)
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
    status, response = Journal().add_request(function="Switch.clone_switch",object=name,payload=request.data)
    if status is True:
        status, response = Switch().clone_switch(name, request.data)
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
    status, response = Journal().add_request(function="Switch.delete_switch",object=name)
    if status is True:
        status, response = Switch().delete_switch(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Other Devices configuration #############################

@config_blueprint.route("/config/otherdev", methods=['GET'])
@token_required
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
@token_required
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
    status, response = Journal().add_request(function="OtherDev.update_otherdev",object=name,payload=request.data)
    if status is True:
        status, response = OtherDev().update_otherdev(name, request.data)
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
    status, response = Journal().add_request(function="OtherDev.clone_otherdev",object=name,payload=request.data)
    if status is True:
        status, response = OtherDev().clone_otherdev(name, request.data)
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
    status, response = Journal().add_request(function="OtherDev.delete_otherdev",object=name)
    if status is True:
        status, response = OtherDev().delete_otherdev(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code

############################# Network configuration #############################

@config_blueprint.route("/config/network", methods=['GET'])
@token_required
def config_network():
    """
    Input - None
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    access_code=404
    status,response = Network().get_all_networks()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/network/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_network_get(name=None):
    """
    Input - Network Name
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    access_code=404
    status, response = Network().get_network(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    status, response = Journal().add_request(function="Network.update_network",object=name,payload=request.data)
    if status is True:
        status, response = Network().update_network(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
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
    status, response = Journal().add_request(function="Network.delete_network",object=name)
    if status is True:
        status, response = Network().delete_network(name)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


# Antoine - Aug 5 2023 - next API call will probably never be used, or not in context with a network?
@config_blueprint.route("/config/network/<string:name>/<string:ipaddress>", methods=['GET'])
@token_required
@validate_name
def config_network_ip(name=None, ipaddress=None):
    """
    Input - Network Name And IP Address
    Process - checks if a given ip address is free or taken for the network
    Output - Success or Failure.
    """
    access_code=404
    status, response = Network().network_ip(name, ipaddress)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/_member", methods=['GET'])
@token_required
@validate_name
def config_network_taken(name=None):
    """
    Input - Network Name
    Process - Find out all the ipaddress which is taken by the provided network.
    Output - List all taken ipaddress by the network.
    """
    access_code=404
    status, response = Network().taken_ip(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
@token_required
@validate_name
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Network.
    Output - Next Available IP on the Network.
    """
    access_code=404
    status, response = Network().next_free_ip(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code

############################# Secrets configuration #############################

@config_blueprint.route("/config/secrets", methods=['GET'])
@token_required
def config_secrets_get():
    """
    Input - None
    Output - Return the List Of All Secrets.
    """
    access_code=404
    status, response = Secret().get_all_secrets()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_node(name=None):
    """
    Input - Node Name
    Output - Return the Node Secrets And Group Secrets for the Node.
    """
    access_code=404
    status, response = Secret().get_node_secrets(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.update_node_secrets",object=name,payload=request.data)
    if status is True:
        status, response = Secret().update_node_secrets(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_node_secret(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Return the Node Secret
    """
    access_code=404
    status, response = Secret().get_node_secret(name, secret)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.update_node_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().update_node_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.clone_node_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().clone_node_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
@token_required
@validate_name
def config_node_secret_delete(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Secret.delete_node_secret",object=name,param=secret)
    if status is True:
        status, response = Secret().delete_node_secret(name, secret)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_get_secrets_group(name=None):
    """
    Input - Group Name
    Output - Return the Group Secrets.
    """
    access_code=404
    status, response = Secret().get_group_secrets(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.update_group_secrets",object=name,payload=request.data)
    if status is True:
        status, response = Secret().update_group_secrets(name, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['GET'])
@token_required
@validate_name
def config_get_group_secret(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Return the Group Secret
    """
    access_code=404
    status, response = Secret().get_group_secret(name, secret)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.update_group_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().update_group_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
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
    status, response = Journal().add_request(function="Secret.clone_group_secret",object=name,param=secret,payload=request.data)
    if status is True:
        status, response = Secret().clone_group_secret(name, secret, request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@config_blueprint.route('/config/secrets/group/<string:name>/<string:secret>/_delete', methods=['GET'])
@token_required
@validate_name
def config_group_secret_delete(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Success or Failure
    """
    status, response = Journal().add_request(function="Secret.delete_group_secret",object=name,param=secret)
    if status is True:
        status, response = Secret().delete_group_secret(name, secret)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


########### OSUSER
@config_blueprint.route("/config/osuser", methods=['GET'])
@token_required
def config_get_os_user_list():
    """
    Input - None
    Output - List of OSUsers (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().list_users()
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osuser/<string:name>", methods=['GET'])
@token_required
def config_get_os_user(name):
    """
    Input - username
    Process - Show info of OSUser (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().get_user(name)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
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
    access_code = 503
    response = "Invalid request: missing data"
    if name and name in request.json['config']['osuser']:
        userdata = request.json['config']['osuser'][name]
        status, response = OsUser().update_user(name, **userdata)
        access_code=Helper().get_access_code(status,response)
    return {'message': response}, access_code


@config_blueprint.route("/config/osuser/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_user_delete(name=None):
    """
    Input - User Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    access_code=404
    status, response = OsUser().delete_user(name)

    if status is True:
        access_code=204
    return {'message': response}, access_code

########### OSGROUP
@config_blueprint.route("/config/osgroup", methods=['GET'])
@token_required
def config_get_os_group_list():
    """
    Input - None
    Output - List of OSUsers (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().list_groups()

    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osgroup/<string:name>", methods=['GET'])
@token_required
def config_get_os_group(name):
    """
    Input - groupname
    Process - Show info of OSUser (ldap/ssd/pam).
    """
    access_code=404
    status, response = OsUser().get_group(name)

    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/osgroup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:osgroup'], skip=None)
def config_post_os_group(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update System (ldap/ssd/pam) groups.
    Output - None.
    """
    access_code = 503
    response = "Invalid request: data missing"
    if name and name in request.json['config']['osgroup']:
        groupdata = request.json['config']['osgroup'][name]
        status, response = OsUser().update_group(name, **groupdata)
        access_code=Helper().get_access_code(status,response)
    return {'message': response}, access_code


@config_blueprint.route("/config/osgroup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_post_os_group_delete(name=None):
    """
    Input - User Name
    Process - Delete System (ldap/ssd/pam) group.
    Output - None.
    """
    access_code=404
    status, response = OsUser().delete_group(name)

    if status is True:
        access_code=204
    return {'message': response}, access_code


@config_blueprint.route('/config/status/<string:request_id>', methods=['GET'])
@validate_name
def control_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """
    access_code=404
    status, response = Status().get_status(request_id)
    if status is True:
        access_code=200
        response=dumps(response)
    else:
        response={'message': response}
    return response, access_code


@config_blueprint.route('/config/dns/<string:name>', methods=['GET'])
@token_required
def get_dns(name=None):
    """
    This api will send all records for additional dns for the network.
    """
    access_code = 404
    status, response = DNS().get_dns(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@config_blueprint.route("/config/dns/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:dns'], skip=None)
def config_dns(name=None):
    """
    Input - User Name & Payload
    Process - Create Or Update additional DNS entries.
    Output - None.
    """
    status, response = Journal().add_request(function="DNS.update_dns",object=name,payload=request.data)
    if status is True:
        status, response = DNS().update_dns(name, request.data)
    access_code=Helper().get_access_code(status,response)
    return {'message': response}, access_code


@config_blueprint.route('/config/dns/<string:network>/<string:name>/_delete', methods=['GET'])
@token_required
def delete_dns(name=None,network=None):
    """
    This api deletes an additional dns entry.
    """
    access_code = 404
    status, response = Journal().add_request(function="DNS.delete_dns",object=name,param=network)
    if status is True:
        status, response = DNS().delete_dns(name,network)
    if status is True:
        access_code=204
    return {'message': response}, access_code

