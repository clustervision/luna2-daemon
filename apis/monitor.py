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

LOGGER = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)

node_status = {
    204: [
        "installer.discovery",
        "installer.downloaded",
        "installer.started",
        "installer.completed",
        "installer.prescript",
        "installer.partscript",
        "installer.postscript",
        "installer.image",
        "installer.finalizing"
    ],
    500: [
        "installer.finalizing",
        "installer.error"
    ]
}

@monitor_blueprint.route('/monitor/service/<string:name>', methods=['GET'])
def monitor_service(name=None):
    """
    Input - name of service
    Process - With the help of service class, the status of the service can be obtained.
    Currently supported services are DHCP, DNS and luna2 itself.
    Output - Status
    """
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
    nodes = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
    if nodes:
        if nodes[0]['status'] in node_status[204]:
            status = nodes[0]['status'].replace("installer.", '')
            response['monitor']['status'][node]['status'] = f'Luna installer: {status}'
            response['monitor']['status'][node]['state'] = nodes[0]['status']
            access_code = 200
        elif nodes[0]['status'] in node_status[500]:
            status = nodes[0]['status'].replace("installer.", '')
            response['monitor']['status'][node]['status'] = f'Luna installer: {status}'
            response['monitor']['status'][node]['state'] = nodes[0]['status']
            access_code = 500
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
        request_data = request.get_json(force=True)
    if request_data:
        try:
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

#                if state in node_status[204]:
#                    access_code = 204
#                    update = True
#                elif state in node_status[500]:
#                    access_code = 500
#                    update = True
#                else:
#                    response = {'message': f'State {state} does not belong to Node states.'}
#                    access_code = 204
            else:
                response = {'message': 'Node is not present.'}
                access_code = 404
        except KeyError:
            response = {'message': 'URL Node is not matching with requested node.'}
            access_code = 400

    return json.dumps(response), access_code
