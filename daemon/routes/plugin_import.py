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
This file provides end points for exporting config.
Plugins are responsible for handling the actual data
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2024, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from flask import Blueprint, request
from json import dumps,loads
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import validate_name
from utils.journal import Journal
from base.plugin_import import Import

LOGGER = Log.get_logger()
import_blueprint = Blueprint('import', __name__)


@import_blueprint.route('/import/<string:name>', methods=['POST'])
@token_required
@validate_name
def import_data(name=None):
    """
    This api receives the request to call a specific plugin (in base) and forwards data as is
    """
    access_code=200
    try:
       payload = loads(request.data)
    except:
       payload = request.data
    status, response = Journal().add_request(function="Import.plugin", object=name, payload=payload)
    if status is True:
        status, response = Import().plugin(name, payload)
        if status is True:
            return response, access_code
    access_code=404
    response = {'message': response}
    return response, access_code


