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
This File is a Main File Luna 2 Daemon Service.
This File will Initiate the Logger and A Entry Point to the API's
Some Of Default Error Handler is define here such as 404, 400, etc.
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

import sys
import concurrent.futures
from threading import Event
import traceback
from io import StringIO
from flask import Flask, abort, json, Response, request
from common.constant import LOGGER
from common.bootstrap import validate_bootstrap
from utils.housekeeper import Housekeeper
from utils.service import Service
from routes.auth import auth_blueprint
from routes.boot import boot_blueprint
from routes.config import config_blueprint
from routes.files import files_blueprint
from routes.service import service_blueprint
from routes.monitor import monitor_blueprint
from routes.control import control_blueprint
from routes.tracker import tracker_blueprint
from routes.journal import journal_blueprint

event = Event()

############# Gunicorn Server Hooks #############

def on_starting(server):
    """
    A Testing Method for Gunicorn on_starting.
    """
    result = validate_bootstrap()
    if result is False:
        sys.exit(1)
    # we generate initial dhcpd and dns configs
    Service().luna_service('dhcp', 'restart')
    Service().luna_service('dns', 'restart')
    # --------------- status message cleanup thread ----------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().cleanup_mother, event)
    executor.shutdown(wait=False)
    # ----------------- queue housekeeper thread -------------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().tasks_mother, event)
    executor.shutdown(wait=False)
    # ------------- switch/port/mac detection thread ---------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().switchport_scan, event)
    executor.shutdown(wait=False)
    # --------------- journal / replication thread -----------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    executor.submit(Housekeeper().journal_mother, event)
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
    """
    This Gunicorn Method will help while debugging.
    """
    debug_info = StringIO()
    debug_info.write("Traceback at time of timeout:\n")
    traceback.print_stack(file=debug_info)
    worker.log.critical(debug_info.getvalue())
    LOGGER.error(debug_info.getvalue())

############# Gunicorn Server Hooks #############


daemon = Flask(__name__)
daemon.register_blueprint(auth_blueprint)
daemon.register_blueprint(boot_blueprint)
daemon.register_blueprint(config_blueprint)
daemon.register_blueprint(files_blueprint)
daemon.register_blueprint(service_blueprint)
daemon.register_blueprint(monitor_blueprint)
daemon.register_blueprint(control_blueprint)
daemon.register_blueprint(tracker_blueprint)
daemon.register_blueprint(journal_blueprint)
daemon.register_blueprint(ha_blueprint)


@daemon.route('/all-routes')
def all_routes():
    """This method will print all the API"""
    routes = []
    for rule in daemon.url_map.iter_rules():
        method = str(rule.methods).replace("'", "")
        method = method.replace("}", "")
        method = method.replace("{", "")
        method = method.replace("HEAD", "")
        method = method.replace("OPTIONS", "")
        method = method.replace(", ", "")
        route = f"http://{request.environ['HTTP_HOST']}{rule}"
        if "static" != str(rule.endpoint):
            routes.append({"route": route, "function": str(rule.endpoint), "method": method})
    LOGGER.debug(routes)
    return routes, 200


@daemon.route('/version', methods=['GET'])
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


@daemon.route('/')
def main():
    """ Abort Main Route"""
    abort(404, None)


@daemon.errorhandler(400)
def bad_request():
    """ Abort All 400"""
    error = {'message': 'Bad Requests'}
    return json.dumps(error), 400


@daemon.errorhandler(401)
def unauthorized():
    """ Abort All 401"""
    error = {'message': 'Unauthorized'}
    return json.dumps(error), 401


@daemon.errorhandler(404)
def page_not_found(error):
    """ Abort All 404"""
    if error:
        response = Response(status=404)
    else:
        error = {'message': 'Route Not Found'}
        response = json.dumps(error), 404
    return response


@daemon.errorhandler(500)
def server_error():
    """ Abort All 500"""
    error = {'message': 'Server Error'}
    return json.dumps(error), 500


@daemon.errorhandler(503)
def service_unavailable(error):
    """ Abort All 503"""
    error = {'message': f'{error} Service Unavailable'}
    return json.dumps(error), 503
