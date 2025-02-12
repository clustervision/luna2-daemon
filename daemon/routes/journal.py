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
This File is a A Entry Point of Every Journal Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required, agent_check
from common.validate_input import input_filter, validate_name
from base.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
journal_blueprint = Blueprint('journal', __name__)


@journal_blueprint.route('/journal', methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['journal'], skip=None)
def journal_post(name=None):
    """
    This api will sync the journal received by other controller
    """
    status, response = Journal().update_journal(request.data)
    access_code=Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@journal_blueprint.route('/journal', methods=['GET'])
@token_required
def journal_get():
    """
    This api will generate the current journal and send it back
    """
    access_code = 404
    remote_ip = request.environ['REMOTE_ADDR']
    status, response = Journal().get_journal(remote_ip)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@journal_blueprint.route('/journal/<string:name>', methods=['GET'])
@token_required
@validate_name
def journal_get_byname(name=None):
    """
    This api will generate the current journal and send it back
    """
    access_code = 404
    status, response = Journal().get_journal(name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@journal_blueprint.route('/journal/<string:name>/_delete', methods=['GET'])
@token_required
@validate_name
def journal_del_byname(name=None):
    """
    This api will delete all host related journal entries
    """
    access_code = 404
    status, response = Journal().delete_journal(name)
    if status is True:
        access_code = 204
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code

