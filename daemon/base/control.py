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


from json import dumps
from time import sleep, time
from random import randint
from os import getpid
from concurrent.futures import ThreadPoolExecutor
from common.constant import CONSTANT
from common.validate_input import check_structure
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.control import Control as BMC
from utils.status import Status


class Control():
    """
    This class is responsible for power control operations.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def control_action(self, hostname=None, action=None):
        """
        This method will perform the power operation on a requested host, such as
        on, off, status.
        """
        status=False
        result=False
        node = Database().get_record_join(
            [
                'node.id as nodeid',
                'node.name as nodename',
                'node.groupid as groupid',
                'group.name as groupname',
                'ipaddress.ipaddress as device',
                'node.bmcsetupid'
            ],
            [
                'nodeinterface.nodeid=node.id',
                'ipaddress.tablerefid=nodeinterface.id',
                'group.id=node.groupid'
            ],
            ['tableref="nodeinterface"', "nodeinterface.interface='BMC'", f"node.name='{hostname}'"]
        )
        if node:
            bmcsetupid, group = None, None
            if 'bmcsetupid' in node[0] and str(node[0]['bmcsetupid']) == 'None':
                groupid = node[0]['groupid']
                group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
                if group:
                    bmcsetupid = group[0]['bmcsetupid']
                else:
                    self.logger.info(f"{node[0]['nodename']} does not have any group.")
                    status=False
                    return status, f'{hostname} does not have any group'
            else:
                bmcsetupid = node[0]['bmcsetupid']
            bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE id = "{bmcsetupid}"')
            if bmcsetup and 'device' in node[0] and node[0]['device']:
                username = bmcsetup[0]['username']
                password = bmcsetup[0]['password']
                action = action.replace('_', '')
                result, message = BMC().control_action(
                    node[0]['nodename'],
                    node[0]['groupname'],
                    action,
                    node[0]['device'],
                    username,
                    password
                )
                # message = Helper().ipmi_action(hostname, action, username, password)
                if 'power' in action:
                    action=action.replace('power ','')
                response = {'control': {action : message } }
                status=True
            else:
                response = f'{hostname} does not have any bmcsetup'
                status=False
        else:
            response = f'{hostname} does not have BMC configured (properly)'
            status=False
        return status, response


    def bulk_action(self, http_request=None):
        """
        This method will perform the power operation on requested hostlist, such as
        power on, off, status.
        sel list, clear
        """
        response = 'Bad Request'
        status=False
        request_data = http_request.data
        if request_data:
            if not 'control' in request_data.keys():
                status=False
                return status, 'Bad request'
            func   = list(request_data['control'].keys())[0]
            action = list(request_data['control'][func].keys())[0]
            if not check_structure(request_data, ['control:' + func + ':' + action + ':hostlist']):
                status=False
                return status, 'Bad request'
            raw_hosts = request_data['control'][func][action]['hostlist']
            hostlist = Helper().get_hostlist(raw_hosts)
            if hostlist:
                size = int(CONSTANT['BMCCONTROL']['BMC_BATCH_SIZE'])
                delay = CONSTANT['BMCCONTROL']['BMC_BATCH_DELAY']
                # Antoine -------------------------------------------------------------------
                pipeline = Helper().Pipeline()
                for hostname in hostlist:
                    pipeline.add_nodes({hostname: func+' '+action})
                request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
                executor = ThreadPoolExecutor(max_workers=1)
                executor.submit(BMC().control_mother, pipeline, request_id, size, delay)
                executor.shutdown(wait=False)
                # use below to not spawn a thread. easy for debugging.
                # BMC().control_mother(pipeline, request_id, size, delay)
                # though we won't wait till all scheduled tasks are done, we wait a bit
                # and return what we have.
                # the client/lpower will then have to inquire to see what's done hereafter
                wait_count = 3
                while(pipeline.has_nodes() and wait_count > 0):
                    sleep(1)
                    wait_count -= 1
                where = f' WHERE request_id = "{request_id}"'
                status = Database().get_record(None , 'status', where)
                if status:
                    on_nodes = []
                    off_nodes = []
                    failed_nodes = []
                    for record in status:
                        if 'message' in record:
                            if record['read'] == 0:
                                node, result, *_ = (record['message'].split(':', 1) + [None])
                                # data is message is like 'node:message'
                                self.logger.info(f"control POST regexp match: [{result}]")
                                if result in ['on','reset','cycle']:
                                    on_nodes.append(node)
                                elif result == "off":
                                    off_nodes.append(node)
                                else:
                                    failed_nodes.append(node)
                    Status().mark_messages_read(request_id)
                    response = {
                        'control': {
                            'power': {
                                'on': {'hostlist': ','.join(on_nodes)},
                                'off': {'hostlist': ','.join(off_nodes)},
                                'failed': {'hostlist': ','.join(failed_nodes)},
                                'request_id': request_id
                            }
                        }
                    }
                    status=True
                else:
                    response = {'control': {'power': {'request_id': request_id} } }
                    status=True
                # end Antoine ---------------------------------------------------------------
            else:
                response = 'Invalid request: invalid hostlist'
                status=False
        return status, response


    def get_status(self, request_id=None):
        """
        This method will get the exact status of the nodes, depends on the request ID.
        """
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            on_nodes = []
            off_nodes = []
            failed_nodes = []
            other_nodes = []
            for record in status:
                if 'message' in record:
                    if record['read'] == 0:
                        if record['message'] == "EOF":
                            Status().del_messages(request_id)
                        else:
                            node, result, message = record['message'].split(':',2)
                            # data is message is like 'node:message'
                            if message == "on":
                                on_nodes.append(node)
                            elif message == "off":
                                off_nodes.append(node)
                            elif result == 0 or message == "identify" or message == "noidentify":
                                other_nodes.append(node)
                            else:
                                failed_nodes.append(node)
            response = {
                'control': {
                    'power': {
                        'on': {'hostlist': ','.join(on_nodes)},
                        'off': {'hostlist': ','.join(off_nodes)},
                        'other': {'hostlist': ','.join(other_nodes)},
                        'failed': {'hostlist': ','.join(failed_nodes)}
                    }
                }
            }
            Status().mark_messages_read(request_id)
            return True, response
        return False, 'No data for this request'

