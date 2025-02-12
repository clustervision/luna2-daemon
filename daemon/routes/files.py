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
This endpoint is serving files.
The location is defined in the configuration file,
see luna2.ini
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

from json import dumps
from flask import Blueprint, request
from utils.log import Log
from base.file import File
from utils.helper import Helper

LOGGER = Log.get_logger()
files_blueprint = Blueprint('files', __name__)


@files_blueprint.route('/files', methods=['GET'])
def files():
    """
    Input - None
    Process - Search IMAGE_FILES for *.tar.gz. *.tar.bz2 files.
    Output - List of available files.
    """
    access_code = 503
    status, response = File().get_files_list()
    if status is True:
        access_code=200
        response = dumps(response)
    else:
        access_code = Helper().get_access_code(status, response)
        response = {'message': response}
    return response, access_code


@files_blueprint.route('/files/<string:filename>', methods=['GET'])
def files_get(filename=None):
    """
    Input - Filename
    Process - Make available file to download.
    Output - File
    """
    access_code = 503
    request_ip = None
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        request_ip = request.environ['REMOTE_ADDR']
    else:
        request_ip = request.environ['HTTP_X_FORWARDED_FOR']

    status, response = File().get_file(filename=filename, request_headers=request.headers, request_ip=request_ip)
    if status is True:
        access_code = 200
        return response, access_code
    else:
        access_code = Helper().get_access_code(status, response)
        response = {'message': response}
    return response, access_code
