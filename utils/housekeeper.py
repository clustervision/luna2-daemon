#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is a class to assist in housekeeping related items. e.g. the cleanup thread lives here.

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
from threading import Event
from time import sleep, time
from datetime import datetime
import signal
# below are need to accomodate for the housekeeper
from utils.status import Status
from utils.queue import Queue
from utils.config import Config
from utils.osimage import OsImage
from utils.service import Service


class Housekeeper(object):

    def __init__(self):
        self.logger = Log.get_logger()

    def tasks_mother(self,event):
        tel=0
        self.logger.info("--> Starting tasks thread")
        while True:
            try:
                tel+=1
                if tel > 6:
                    tel=0
                    while next_id := Queue().next_task_in_queue('housekeeper'):
                        self.logger.info(f"tasks_mother sees job in queue as next: {next_id}")
                        details=Queue().get_task_details(next_id)
                        first,second,*_=(details['task'].split(':')+[None])
                        self.logger.info(f"tasks_mother will work on {first} {second}")

                        match first:
                            case 'dhcp' | 'dns':
                                service=first
                                action=second
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                response, code = Service().luna_service(service, action)
                            case 'pack_n_tar_osimage':
                                osimage=second
                                ret,mesg=OsImage().pack_image(osimage)
                                if ret is True:
                                    rett,mesgt=OsImage().create_tarball(osimage)

                        Queue().remove_task_from_queue(next_id)
                            
                if event.is_set():
                    return
            except Exception as exp:
                self.logger.error(f"tasks_mother up thread encountered problem: {exp}")
            sleep(5)


    def cleanup_mother(self,event):
        tel=0
        self.logger.info("--> Starting cleanup thread")
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



