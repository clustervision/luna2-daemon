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
Entry file for the local artefact checksums.

Read-only, and deliberately so: these describe files on this controller, and are
written where those files are produced or pulled. There is no POST and no
_delete - a hash is retired by removing the artefact it describes, which
cleanup_file already does.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from json import dumps
from flask import Blueprint
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import validate_name
from base.hashes import Hashes

LOGGER = Log.get_logger()
hash_blueprint = Blueprint('config_hash', __name__)


@hash_blueprint.route('/hash', methods=['GET'])
@token_required
def config_hash_list():
    """
    Output - every artefact checksum this controller holds
    """
    access_code = 404
    status, response = Hashes().get_hashes()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@hash_blueprint.route('/hash/<string:object_type>/<string:name>', methods=['GET'])
@token_required
@validate_name
def config_hash_object(object_type=None, name=None):
    """
    Input - object kind and its name, e.g. osimage/compute
    Output - every checksum held for that object
    """
    access_code = 404
    status, response = Hashes().get_hashes(object_type, name)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@hash_blueprint.route('/hash/<string:object_type>/<string:name>/<string:file>', methods=['GET'])
@token_required
@validate_name
def config_hash_get(object_type=None, name=None, file=None):
    """
    Input - object kind, name and artefact filename
    Output - the checksum of that one artefact, or 404 when none is held
    """
    access_code = 404
    status, response = Hashes().get_hash(object_type, name, file)
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code
