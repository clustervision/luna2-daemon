#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is a Main File Luna 2 Daemon Service.
This File will Initiate the Logger and A Entry Point to the API's
Some Of Default Error Handler is defaine here such as 404, 400, etc.
Getting the Constants from common/constant.py File
To Generate the Application Security Key -> python -c "import secrets; print(secrets.token_hex())"
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from flask import Flask, abort, json, Response
from common.constant import CONSTANT
from utils.log import Log
LOGGER = Log.init_log(CONSTANT['LOGGER']['LEVEL'])

from common.bootstrap import validatebootstrap
from utils.templates import Templates

from apis.auth import auth_blueprint
from apis.boot import boot_blueprint
from apis.config import config_blueprint
from apis.files import files_blueprint
from apis.service import service_blueprint
from apis.monitor import monitor_blueprint


validatebootstrap()
TEMP = Templates().validate()

def on_starting(server):
    """
    A Testing Method for Gunicorn on_starting.
    """
    LOGGER.info(vars(server))
    LOGGER.info('Templates Check On Start')
    return True

def on_reload(server):
    """
    A Testing Method for Gunicorn on_reload.
    """
    LOGGER.info(vars(server))
    LOGGER.info('Templates Check On Start')
    return True


api = Flask(__name__)
api.register_blueprint(auth_blueprint)
api.register_blueprint(boot_blueprint)
api.register_blueprint(config_blueprint)
api.register_blueprint(files_blueprint)
api.register_blueprint(service_blueprint)
api.register_blueprint(monitor_blueprint)


@api.route('/')
def main():
    """ Abort Main Route"""
    abort(404, None)


@api.errorhandler(400)
def bad_request():
    """ Abort All 400"""
    error = {'message': 'Bad Requests'}
    return json.dumps(error), 400


@api.errorhandler(401)
def unauthorized():
    """ Abort All 401"""
    error = {'message': 'Unauthorized'}
    return json.dumps(error), 401


@api.errorhandler(404)
def page_not_found(error):
    """ Abort All 404"""
    if error:
        response = Response(status=404)
    else:
        error = {'message': 'Route Not Found'}
        response = json.dumps(error), 404
    return response


@api.errorhandler(500)
def server_error():
    """ Abort All 500"""
    error = {'message': 'Server Error'}
    return json.dumps(error), 500


@api.errorhandler(503)
def service_unavailable(error):
    """ Abort All 503"""
    error = {'message': f'{error} Service Unavailable'}
    return json.dumps(error), 503


# api.run(host='0.0.0.0', port=7050, debug=True)
