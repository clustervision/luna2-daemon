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

"""

from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request, send_file, json
from utils.log import *
from utils.files import *

logger = Log.get_logger()
files_blueprint = Blueprint('files', __name__)


"""
/files will provide the list of tar files inside the tar file directory 
"""
@files_blueprint.route("/files", methods=['GET'])
@validate_access
def files(**kwargs):
    if "access" in kwargs:
        access = "admin"
    filelist = Files().list_files()
    if filelist:
        logger.info("This is Files API.")
        return filelist
    else:
        response = {"message": "Nothing is present."}
        code = 200
        return json.dumps(response), code


"""
/files will receive the tar file COMPLETE name.
Return the Tar File.
"""
@files_blueprint.route("/files/<string:filename>", methods=['GET'])
@validate_access
def files_get(filename=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
    if filename:
        filepath = Files().check_file(filename)
        if filepath:
            return send_file(filepath, as_attachment=True)
        else:
            response = "File {}, is not present.".format(filename)
            code = 200
            return json.dumps(response), code
        logger.info("This is Files GET API File Name is: {}".format(filename))
        response = {"message": "This is Files GET API File Name is: {}".format(filename)}
        code = 200
    else:
        logger.error("File Name is Missing.")
        response = {"message": "File Name is Missing."}
        code = 200
    return json.dumps(response), code
