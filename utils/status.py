

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
from datetime import datetime
import signal

#stop_requested = False

class Status(object):

    def __init__(self):

        self.logger = Log.get_logger()
#        signal.signal(signal.SIGTERM, self.sig_handler)
#        signal.signal(signal.SIGINT, self.sig_handler)
# 
#    def sig_handler(signum, frame):
#        self.logging.info("handling signal: %s\n" % signum)
#
#        global stop_requested
#        stop_requested = True

    def add_message(self,request_id,username_initiator,message):
        current_datetime=datetime.now()
        row=[{"column": "request_id", "value": f"{request_id}"}, 
             {"column": "created", "value": str(current_datetime)}, 
             {"column": "username_initiator", "value": f"{username_initiator}"}, 
             {"column": "read", "value": "0"}, 
             {"column": "message", "value": f"{message}"}]
        Database().insert('status', row)


    def mark_messages_read(self,request_id,id=None):
        where = [{"column": "request_id", "value": request_id}]
        row = [{"column": "read", "value": "1"}]
        Database().update('status', row, where)


    def del_message(self,id):
        pass


    def del_messages(self,request_id):
        Database().delete_row('status', [{"column": "request_id", "value": request_id}])


    def cleanup_mother(self,event):
        tel=0
        while True:
            try:
                tel+=1
                if tel > 120:
                    tel=0
                    records=Database().get_record_query("select id,message from status where created<datetime('now','-1 hour')") # only sqlite compliant. rest pending
                    for record in records:
                        self.logger.info(f"cleaning up status id {record['id']} : {record['message']}")
                        where = [{"column": "id", "value": record['id']}]
                        Database().delete_row('status', where)
                if event.is_set():
                    return
            except Exception as exp:
                self.logger.error(f"clean up thread encountered problem: {exp}")
            sleep(5)



