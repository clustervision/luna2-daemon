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
from common.constant import CONSTANT
import concurrent.futures
from time import sleep,time
from random import randint
from os import getpid
import re

LOGGER = Log.get_logger()
control_blueprint = Blueprint('control', __name__)


@control_blueprint.route('/control/power/<string:hostname>/<string:action>', methods=['GET'])
@token_required
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
@token_required
def control_post():
    """
    Input - hostname & action
    Process - Use to perform on, off, reset operations on one node.
    Output - Success or failure
    """

    response = {'message': 'Bad Request.'}
    access_code = 400
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
        if request_data:
            action = list(request_data['control']['power'].keys())[0]
            rawhosts = request_data['control']['power'][action]['hostlist']
            hostlist = Helper().get_hostlist(rawhosts)
            if hostlist:
                access_code = 200

                batch_size = int(CONSTANT['BMCCONTROL']['BMC_BATCH_SIZE'])
                batch_delay = CONSTANT['BMCCONTROL']['BMC_BATCH_DELAY']

                # Antoine -------------------------------------------------------------------
                pipeline = Helper().Pipeline()
                for hostname in hostlist:
                    pipeline.add_nodes({hostname: action})

                request_id=str(time())+str(randint(1001,9999))+str(getpid())

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(Helper().control_mother, pipeline, request_id, batch_size, batch_delay)
                executor.shutdown(wait=False)
                # use below to not spawn a thread. easy for debugging.
                #Helper().control_mother(pipeline, request_id, batch_size, batch_delay)

                # though we won't wait till all scheduled tasks are done, we wait a bit and return what we have.
                # the client/lpower will then have to inquire to see what's done hereafter
                wait_count=3
                while(pipeline.has_nodes() and wait_count > 0):
                    sleep(1)
                    wait_count-=1

                response = {'message': 'Bad Request.'}
                status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
                if status:
                    on_nodes=[]
                    off_nodes=[]
                    failed_nodes=[]
                    for record in status:
                        if 'message' in record:
                            if record['read'] == 0:
                                node,result=record['message'].split(':',1)  #data is message is like 'nodexxx:message'
                                LOGGER.info(f"control POST regexp match: [{result}]")
                                if result == "on":
                                    on_nodes.append(node)
                                elif result == "off":
                                    off_nodes.append(node)
                                else:
                                    failed_nodes.append(node)
                    response={'control': {'power': {'on': { 'hostlist': ','.join(on_nodes) }, 'off': { 'hostlist': ','.join(off_nodes) }, 'failed': { 'hostlist': ','.join(failed_nodes) }, 'request_id': request_id } }}
                    where = [{"column": "request_id", "value": request_id}]
                    row = [{"column": "read", "value": "1"}]
                    Database().update('status', row, where)
                else:
                    response = {'control': {'power': {'request_id': request_id} } }
                # end Antoine ---------------------------------------------------------------
            else:
                response = {'message': 'invalid hostlist.'}
                access_code = 404
           
            # no longer used functions:         
            #  list_for_queue = list(Helper().chunks(hostlist, batch_size))
            #  response = f'Hostlistcount {len(hostlist)}, batch_size {batch_size} batch_delay {batch_delay} list_for_queue {list_for_queue}'

    return json.dumps(response), access_code

@control_blueprint.route('/control/status/<string:request_id>', methods=['GET'])
def control_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """

    LOGGER.info(f"control STATUS: request_id: [{request_id}]")
    access_code = 400
    response = {'message': 'Bad Request.'}
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        on_nodes=[]
        off_nodes=[]
        failed_nodes=[]
        for record in status:
            if 'message' in record:
                if record['read']==0:
                    if record['message'] == "EOF":
                        Database().delete_row('status', [{"column": "request_id", "value": request_id}])
                    else:
                        node,result=record['message'].split(':',1)  #data is message is like 'nodexxx:message'
                        if result == "on":
                            on_nodes.append(node)
                        elif result == "off":
                            off_nodes.append(node)
                        else:
                            failed_nodes.append(node)
        response={'control': {'power': {'on': { 'hostlist': ','.join(on_nodes) }, 'off': { 'hostlist': ','.join(off_nodes) }, 'failed': { 'hostlist': ','.join(failed_nodes) }} }}
        where = [{"column": "request_id", "value": request_id}]
        row = [{"column": "read", "value": "1"}]
        Database().update('status', row, where)
        access_code = 200
    return json.dumps(response), access_code

