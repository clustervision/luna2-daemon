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
This File is a A Entry Point of Every H/A Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required, agent_check
from common.validate_input import input_filter, validate_name
from utils.ha import HA
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
ha_blueprint = Blueprint('ha', __name__)


@ha_blueprint.route('/ping', methods=['GET'])
#@token_required
def ha_ping():
    """
    This api will just send pong back
    """
    access_code=200
    response = {'message': 'pong'}
    return response, access_code


@ha_blueprint.route('/ha/master/_set', methods=['GET'])
@token_required
def ha_set_master(cli=None, name=None):
    """
    This api will set the current host as master.
    """
    access_code = 404
    status, response = Journal().add_request(function="HA.set_role",object=False)
    if status is True:
        role = HA().set_role(True)
        if role is True: # meaning it's what i asked for
            access_code = 200
            response="current role set to master"
        else:
            access_code = 503
            response="could not set role to master"
    response = {'message': response}
    return response, access_code


@ha_blueprint.route('/ha/master', methods=['GET'])
@token_required
def ha_get_master():
    """
    This api will set the current host as master.
    """
    access_code = 404
    response = HA().get_role()
    if response:
        access_code = 200
    response = {'message': response}
    return response, access_code


@ha_blueprint.route('/ha/state', methods=['GET'])
@token_required
def ha_get_state():
    """
    This api will set the current host as master.
    """
    access_code = 404
    response = HA().get_full_state()
    if response:
        access_code = 200
        response = {'ha': response}
    else:
        response = {'message': 'HA not available'}
    return response, access_code


@ha_blueprint.route('/ha/syncimage/<string:name>', methods=['GET'])
@token_required
@validate_name
def ha_sync_image(name=None):
    """
    This api will set the current host as master.
    """
    access_code = 404
    response = "sync not available for images"
    ha_object=HA()
    if ha_object.get_syncimages() is True:
        status, response = Journal().add_request(function='Downloader.pull_image_data',object=name,param=ha_object.get_me())
        if status is True:
            access_code = 201
            response=f"image sync for {name} added to journal"
    response = {'message': response}
    return response, access_code

