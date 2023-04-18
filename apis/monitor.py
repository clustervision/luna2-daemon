#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This endpoint can be contacted to obtain service status.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from flask import Blueprint, json, request
from utils.log import Log
from utils.service import Service
from utils.helper import Helper
from utils.database import Database
from common.validate_auth import token_required
from utils.filter import Filter
from utils.monitor import Monitor

LOGGER = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)

@monitor_blueprint.route('/monitor/service/<string:name>', methods=['GET'])
def monitor_service(name=None):
    """
    Input - name of service
    Process - With the help of service class, the status of the service can be obtained.
    Currently supported services are DHCP, DNS and luna2 itself.
    Output - Status
    """
    name = Filter().filter(name,'monitor')
    if name == "luna2":
        response, code = Helper().checkdbstatus()
        LOGGER.info(f'Database status is: {response}.')
    response, code = Service().luna_service(name, 'status')
    return json.dumps(response), code


@monitor_blueprint.route("/monitor/status/<string:node>", methods=['GET'])
def monitor_status_get(node=None):
    """
    Input - NodeID or node name
    Process - Validate if the node exists and what the state is
    Output - Status.
    """
    access_code = 404
    response = {"monitor": {"status": { node: { } } } }
    node = Filter().filter(node,'name')
    nodes = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
    if nodes:
        status,access_code=Monitor().installer_state(nodes[0]['status'])
        response['monitor']['status'][node]['status'] = status
        response['monitor']['status'][node]['state'] = nodes[0]['status']
    else:
        response = None
        access_code = 404
    return json.dumps(response), access_code



@monitor_blueprint.route("/monitor/status/<string:node>", methods=['POST'])
@token_required
def monitor_status_post(node=None):
    """
    Input - NodeID or Node Name
    Process - Update the Node Status
    Output - Status.
    """
    access_code = 400
    response = {'message': 'Bad Request.'}
    if Helper().check_json(request.data):
        request_data,ret = Filter().validate_input(request.get_json(force=True),['monitor:status'])
        if not ret:
            response = {'message': request_data}
            access_code = 400
            return json.dumps(response), access_code
        if request_data:
            try:
                node = Filter().filter(node,'name')
                state = request_data['monitor']['status'][node]['state']
                where = f' WHERE id = "{node}" OR name = "{node}";'
                dbnode = Database().get_record(None, 'node', where)
                if dbnode:
                    LOGGER.info(f"node {node}: {state}")
                    row = [{"column": "status", "value": state}]
                    where = [{"column": "name", "value": node}]
                    Database().update('node', row, where)
                    access_code = 204
                    response = {'message': f'Node {node} updated.'}
                else:
                    response = {'message': 'Node is not present.'}
                    access_code = 404
            except KeyError:
                response = {'message': 'URL Node is not matching with requested node.'}
                access_code = 400

    return json.dumps(response), access_code

