#!/usr/bin/env python3

import os
import sys
import logging
import configparser
from flask import  Flask, request, url_for, json
from utils.log import *
from common.constants import *
from utils.helper import *
# from utils.service import *
# from utils.files import *

if len(sys.argv) == 2:
    log_level = str(sys.argv[1])
    if log_level == "--debug":
        log_level = log_level.replace("--", "")
        LEVEL = log_level
    else:
        LEVEL = "critical"

Log.init_log(LEVEL)
logger = Log.get_logger()
# logger.warning("This is warning.")
# logger.debug("This is debug.")
# logger.info("This is info.")
# logger.critical("This is critical.")


# from flask import Flask, request, abort, json
from apis.boot import boot_blueprint
from apis.config import config_blueprint
from apis.files import files_blueprint
from apis.service import service_blueprint
from apis.monitor import monitor_blueprint
api = Flask(__name__)
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