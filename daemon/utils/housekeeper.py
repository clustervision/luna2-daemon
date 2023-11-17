#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT
from utils.helper import Helper
import concurrent.futures
from time import sleep
import sys
# below are needed to accomodate for the housekeeper
from utils.queue import Queue
from utils.osimage import OsImage
from utils.service import Service


class Housekeeper(object):

    def __init__(self):
        self.logger = Log.get_logger()

    def tasks_mother(self,event):
        tel=0
        self.logger.info("Starting tasks thread")
        while True:
            try:
                tel+=1
                if tel > 3:
                    tel=0
                    while next_id := Queue().next_task_in_queue('housekeeper'):
                        remove_from_queue=True
                        self.logger.info(f"tasks_mother sees job in queue as next: {next_id}")
                        details=Queue().get_task_details(next_id)
                        request_id=None
                        if 'request_id' in details:
                            request_id=details['request_id']
                        first,second,third,*_=details['task'].split(':')+[None]+[None]+[None]
                        self.logger.info(f"tasks_mother will work on {first} {second}")

                        match first:
                            case 'dhcp' | 'dns':
                                service=first
                                action=second
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                response, code = Service().luna_service(service, action)
                            case 'cleanup_old_file':
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                returned=OsImage().cleanup_file(second)
                                status=returned[0]
                                if status is False and len(returned)>1:
                                    self.logger.error(f"cleanup_file: {returned[1]}")
                            case 'cleanup_old_provisioning':
                                returned=OsImage().cleanup_provisioning(second)
                                status=returned[0]
                                if status is False and len(returned)>1:
                                    self.logger.error(f"cleanup_provisioning: {returned[1]}")

                        if remove_from_queue:
                            Queue().remove_task_from_queue(next_id)

                if event.is_set():
                    return
            except Exception as exp:
                self.logger.error(f"tasks_mother up thread encountered problem: {exp}")
            sleep(5)


    def cleanup_mother(self,event):
        tel=0
        self.logger.info("Starting cleanup thread")
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
                    records=Database().get_record_query("select id,peer from tracker where updated<datetime('now','-6 hour')") # only sqlite compliant. rest pending
                    for record in records:
                        self.logger.info(f"cleaning up tracker id {record['id']} : {record['peer']}")
                        where = [{"column": "id", "value": record['id']}]
                        Database().delete_row('tracker', where)
                if event.is_set():
                    return
            except Exception as exp:
                self.logger.error(f"clean up thread encountered problem: {exp}")
            sleep(5)


    def switchport_scan(self,event):
        tel=118
        self.logger.info("Starting switch port scan thread")
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIR"]
        #detection_plugins = Helper().plugin_finder(f'{plugins_path}/detection')
        #DetectionPlugin=Helper().plugin_load(detection_plugins,'detection','switchport')
        try:
            from plugins.boot.detection.switchport import Plugin as DetectionPlugin
            while True:
                try:
                    tel+=1
                    if tel > 120:
                        tel=0
                        switches = Database().get_record_join(['switch.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=switch.id'], ['ipaddress.tableref="switch"'])
                        self.logger.debug(f"switches {switches}")
                        if switches:
                            DetectionPlugin().clear()
                            for switch in switches:
                                uplinkports = []
                                if switch['uplinkports']:
                                    uplinkportsstring = switch['uplinkports'].replace(' ','')
                                    uplinkports = uplinkportsstring.split(',')
                                DetectionPlugin().scan(name=switch['name'], ipaddress=switch['ipaddress'],
                                                       oid=switch['oid'], read=switch['read'], rw=switch['rw'],
                                                       uplinkports=uplinkports)
                    if event.is_set():
                        return
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"switch port scan thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                sleep(5)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"switch port scan thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")


    def journal_mother(self,event):
        self.logger.info("Starting Journal/Replication thread")
        sync_tel=0
        try:
            from utils.journal import Journal
            journal_object=Journal()
            journal_object.set_insync(False)
            while journal_object.get_insync() is False:
                status=journal_object.pullfrom_controllers()
                if status is True:
                    journal_object.set_insync(True)
                if event.is_set():
                    return
                sleep(10)
            while True:
                try:
                    if sync_tel<1:
                        journal_object.pushto_controllers()
                        sync_tel=7
                    sync_tel-=1
                    journal_object.handle_requests()
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"journal_mother thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                if event.is_set():
                    return
                sleep(5)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"journal_mother thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")

