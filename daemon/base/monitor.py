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


from json import dumps
from utils.log import Log
from utils.service import Service
from utils.helper import Helper
from utils.database import Database
from utils.monitor import Monitor as monitor


class Monitor():
    """
    This class is responsible to monitor all the services.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def service_monitor(self, name=None):
        """
        This method will check the status of a service
        """
        if name == "luna2":
            # response, code = Helper().checkdbstatus()
            response, code = 'Helper Method checkdbstatus is missing', 200
            self.logger.info(f'Database status is: {response}.')
        response, code = Service().luna_service(name, 'status')
        return dumps(response), code


    def get_status(self, node=None):
        """
        This method will check the status of a node
        """
        access_code = 404
        response = {"monitor": {"status": { node: { } } } }
        nodes = Database().get_record(None, 'node', f' WHERE id = "{node}" OR name = "{node}"')
        if nodes:
            status,access_code=monitor().installer_state(nodes[0]['status'])
            response['monitor']['status'][node]['status'] = status
            response['monitor']['status'][node]['state'] = nodes[0]['status']
        else:
            response = None
            access_code = 404
        return dumps(response), access_code


    def update_status(self, node=None, http_request=None):
        """
        This method will update the status of a node
        """
        access_code = 400
        response = {'message': 'Bad Request'}
        request_data = http_request.data
        if request_data:
            try:
                state = request_data['monitor']['status'][node]['state']
                where = f' WHERE id = "{node}" OR name = "{node}";'
                node_db = Database().get_record(None, 'node', where)
                if node_db:
                    self.logger.info(f"node {node}: {state}")
                    row = [{"column": "status", "value": state}]
                    where = [{"column": "name", "value": node}]
                    Database().update('node', row, where)
                    access_code = 204
                    response = {'message': f'Node {node} updated'}
                else:
                    response = {'message': 'Node is not present'}
                    access_code = 404
            except KeyError:
                response = {'message': 'URL Node is not matching with requested node'}
                access_code = 400
        return dumps(response), access_code
