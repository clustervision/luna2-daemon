
# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Routes for the firmware catalogue and for asking what a push would do.

The preview routes are reads and contact nothing, so they are cheap enough to ask
about a whole cluster and answer for machines that are switched off.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2026, Luna2 Project"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.firmware import Firmware
from utils.journal import Journal
from utils.helper import Helper


LOGGER = Log.get_logger()
firmware_blueprint = Blueprint('config_firmware', __name__)


@firmware_blueprint.route("/config/firmwarecatalog", methods=['GET'])
@token_required
def config_firmware():
    """
    Input - None
    Output - Every entry in the firmware catalogue.
    """
    access_code = 404
    status, response = Firmware().get_all_firmware()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@firmware_blueprint.route("/config/firmwarecatalog/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_firmware_get(name=None):
    """
    Input - Catalogue entry name
    Output - That entry.
    """
    access_code = 404
    status, response = Firmware().get_firmware(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@firmware_blueprint.route("/config/firmwarecatalog/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:firmwarecatalog'], skip=None)
def config_firmware_post(name=None):
    """
    Input - Catalogue entry name and its fields
    Output - Creates or changes one entry.
    """
    status, response = Journal().add_request(function="Firmware.update_firmware",
                                             object=name, payload=request.data)
    if status is True:
        status, response = Firmware().update_firmware(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@firmware_blueprint.route("/config/firmwarecatalog/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_firmware_delete(name=None):
    """
    Input - Catalogue entry name
    Output - Removes that entry.
    """
    status, response = Journal().add_request(function="Firmware.delete_firmware",
                                             object=name)
    if status is True:
        status, response = Firmware().delete_firmware(name)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@firmware_blueprint.route("/config/node/<string:name>/firmware/_preview", methods=['GET'])
@token_required
@validate_name
def config_firmware_preview_node(name=None):
    """
    Input - Node name
    Output - What a firmware push would do to it, and why it would not. No BMC is
             contacted, so this answers for a machine that is switched off.
    """
    return _preview('node', name)


@firmware_blueprint.route("/config/group/<string:name>/firmware/_preview", methods=['GET'])
@token_required
@validate_name
def config_firmware_preview_group(name=None):
    """
    Input - Group name
    Output - The same, per node, grouped by cause. A group can hold several
             platforms, so the answer differs between its members and the summary
             counts causes rather than listing nodes.
    """
    return _preview('group', name)


def _preview(object_type=None, name=None):
    """
    Both preview routes, which differ only in what they are aimed at.
    """
    access_code = 404
    status, response = Firmware().preview(object_type=object_type, name=name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@firmware_blueprint.route("/config/node/<string:name>/_firmwarepush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:node'], skip=None)
def config_firmware_push_node(name=None):
    """
    Input - Node name, optionally a single component
    Output - Records the update and hands back the request id.
    """
    return _firmwarepush('node', name)


@firmware_blueprint.route("/config/group/<string:name>/_firmwarepush", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:group'], skip=None)
def config_firmware_push_group(name=None):
    """
    Input - Group name, optionally a single component
    Output - The same, for every member the catalogue covers.
    """
    return _firmwarepush('group', name)


def _firmwarepush(object_type=None, name=None):
    """
    Both push routes, which differ only in what they are aimed at.

    The work is recorded and the request id comes back at once: a component takes
    minutes and a board can need several, so holding the request open would mean
    holding it for the better part of an hour.
    """
    returned = Firmware().push_firmware(object_type=object_type, name=name,
                                        request_data=request.data)
    status, response = returned[0], returned[1]
    if status is True and len(returned) == 3:
        return {'message': response, 'request_id': returned[2]}, 200
    return {'message': response}, Helper().get_access_code(status, response)


@firmware_blueprint.route("/config/firmwarecatalog/status", methods=['GET'])
@token_required
def config_firmware_status():
    """
    Input - None
    Output - What became of every firmware update that was asked for.
    """
    return _firmware_status()


@firmware_blueprint.route("/config/firmwarecatalog/status/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_firmware_status_node(name=None):
    """
    Input - Node name
    Output - The same, for one node.
    """
    return _firmware_status(name=name)


@firmware_blueprint.route("/config/firmwarecatalog/status/group/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_firmware_status_group(name=None):
    """
    Input - Group name
    Output - The same, for every node of that group.
    """
    return _firmware_status(group=name)


def _firmware_status(name=None, group=None):
    """
    All three status routes, which differ only in what was asked about.
    """
    access_code = 404
    status, response = Firmware().status(name=name, group=group)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code
