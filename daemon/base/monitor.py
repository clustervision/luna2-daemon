#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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

This endpoint can be contacted to obtain service status.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


import re
from common.constant import CONSTANT
from utils.log import Log
from utils.service import Service
from utils.helper import Helper
from utils.database import Database
from utils.monitor import Monitor as monitor
from utils.status import Status


try:
    PLUGIN_PATH = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
    HOOKS_PLUGINS = Helper().plugin_finder(f'{PLUGIN_PATH}/hooks/monitor')
    NodeMonitorPlugin = Helper().plugin_load(HOOKS_PLUGINS,'hooks/monitor','node')
except Exception as exp:
    LOGGER = Log.get_logger()
    LOGGER.error(f"Problems encountered while pre-loading detection plugin: {exp}")


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
        status=False
        if name == "luna2":
            # response, code = Helper().checkdbstatus()
            response, status = 'Helper Method checkdbstatus is missing', True
            self.logger.info(f'Database status is: {response}.')
        returned = Service().luna_service(name, 'status')
        status=returned[0]
        response=returned[1]
        return status, response


    def get_nodestatus(self, node=None):
        """
        This method will check the status of a node
        """
        status=False
        response = {"monitor": {"status": { node: { } } } }
        db_node = Database().get_record_join(['monitor.*'],['monitor.tablerefid=node.id'],
                                             ["monitor.tableref='node'",f"node.name='{node}'"])
        if db_node:
            status = True
            state,servicestatus=monitor().installer_state(db_node[0]['state'],db_node[0]['status'])
            response['monitor']['status'][node]['status'] = servicestatus
            response['monitor']['status'][node]['state'] = db_node[0]['state']
        else:
            response = None
            status = False
        return status, response


    def get_itemstatus(self, item=None, name=None):
        """
        This method will check the status of an item by the supplied name
        """
        status=False
        if not name:
            return status, "Invalid request: name not provided"
        response = {"monitor": {"status": { name: { } } } }
        tablerefid = 0
        if item:
            tablename = item
            where = f'WHERE id="{name}" OR name="{name}";'
            if item in ['ha', 'mother']:
                tablename = 'reference'
                where = f'WHERE tableref="{item}" and tablerefname="{name}"'
            elif item == 'sync':
                tablename = 'osimage'
            db_item = Database().get_record(None, tablename, where)
            if db_item:
                tablerefid = db_item[0]['id']
        elif name:
            item = name

        where = f'WHERE tableref="{item}" AND tablerefid="{tablerefid}"'
        db_item = Database().get_record(None, 'monitor', where)
        if db_item:
            status = True
            response['monitor']['status'][name]['status'] = db_item[0]['status']
            response['monitor']['status'][name]['state'] = db_item[0]['state']
        else:
            response = None
            status = False
        return status, response


    def update_nodestatus(self, node=None, request_data=None):
        """
        This method will update the status of a node
        """
        status=False
        response = 'Bad Request'
        if request_data:
            try:
                state = request_data['monitor']['status'][node]['state']
                node_status = None
                if 'status' in request_data['monitor']['status'][node].keys():
                    node_status = request_data['monitor']['status'][node]['status']
                where = f' WHERE id = "{node}" OR name = "{node}";'
                node_db = Database().get_record(None, 'node', where)
                if node_db:
                    self.logger.info(f"node {node}: {state}, {node_status}")
                    row = [{"column": "tableref", "value": "node"},
                           {"column": "tablerefid", "value": node_db[0]['id']},
                           {"column": "state", "value": state}]
                    if node_status:
                        row.append({"column": "status", "value": node_status})
                    result = Database().insert('monitor',row,replace=True)
                    if result:
                        status=True
                        response = f'Node {node} updated'
                        try:
                            function_name = state.replace('.','_')
                            function_name = function_name.replace(' ','_')
                            if function_name and function_name in vars(NodeMonitorPlugin):
                                plugin_function = getattr(NodeMonitorPlugin,function_name)
                                result, message = plugin_function(NodeMonitorPlugin,name=node)
                            else:
                                self.logger.debug(f"function {function_name} not found in node monitor plugin")
                        except Exception as exp:
                            self.logger.error(f"{exp}")
                    else:
                        status=False
                        response = f'Node {node} update not succesful'
                else:
                    response = 'Node is not present'
                    status=False
            except KeyError:
                response = 'Invalid request: URL Node is not matching with requested node'
                status=False
        return status, response


    def update_itemstatus(self, item=None, name=None, request_data=None):
        """
        This method will update the status of a an item
        """
        status=False
        response = 'Bad Request'
        if request_data:
            try:
                state = request_data['monitor']['status'][name]['state']
                item_status = False
                if 'status' in  request_data['monitor']['status'][name]:
                    item_status = request_data['monitor']['status'][name]['status']
                if 'item' in  request_data['monitor']['status'][name]:
                    item = request_data['monitor']['status'][name]['item']
                if isinstance(item_status, bool):
                    state,item_status=monitor().item_state(state,item_status)
                self.logger.info(f"item {item}/{name}: {state}, {item_status}")
                tablerefid = 0
                if item:
                    tablename = item
                    where = f'WHERE id = "{name}" OR name = "{name}";'
                    if item in ['ha', 'mother']:
                        tablename = 'reference'
                        where = f'WHERE tableref="{item}" and tablerefname="{name}"'
                    elif item == 'sync':
                        tablename = 'osimage'
                    item_db = Database().get_record(None, tablename, where)
                    if item_db:
                        tablerefid = item_db[0]['id']
                    elif item in ['ha', 'mother']:
                        row = [{"column": "tableref", "value": item},
                               {"column": "tablerefname", "value": name}]
                        result = Database().insert('reference',row)
                        if result:
                            tablerefid = result
                   
                elif name:
                    item = name
                else:
                    status = False
                    return status, "Invalid request: Neither item or name provided"
                row = [{"column": "tableref", "value": item},
                       {"column": "tablerefid", "value": tablerefid},
                       {"column": "state", "value": state}]
                if item_status:
                    row.append({"column": "status", "value": item_status})
                result = Database().insert('monitor',row,replace=True)
                if result:
                    status=True
                    response = f'Item {item} updated'
                else:
                    status=False
                    response = f'Item {item} update not succesful'
            except KeyError:
                response = 'Invalid request: URL item Name is not matching with requested name'
                status=False
            except Exception as exp:
                self.logger.info(f"EXP: {exp}")
                response = 'Invalid request: {exp}'
                status=False
        return status, response


    def get_queue(self):
        """
        This method generates a list of tasks in the queue
        """
        status=True
        response = []
        queue = Database().get_record(None, 'queue', "ORDER BY created ASC")
        if queue:
            status=True
            for task in queue:
                details={}
                details['level']='maintask'
                if task['noeof']:
                    details['level']='subtask'
                for item in ['request_id','username_initiator','created','subsystem','task','status']:
                    details[item]=task[item]
                details['task']+=f" {task['param']}"
                response.append(details)
        return status, response


    def get_status(self):
        """
        This method generates a list of messages in the status table
        """
        status=True
        response = []
        statuslist = Database().get_record(None, 'status', "ORDER BY created ASC")
        if statuslist:
            status=True
            for line in statuslist:
                details={}
                for item in ['request_id','username_initiator','created','read','message']:
                    details[item]=line[item]
                response.append(details)
        return status, response


    def insert_status_messages(self, request_data=None):
        status=False
        response = 'Bad Request'
        if request_data:
            data=request_data['monitor']['status']
            self.logger.debug(f"RESPONSE RECEIVED: {request_data}")
            if 'request_id' in data:
                status=True
                response="success"
                if 'remote_request_id' in data and 'remote_host' in data:
                    Status().add_message(data['request_id'], '__remote__', 'message on remote host', data['remote_request_id'], data['remote_host'])
                elif 'messages' in data:
                    for record in data['messages']:
                        if 'message' in record:
                            Status().add_message(data['request_id'], '__remote__', record['message'], remote_request_id, remote_host)
        return status, response

