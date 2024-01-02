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
This is a entry file for osimage configurations.
@token_required wrapper Method is used to Validate the token.
@validate_name wrapper Method is used to Validate the URI param.
@input_filter wrapper Method is used to Validate the POST data.
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
from base.osimage import OSImage
from utils.journal import Journal
from utils.helper import Helper
from utils.status import Status
from utils.ha import HA

LOGGER = Log.get_logger()
osimage_blueprint = Blueprint('config_osimage', __name__)


@osimage_blueprint.route("/config/osimage", methods=['GET'])
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


@osimage_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
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


@osimage_blueprint.route("/config/osimage/<string:name>/_member", methods=['GET'])
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


@osimage_blueprint.route("/config/osimagetag", methods=['GET'])
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


@osimage_blueprint.route("/config/osimagetag/<string:name>", methods=['GET'])
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
#@osimage_blueprint.route("/config/osimagetag/<string:name>/_member", methods=['GET'])
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


@osimage_blueprint.route("/config/osimage/<string:name>", methods=['POST'])
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
@osimage_blueprint.route("/config/osimage/<string:name>/_clone", methods=['POST'])
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


@osimage_blueprint.route("/config/osimage/<string:name>/_delete", methods=['GET'])
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


@osimage_blueprint.route("/config/osimage/<string:name>/osimagetag/<string:tagname>/_delete", methods=['GET'])
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
@osimage_blueprint.route("/config/osimage/<string:name>/_pack", methods=['GET'])
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


@osimage_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
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


@osimage_blueprint.route("/config/osimage/<string:name>/tag", methods=['POST'])
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
