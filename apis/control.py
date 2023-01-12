#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This file is the entry point for provisioning
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


from flask import Blueprint, json, request
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from common.validate_auth import token_required
# from common.constant import CONSTANT

LOGGER = Log.get_logger()
control_blueprint = Blueprint('control', __name__)


@control_blueprint.route('/control/power/<string:hostname>/<string:action>', methods=['GET'])
# @token_required
def control_get(hostname=None, action=None):
    """
    Input - hostname & action
    Process - Use to perform on, off, reset operations on one node.
    Output - Success or failure
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{hostname}"')
    if node:
        groupid = node[0]['groupid']
        group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
        if group:
            bmcsetupid = group[0]['bmcsetupid']
            bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE id = "{bmcsetupid}"')
            if bmcsetup:
                username = bmcsetup[0]['username']
                password = bmcsetup[0]['password']
                action = action.replace('_', '')
                control_node = Helper().ipmi_action(hostname, action, username, password)
                if 'status' in action:
                    response = {'control': {action : control_node } }
                    access_code = 200
                else:
                    response = {}
                    access_code = 204
            else:
                LOGGER.info(f'{hostname} not have any bmcsetup.')
                response = {'message': f'{hostname} not have any bmcsetup.'}
                access_code = 404
        else:
            LOGGER.info(f'{hostname} not have any group.')
            response = {'message': f'{hostname} not have any group.'}
            access_code = 404
    else:
        LOGGER.info(f'{hostname} not have any node.')
        response = {'message': f'{hostname} not have any node.'}
        access_code = 404
    return json.dumps(response), access_code


@control_blueprint.route('/control/power', methods=['POST'])
# @token_required
def control_post():
    """
    Input - hostname & action
    Process - Use to perform on, off, reset operations on one node.
    Output - Success or failure
    """
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
        if request_data:
            action = list(request_data['control']['power'].keys())[0]
            rawhosts = request_data['control']['power'][action]['hostlist']
            hostlist = Helper().get_hostlist(rawhosts)
            for hostname in hostlist:
                node = Database().get_record(None, 'node', f' WHERE name = "{hostname}"')
                if node:
                    groupid = node[0]['groupid']
                    group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
                    if group:
                        bmcsetupid = group[0]['bmcsetupid']
                        bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE id = "{bmcsetupid}"')
                        if bmcsetup:
                            username = bmcsetup[0]['userid']
                            password = bmcsetup[0]['password']
                            control_node = Helper().ipmi_action(hostname, action, username, password)
                            access_code = 204
                            if control_node is True:
                                if action == 'status':
                                    LOGGER.info(f'{hostname} is on')
                                    response = {'control': {action: 'on' } }
                                else:
                                    LOGGER.info(f'{hostname} has been {action}')
                                    response = {'message': f'{hostname} has been {action}'}
                            else:
                                if action == 'status':
                                    LOGGER.info(f'{hostname} is off')
                                    response = {'control': {action: 'off' } }
                                else:
                                    LOGGER.info(f'{hostname} failed to {action}')
                                    response = {'message': f'{hostname} has been {action}'}
                        else:
                            LOGGER.info(f'{hostname} not have any bmcsetup.')
                            response = {'message': f'{hostname} not have any bmcsetup.'}
                            access_code = 404
                    else:
                        LOGGER.info(f'{hostname} not have any group.')
                        response = {'message': f'{hostname} not have any group.'}
                        access_code = 404
                else:
                    LOGGER.info(f'{hostname} not have any node.')
                    response = {'message': f'{hostname} not have any node.'}
                    access_code = 404
            response = {'message': hostlist}
            access_code = 200
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    return json.dumps(response), access_code
