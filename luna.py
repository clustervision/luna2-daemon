#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a Main File Luna 2 Daemon Service.
This File will Initiate the Logger and A Entry Point to the API's
Some Of Default Error Handler is defaine here such as 404, 400, etc.
Getting the Constants from common/constant.py File
#### To Generate the Application Security Key -> python -c 'import secrets; print(secrets.token_hex())'
"""

from flask import Flask, request, abort, json
from utils.log import *
from common.constants import *



if len(sys.argv) == 2:
    log_level = str(sys.argv[1])
    if log_level == "--debug":
        log_level = log_level.replace("--", "")
        LEVEL = log_level
    else:
        LEVEL = "critical"

Log.init_log(LEVEL)
# logger = Log.get_logger()


from apis.auth import auth_blueprint
from apis.boot import boot_blueprint
from apis.config import config_blueprint
from apis.files import files_blueprint
from apis.service import service_blueprint
from apis.monitor import monitor_blueprint
# global api
api = Flask(__name__)
api.register_blueprint(auth_blueprint)
api.register_blueprint(boot_blueprint)
api.register_blueprint(config_blueprint)
api.register_blueprint(files_blueprint)
api.register_blueprint(service_blueprint)
api.register_blueprint(monitor_blueprint)


@api.route('/')
def main():
    abort(404)


@api.errorhandler(400)
def bad_request(e):
    error = {"message": "Bad Requests"}
    return json.dumps(error), 401


@api.errorhandler(401)
def unauthorized(e):
    error = {"message": "Unauthorized"}
    return json.dumps(error), 401


@api.errorhandler(404)
def page_not_found(e):
    error = {"message": "Route Not Found"}
    return json.dumps(error), 404


@api.errorhandler(500)
def server_error(e):
    error = {"message": "Server Error"}
    return json.dumps(error), 500


@api.errorhandler(503)
def service_unavailable(e, msg):
    error = {"message": msg + " Service Unavailable"}
    return json.dumps(error), 503


if __name__ == "__main__":
    api.run(host=SERVERIP, port=SERVERPORT, debug=True)