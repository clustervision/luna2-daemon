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

import concurrent.futures
from time import sleep
import sys
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT
from utils.helper import Helper
# below are needed to accomodate for the housekeeper
from utils.queue import Queue
from utils.osimage import OsImage
from utils.service import Service
from base.monitor import Monitor
from base.node import Node
# H/A and journal funcs
from utils.ha import HA
from utils.journal import Journal
from utils.tables import Tables


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
                            case 'dhcp' | 'dhcp6' | 'dns':
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
                            case 'sync_osimage_with_master':
                                osimage=second
                                master=third
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                ret,mesg=Journal().add_request(function='OsImager.schedule_cleanup',object=osimage,keeptrying=60)
                                if ret is True:
                                    osimage_data=Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                                    if osimage_data:
                                        payload={'config':{'osimage':{osimage: {}}}}
                                        for file in ['kernelfile','initrdfile','imagefile']:
                                            payload['config']['osimage'][osimage][file]=osimage_data[0][file]
                                        Journal().add_request(function='OSImage.update_osimage',object=osimage,payload=payload)
                                    Journal().add_request(function='Downloader.pull_image_files',object=osimage,param=master)
                                    Journal().add_request(function='OsImager.schedule_provision',object=osimage,param='housekeeper')
                                    if HA().get_syncimages() is True:
                                        Journal().add_request(function='Queue.add_task_to_queue',object=f'unpack_osimage:{osimage}',param='housekeeper')
                                else:
                                    Queue().update_task_status_in_queue(next_id,'stuck')
                                    remove_from_queue=False
                            case 'provision_osimage':
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                OsImage().provision_osimage(next_id,request_id)
                            case 'unpack_osimage':
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                OsImage().unpack_osimage(next_id,request_id)

                        if remove_from_queue:
                            Queue().remove_task_from_queue(next_id)

                if event.is_set():
                    return
            except Exception as exp:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                self.logger.error(f"tasks_mother up thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
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
                    records=Database().get_record_query("select ipaddress from reservedipaddress where created<datetime('now','-10 minute')") # only sqlite compliant. rest pending
                    for record in records:
                        self.logger.info(f"cleaning up reserved ipaddress {record['ipaddress']}")
                        where = [{"column": "ipaddress", "value": record['ipaddress']}]
                        Database().delete_row('reservedipaddress', where)
                if event.is_set():
                    return
            except Exception as exp:
                self.logger.error(f"clean up thread encountered problem: {exp}")
            sleep(5)


    def switchport_scan(self,event):
        tel=118
        self.logger.info("Starting switch port scan thread")
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


    def invalid_config_mother(self, event):
        tel=57
        self.logger.info("Starting invalid config thread")
        while True:
            try:
                tel+=1
                if tel > 60:
                    tel=0
                    all_nodes = Database().get_record(None, "node")
                    if all_nodes:
                        for node in all_nodes:
                            status, response = Node().get_node(node['name'])
                            if status:
                                for key, value in response['config']['node'][node['name']].items():
                                    if value == '!!Invalid!!':
                                        self.logger.warning(f"Node {node['name']} has invalid config: {key} is {value}")
                                        status = {'monitor': {'status': {node['name']: {'state': f'Node configuration for {key} is invalid'} } } }
                                        Monitor().update_nodestatus(node['name'], status)
                            else:
                                self.logger.error(f"Node {node['name']} lookup returned {status}")
            except Exception as exp:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                self.logger.error(f"invalid config thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            if event.is_set():
                return
            sleep(5)


    def journal_mother(self,event):
        self.logger.info("Starting Journal/Replication thread")
        hardsync_enabled=True # experimental hard table sync based on checksums. handle with care!
        startup_controller=True
        syncpull_status=False
        sync_tel=0
        ping_tel=3
        ping_check=4
        sum_tel=0
        ping_status, check_status = True, True
        try:
            ha_object=HA()
            if not ha_object.get_hastate():
                self.logger.info(f"Currently not configured to run in H/A mode. Exiting journal thread")
                return
            me=ha_object.get_me()
            self.logger.info(f"I am {me}")
            journal_object=Journal(me)
            tables_object=Tables()
            ha_object.set_insync(False)
            # ---------------------------- we keep asking the journal from others until successful
            while syncpull_status is False:
                try:
                    if sync_tel<1:
                        syncpull_status=journal_object.pullfrom_controllers()
                        sync_tel=2
                    sync_tel-=1
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"journal_mother thread encountered problem in initial sync: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                sleep(5)
                if event.is_set():
                    return
            # ---------------------------- good. now we can proceed with the main loop
            sync_tel=0
            ha_object.set_overrule(False)
            while True:
                try:
                    # --------------------------- am i a master or not?
                    master=ha_object.get_role()
                    # --------------------------- first we sync with the others. we push what's still in the journal
                    if sync_tel<1:
                        journal_object.pushto_controllers()
                        sync_tel=7
                    sync_tel-=1
                    # --------------------------- then we process what we have received
                    handled=journal_object.handle_requests()
                    if handled is True:
                        if ping_status and check_status:
                            ha_object.set_insync(True)
                        sum_tel=18
                    elif startup_controller is True:
                        startup_controller=False
                        ha_object.set_insync(True)
                    # --------------------------- we ping the others. if someone is down, we become paranoid
                    if ping_tel<1:
                        ping_status=ha_object.ping_all_controllers()
                        if master is False: # i am not a master
                            status = ping_status and check_status
                            ha_object.set_insync(status)
                        ping_tel=3
                    ping_tel-=1
                    # --------------------------- we check if we have received pings. if things are weird we use fallback mechanisms
                    if ping_check<1:
                        check_status=ha_object.verify_pings()
                        if master is False: # i am not a master
                            status = ping_status and check_status
                            ha_object.set_insync(status)
                        if check_status is False:
                            if ping_status is True:
                                self.logger.warning("Reverting to pulling journal updates on interval as an emergency measure...")
                                syncpull_status=journal_object.pullfrom_controllers()
                            ping_check=21
                        else:
                            ping_check=3
                    ping_check-=1
                    # --------------------------- then on top of that, we verify checksums. if mismatch, we import from the master
                    if hardsync_enabled:
                        if sum_tel<1:
                            if master is False: # i am not a master
                                mismatch_tables=tables_object.verify_tablehashes_controllers()
                                if mismatch_tables:
                                    for mismatch in mismatch_tables:
                                        status, data=tables_object.fetch_table(mismatch['table'],mismatch['host'])
                                        if status:
                                            tables_object.import_table(table=mismatch['table'],data=data,emptyok=True)
                                    Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_update__')
                                    Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_update__')
                            sum_tel=720
                        sum_tel-=1
                    # --------------------------- end of magic
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"journal_mother thread encountered problem in main loop: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                sleep(5)
                if event.is_set():
                    return
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"journal_mother thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}")

