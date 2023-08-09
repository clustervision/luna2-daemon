#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This endpoint is serving files.
The location is defined in the configuration file,
see luna2.ini
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
    status, response = File().get_file(filename=filename, http_request=request)
    if status is True:
        access_code = 200
        return response, access_code
    else:
        access_code = Helper().get_access_code(status, response)
        response = {'message': response}
    return response, access_code
