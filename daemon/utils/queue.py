#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is a class to assist in Status related items. e.g. the cleanup thread lives here.

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import subprocess
import json
from configparser import RawConfigParser
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT, LUNAKEY
from utils.helper import Helper
import concurrent.futures
#import threading
from threading import Event
from time import sleep, time
from datetime import datetime, timedelta
import signal
import re

class Queue(object):

    def __init__(self):
        self.logger = Log.get_logger()

    def add_task_to_queue(self,task,subsystem=None,request_id=None,force=None,when=None):
        if subsystem is None:
            subsystem="anonymous"
        if request_id is None:
            request_id="n/a"

        if not force:
            # pending. these datatime calls might not be mysql compliant.
            where=f" WHERE subsystem='{subsystem}' AND task='{task}' AND created>datetime('now','-15 minute') ORDER BY id ASC LIMIT 1"
            check = Database().get_record(None , 'queue', where)
            if check:
                # we already have the same task in the queue
                self.logger.info(f"We already have similar job in the queue {check[0]['task']} ({check[0]['id']}) and i will return the matching request_id: {check[0]['request_id']}")
                return check[0]['id'],check[0]['request_id']

#        current_datetime=datetime.now().replace(microsecond=0)
        current_datetime="NOW"

        if when:
            result = re.search(r"^([0-9]+)(h|m|s)?$", when)
            delay = result.group(1)
            denom = result.group(2)
            if not denom:
                denom='s'
            if delay and denom:
                match denom:
                    case 'h':
#                        current_datetime=datetime.now().replace(microsecond=0) + timedelta(hours=delay)
                        current_datetime=f"NOW +{delay} hour"
                    case 'm':
#                        current_datetime=datetime.now().replace(microsecond=0) + timedelta(minutes=delay)
                        current_datetime=f"NOW +{delay} minute"
                    case 's':
#                        current_datetime=datetime.now().replace(microsecond=0) + timedelta(seconds=delay)
                        current_datetime=f"NOW +{delay} second"
                self.logger.info(f"Scheduling task {task} into the future: {current_datetime}")
                
        row=[{"column": "created", "value": str(current_datetime)}, 
             {"column": "username_initiator", "value": "luna"}, 
             {"column": "task", "value": f"{task}"},
             {"column": "subsystem", "value": f"{subsystem}"},
             {"column": "request_id", "value": f"{request_id}"},
             {"column": "status", "value": "queued"}]
        id=Database().insert('queue', row)
        # the id is supposed to be kept bij de caller so it can update the status, either directly or after other pending stuff is done
        return id,'added'

    def update_task_status_in_queue(self,taskid,status):
        row = [{"column": "status", "value": f"{status}"}]
        where = [{"column": "id", "value": f"{taskid}"}]
        status = Database().update('queue', row, where)

    def remove_task_from_queue(self,taskid):
        Database().delete_row('queue', [{"column": "id", "value": taskid}])

    def remove_task_from_queue_by_request_id(self,request_id):
        Database().delete_row('queue', [{"column": "request_id", "value": request_id}])

    def next_task_in_queue(self,subsystem,filter=None):
        where=None
        if filter:
            where=f" WHERE subsystem='{subsystem}' AND status='{filter}' AND created>datetime('now','-15 minute') AND created<=datetime('now') ORDER BY id ASC LIMIT 1"
        else:
            where=f" WHERE subsystem='{subsystem}' AND created>datetime('now','-15 minute') AND created<=datetime('now') ORDER BY id ASC LIMIT 1"
        task = Database().get_record(None , 'queue', where)
        if task:
            return task[0]['id']
        return False

    def get_task_details(self,taskid):
        where=f" WHERE id='{taskid}'"
        task = Database().get_record(None , 'queue', where)
        if task:
            return task[0]
        return False

    def tasks_in_queue(self,subsystem=None):
        where=''
        if subsystem:
            where=f" WHERE subsystem='{subsystem}' LIMIT 1"
        tasks = Database().get_record(None , 'queue', where)
        if tasks:
            return True
        return False

    def change_subsystem(self,taskid,subsystem):
        row = [{"column": "subsystem", "value": f"{subsystem}"}]
        where = [{"column": "id", "value": f"{taskid}"}]
        status = Database().update('queue', row, where)


