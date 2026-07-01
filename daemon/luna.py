#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import sys
import fcntl
import concurrent.futures
from threading import Event
import traceback
from time import sleep
from io import StringIO
from flask import Flask, abort, json, Response, request
from common.constant import LOGGER, CONSTANT
from common.bootstrap import validate_bootstrap
from utils.housekeeper import Housekeeper
from utils.plugin_sync import PluginSync
from utils.service import Service
from utils.helper import Helper
from utils.queue import Queue
from routes.auth import auth_blueprint
from routes.boot import boot_blueprint
from routes.boot_roles import roles_blueprint
from routes.boot_scripts import scripts_blueprint
from routes.config_bmcsetup import bmcsetup_blueprint
from routes.config_cluster import cluster_blueprint
from routes.config_dns import dns_blueprint
from routes.config_route import route_blueprint
from routes.config_group import group_blueprint
from routes.config_network import network_blueprint
from routes.config_node import node_blueprint
from routes.config_osgroup import osgroup_blueprint
from routes.config_osimage import osimage_blueprint
from routes.config_osuser import osuser_blueprint
from routes.config_otherdev import otherdev_blueprint
from routes.config_secrets import secrets_blueprint
from routes.config_status import status_blueprint
from routes.config_switch import switch_blueprint
from routes.config_cloud import cloud_blueprint
from routes.config_rack import rack_blueprint
from routes.files import files_blueprint
from routes.service import service_blueprint
from routes.monitor import monitor_blueprint
from routes.control import control_blueprint
from routes.tracker import tracker_blueprint
from routes.journal import journal_blueprint
from routes.tables import tables_blueprint
from routes.plugin_export import export_blueprint
from routes.plugin_import import import_blueprint
from routes.ha import ha_blueprint

event = Event()
BACKGROUND_LOCKFILE = '/var/lib/luna2-daemon-background.lock'

############# Helper functions ##################

background_futures = []
background_lock_handle = None
background_started = False

def register_future(executor, future):
    background_futures.append((executor, future))
    return future


def clear_background_futures():
    background_futures.clear()


def _is_default_hook(cfg, hook_name):
    hook = getattr(cfg, hook_name, None)
    return (
        getattr(hook, '__module__', '') == 'gunicorn.config'
        and getattr(hook, '__name__', '') == hook_name
    )


def inject_compat_hooks(cfg):
    """
    Backfill newer Gunicorn hooks when an older gunicorn.py did not define them.
    This allows luna.py to support both old and new gunicorn.py files.
    """
    hook_map = {
        'post_worker_init': post_worker_init,
        'worker_exit': worker_exit,
        'on_reload': on_reload,
        'on_exit': on_exit,
        'worker_abort': worker_abort,
    }
    for hook_name, hook_fn in hook_map.items():
        if _is_default_hook(cfg, hook_name):
            cfg.set(hook_name, hook_fn)
            LOGGER.info(f'Injected compatibility hook {hook_name} -> luna.{hook_name}')


def start_background_workers():
    """
    Start Luna singleton background workers after Gunicorn forks a worker.
    One worker is elected using a non-blocking file lock.
    """
    global background_lock_handle
    global background_started

    if background_started:
        LOGGER.info('Background workers already started in this process')
        return True

    event.clear()
    background_lock_handle = open(BACKGROUND_LOCKFILE, 'a+', encoding='utf-8')
    try:
        fcntl.flock(background_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        LOGGER.info(f'Worker pid {os.getpid()} is not the background owner')
        return False

    # --------------- status message cleanup thread ----------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().cleanup_mother, event))
    # ----------------- queue housekeeper thread -------------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().tasks_mother, event))
    # ------------- switch/port/mac detection thread ---------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().switchport_scan, event))
    # -------------- boot plugin sync watcher thread ---------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(PluginSync().boot_plugins_mother, event))
    # --------------- journal / replication thread -----------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().journal_mother, event))
    # ----------------- invalid config thread ----------------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().invalid_config_mother, event))
    # ----------------- osimage tasks thread -----------------------
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    register_future(executor, executor.submit(Housekeeper().osimage_tasks_mother, event))
    # --------------------------------------------------------------
    background_started = True
    LOGGER.info(f'Background workers started in pid {os.getpid()}')
    return True


def stop_background_workers(wait_for_queue=False):
    """
    Stop Luna singleton background workers from the owning worker process.
    """
    global background_lock_handle
    global background_started

    if not background_started:
        return True

    event.set()
    if wait_for_queue:
        Queue().wait_for_queue_drain()
    for executor, future in background_futures:
        try:
            future.result(timeout=10)
        except Exception as exp:
            LOGGER.warning(f"Background future shutdown issue: {exp}")
        try:
            executor.shutdown(wait=False)
        except Exception as exp:
            LOGGER.warning(f"Executor shutdown issue: {exp}")
    clear_background_futures()
    try:
        if background_lock_handle is not None:
            fcntl.flock(background_lock_handle.fileno(), fcntl.LOCK_UN)
            background_lock_handle.close()
    except Exception as exp:
        LOGGER.warning(f"Background lock cleanup issue: {exp}")
    background_lock_handle = None
    background_started = False
    return True


############# Gunicorn Server Hooks #############

def on_starting(server):
    """
    A Testing Method for Gunicorn on_starting.
    """
    inject_compat_hooks(server.cfg)
    result = validate_bootstrap()
    if result is False:
        sys.exit(1)
    # we generate initial dhcpd and dns configs
    try:
        Queue().add_task_to_queue(task='restart', param='dhcp',
                                  subsystem='housekeeper', request_id='__luna start__')
        Queue().add_task_to_queue(task='restart', param='dhcp6',
                                  subsystem='housekeeper', request_id='__luna start__')
        Queue().add_task_to_queue(task='reload', param='dns',
                                  subsystem='housekeeper', request_id='__luna start__')
        Queue().add_task_to_queue(task='only_start', param='dns',
                                  subsystem='housekeeper', request_id='__luna start__')

        # we no longer do this here as to allow syncs first. also quicker startup
        #Service().luna_service('dhcp', 'restart')
        #Service().luna_service('dhcp6', 'restart')
        #Service().luna_service('dns', 'reload')
        #Service().luna_service('dns', 'start')
    except Exception as exp:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        sys.stderr.write(f"ERROR: Restarting services returned an exception: {exp}, {exc_type}, in {exc_tb.tb_lineno}\n")
    # we call the startup hook plugin
    try:
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        hooks_plugins = Helper().plugin_finder(f'{plugins_path}/hooks')
        hook_plugin = Helper().plugin_load(
            hooks_plugins,
            'hooks/luna',
            'default'
        )
        status, message = hook_plugin().startup(Helper().nodes_and_groups())
        if not status:
            sys.stderr.write(f"ERROR: Startup hook plugin returned: {status}, {message}\n")
    except Exception as exp:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        sys.stderr.write(f"ERROR: Startup hook plugin returned an exception: {exp}, {exc_type}, in {exc_tb.tb_lineno}\n")
    LOGGER.info(vars(server))
    LOGGER.info('Gunicorn server hook on start')
    return True


def post_worker_init(worker):
    """
    Start singleton background workers after fork in one elected worker.
    """
    LOGGER.info(f'post_worker_init called for worker pid {worker.pid} age {worker.age}')
    start_background_workers()
    return True


def worker_exit(server, worker):
    """
    Stop singleton background workers when the owning worker exits.
    """
    LOGGER.info(f'worker_exit called for worker pid {worker.pid} age {worker.age}')
    stop_background_workers(wait_for_queue=False)
    return True


def on_reload(server):
    """
    A Testing Method for Gunicorn on_reload.
    """
    LOGGER.info(vars(server))
    Queue().wait_for_queue_drain()
    LOGGER.info('Gunicorn server hook on reload')
    return True


def on_exit(server):
    """
    A Testing Method for Gunicorn on_reload.
    """
    # master hook only; worker-owned background shutdown happens in worker_exit
    LOGGER.info(vars(server))
    LOGGER.info('Gunicorn server hook on exit')
    # we call the shutdown hook plugin
    try:
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        hooks_plugins = Helper().plugin_finder(f'{plugins_path}/hooks')
        hook_plugin = Helper().plugin_load(
            hooks_plugins,
            'hooks/luna',
            'default'
        )
        status, message = hook_plugin().shutdown(Helper().nodes_and_groups())
        if not status:
            sys.stderr.write(f"ERROR: Shutdown hook plugin returned: {status}, {message}\n")
    except Exception as exp:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        sys.stderr.write(f"ERROR: Shutdown hook plugin returned an exception: {exp}, {exc_type}, in {exc_tb.tb_lineno}\n")
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
daemon.register_blueprint(roles_blueprint)
daemon.register_blueprint(scripts_blueprint)
daemon.register_blueprint(bmcsetup_blueprint)
daemon.register_blueprint(cluster_blueprint)
daemon.register_blueprint(dns_blueprint)
daemon.register_blueprint(route_blueprint)
daemon.register_blueprint(group_blueprint)
daemon.register_blueprint(network_blueprint)
daemon.register_blueprint(node_blueprint)
daemon.register_blueprint(osgroup_blueprint)
daemon.register_blueprint(osimage_blueprint)
daemon.register_blueprint(osuser_blueprint)
daemon.register_blueprint(otherdev_blueprint)
daemon.register_blueprint(secrets_blueprint)
daemon.register_blueprint(status_blueprint)
daemon.register_blueprint(switch_blueprint)
daemon.register_blueprint(cloud_blueprint)
daemon.register_blueprint(files_blueprint)
daemon.register_blueprint(service_blueprint)
daemon.register_blueprint(monitor_blueprint)
daemon.register_blueprint(control_blueprint)
daemon.register_blueprint(tracker_blueprint)
daemon.register_blueprint(journal_blueprint)
daemon.register_blueprint(tables_blueprint)
daemon.register_blueprint(ha_blueprint)
daemon.register_blueprint(rack_blueprint)
daemon.register_blueprint(export_blueprint)
daemon.register_blueprint(import_blueprint)


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
    response = {'version': {'luna': '2.1.0001', 'api': 1, 'commit': version }}
    access_code = 200
    return json.dumps(response), access_code


@daemon.route('/')
def main():
    """ Abort Main Route"""
    abort(404, None)


@daemon.errorhandler(400)
def bad_request(error):
    """ Abort All 400"""
    error = {'message': 'Bad Requests'}
    return json.dumps(error), 400


@daemon.errorhandler(401)
def unauthorized(error):
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
def server_error(error):
    """ Abort All 500"""
    error = {'message': 'Server Error'}
    return json.dumps(error), 500


@daemon.errorhandler(503)
def service_unavailable(error):
    """ Abort All 503"""
    error = {'message': f'{error} Service Unavailable'}
    return json.dumps(error), 503
