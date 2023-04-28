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

from flask import Flask, abort, json, Response, request
from common.constant import LOGGER
from common.bootstrap import validatebootstrap
from utils.housekeeper import Housekeeper 
from utils.service import Service
import concurrent.futures
from threading import Event
from apis.auth import auth_blueprint
from apis.boot import boot_blueprint
from apis.config import config_blueprint
from apis.files import files_blueprint
from apis.service import service_blueprint
from apis.monitor import monitor_blueprint
from apis.control import control_blueprint

event = Event()

############# Gunicorn Server Hooks #############

def on_starting(server):
    """
    A Testing Method for Gunicorn on_starting.
    """
    result=validatebootstrap()
    if result is False:
        exit(1)
    # we generate initial dhcpd and dns configs
    Service().luna_service('dhcp', 'restart')
    Service().luna_service('dns', 'restart')
    # --------------- status message cleanup thread ----------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().cleanup_mother,event)
    executor.shutdown(wait=False)
    # ----------------- queue housekeeper thread -------------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().tasks_mother,event)
    executor.shutdown(wait=False)
    # --------------------------------------------------------------
    LOGGER.info(vars(server))
    LOGGER.info('Gunicorn server hook on start')
    return True


def on_reload(server):
    """
    A Testing Method for Gunicorn on_reload.
    """
    LOGGER.info(vars(server))
    LOGGER.info('Gunicorn server hook on reload')
    return True


def on_exit(server):
    """
    A Testing Method for Gunicorn on_reload.
    """
    event.set()  # stops the threads like cleanup
    LOGGER.info(vars(server))
    LOGGER.info('Gunicorn server hook on exit')
    return True

############# debug traces ######################

def worker_abort(worker):
    import traceback, io
    debug_info = io.StringIO()
    debug_info.write("Traceback at time of timeout:\n")
    traceback.print_stack(file=debug_info)
    worker.log.critical(debug_info.getvalue())
    LOGGER.error(debug_info.getvalue())

############# Gunicorn Server Hooks #############


api = Flask(__name__)
api.register_blueprint(auth_blueprint)
api.register_blueprint(boot_blueprint)
api.register_blueprint(config_blueprint)
api.register_blueprint(files_blueprint)
api.register_blueprint(service_blueprint)
api.register_blueprint(monitor_blueprint)
api.register_blueprint(control_blueprint)


@api.route('/all-routes')
def all_routes():
    """This method will print all the API"""
    routes = []
    for rule in api.url_map.iter_rules():
        apimethod = str(rule.methods).replace("'", "")
        apimethod = apimethod.replace("}", "")
        apimethod = apimethod.replace("{", "")
        apimethod = apimethod.replace("HEAD", "")
        apimethod = apimethod.replace("OPTIONS", "")
        apimethod = apimethod.replace(", ", "")
        route = f"http://{request.environ['HTTP_HOST']}{rule}"
        if "static" != str(rule.endpoint):
            routes.append({"route": route, "function": str(rule.endpoint), "method": apimethod})
    LOGGER.info(routes)
    return routes, 200


@api.route('/version', methods=['GET'])
def files():
    """
    This Method will provide the current version of the Luna Daemon Application.
    """
    # version_file = 'version.txt'
    # try:
    #     with open(version_file, 'r', encoding='utf-8') as ver:
    #         version = ver.read()
    # except OSError:
    #     version = "Error :: Not Available"
    version = '711e3a5---DUMMY---278ad6399b'
    response = {'version': {'luna': '2.0.0001', 'api': 1, 'commit': version }}
    access_code = 200
    return json.dumps(response), access_code


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
