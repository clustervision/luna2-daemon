#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is Serving the TarBalls Files.
TarBalls Default Location is mentioned in Conf file.

"""

from common.validate_auth import *
from flask import Blueprint, request, send_file, json
from utils.log import *
from utils.files import *

logger = Log.get_logger()
files_blueprint = Blueprint('files', __name__)


"""
Input - None
Process - Search TARBALLS for *.tar.gz. *.tar.bz2 files. 
Output - List of available files.
"""
@files_blueprint.route("/files", methods=['GET'])
def files():
    filelist = Files().list_files()
    if filelist:
        logger.info("Available Tar file in {} are {}.".format(CONSTANT["FILES"]["TARBALL"], str(filelist)))
        return filelist, 200
    else:
        logger.error("No Tar file is present in {}.".format(CONSTANT["FILES"]["TARBALL"]))
        response = {"message": "No Tar file is present in {}.".format(CONSTANT["FILES"]["TARBALL"])}
        code = 503
        return json.dumps(response), code


"""
Input - Tar File Name
Process - Make Available File to Download. 
Output - File
"""
@files_blueprint.route("/files/<string:filename>", methods=['GET'])
def files_get(filename=None):
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        REQUESTIP = request.environ['REMOTE_ADDR']
    else:
        REQUESTIP = request.environ['HTTP_X_FORWARDED_FOR']
    NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE ipaddress = "{REQUESTIP}"')
    if NODEINTERFACE:
        row = [{"column": "status", "value": "installer.discovery"}]
        where = [{"column": "id", "value": NODEINTERFACE[0]["id"]}]
        Database().update('node', row, where)
    filepath = Files().check_file(filename)
    if filepath:
        logger.info("Tar File Path is {}.".format(filepath))
        return send_file(filepath, as_attachment=True), 200
    else:
        logger.error("Tar File {} Is Not Present in Directory {}.".format(filename, CONSTANT["FILES"]["TARBALL"]))
        response = "Tar File {} Is Not Present in Directory {}.".format(filename, CONSTANT["FILES"]["TARBALL"])
        code = 503
        return json.dumps(response), code
    return json.dumps(response), code
