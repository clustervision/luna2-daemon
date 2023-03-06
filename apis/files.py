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

from flask import Blueprint, request, send_file, json
from utils.log import Log
from utils.files import Files
from utils.database import Database
from common.constant import CONSTANT
import os

LOGGER = Log.get_logger()
files_blueprint = Blueprint('files', __name__)


@files_blueprint.route('/files', methods=['GET'])
def files():
    """
    Input - None
    Process - Search TARBALLS for *.tar.gz. *.tar.bz2 files.
    Output - List of available files.
    """
    filelist = Files().list_files()
    if filelist:
        LOGGER.info(f'Available tar file in {CONSTANT["FILES"]["TARBALL"]} are {filelist}.')
        return filelist, 200
    else:
        LOGGER.error(f'No tar file is present in {CONSTANT["FILES"]["TARBALL"]}.')
        response = {'message': f'No tar file is present in {CONSTANT["FILES"]["TARBALL"]}.'}
        code = 503
        return json.dumps(response), code


@files_blueprint.route('/files/<string:filename>', methods=['GET'])
def files_get(filename=None):
    """
    Input - Filename
    Process - Make available file to download.
    Output - File
    """
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        request_ip = request.environ['REMOTE_ADDR']
    else:
        request_ip = request.environ['HTTP_X_FORWARDED_FOR']

    response = {'message': ''}
    code=500
    LOGGER.debug(f'Request for file: {filename} from IP Address: {request_ip}')
    nodeinterface = Database().get_record_join(['nodeinterface.nodeid'], ['ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"ipaddress.ipaddress='{request_ip}'"])
    if node_interface:
        row = [{"column": "status", "value": "installer.discovery"}]
        where = [{"column": "id", "value": node_interface[0]["id"]}]
        Database().update('node', row, where)
    filepath = Files().check_file(filename)
    if filepath:
        LOGGER.info(f'Tar File Path is {filepath}.')
        return send_file(filepath, as_attachment=True), 200
    else:
        LOGGER.error(f'{filename} is not present in {CONSTANT["FILES"]["TARBALL"]}.')
        response = {'message': f'{filename} is not present in {CONSTANT["FILES"]["TARBALL"]}.'}
        code = 503
    return json.dumps(response), code

