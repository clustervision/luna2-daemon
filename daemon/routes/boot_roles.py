#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2024  ClusterVision Solutions b.v.
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
This File is a A Entry Point of Every Role related requests
@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2024, Luna2 Project"
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
from base.boot_roles import Roles
from utils.helper import Helper

LOGGER = Log.get_logger()
roles_blueprint = Blueprint('roles', __name__)


@roles_blueprint.route('/boot/roles/<string:role>', methods=['GET'])
@token_required
@validate_name
def get_role(role=None):
    """
    Input - Role name
    Process - Calls the function that returns the target and role script for the role
    Output - json payload with target and base64 encoded script data
    """
    access_code = 404
    status, response = Roles().get_role(role)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code

