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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import concurrent.futures
from time import sleep
import os
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
                        request_id=details['request_id']
                        task = details['task']
                        first,second,*_=details['param'].split(':')+[None]+[None]
                        self.logger.info(f"tasks_mother will work on {task} {first}")

                        match task:
                            case 'restart'|'reload':
                                service=first
                                if service in ['dhcp','dhcp6','dns']:
                                    Queue().update_task_status_in_queue(next_id,'in progress')
                                    response, code = Service().luna_service(service, task)
                            case 'cleanup_old_file':
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                returned=OsImage().cleanup_file(first)
                                status=returned[0]
                                if status is False and len(returned)>1:
                                    self.logger.error(f"cleanup_file: {returned[1]}")
                            case 'cleanup_old_provisioning':
                                returned=OsImage().cleanup_provisioning(first)
                                status=returned[0]
                                if status is False and len(returned)>1:
                                    self.logger.error(f"cleanup_provisioning: {returned[1]}")
                            case 'sync_osimage_with_master':
                                osimage=first
                                master=second
                                Queue().update_task_status_in_queue(next_id,'in progress')
                                ret,mesg=Journal().add_request(function='OsImager.schedule_cleanup',object=osimage,keeptrying=60)
                                if ret is True:
                                    osimage_data=Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                                    if osimage_data:
                                        payload={'config':{'osimage':{osimage: {}}}}
                                        for file in ['kernelfile','initrdfile','imagefile']:
                                            payload['config']['osimage'][osimage][file]=osimage_data[0][file]
                                        ret,mesg=Journal().add_request(function='OSImage.update_osimage',object=osimage,payload=payload)
                                    if ret is True:
                                        ret,mesg=Journal().add_request(function='Downloader.pull_image_files',object=osimage,param=master)
                                    if ret is True:
                                        ret,mesg=Journal().add_request(function='OsImager.schedule_provision',object=osimage,param='housekeeper')
                                    if ret is True and HA().get_syncimages() is True:
                                        ret,mesg=Journal().add_request(function='Queue.add_task_to_queue_legacy',object=f'unpack_osimage:{osimage}',param='housekeeper')
                                if not ret and mesg:
                                    self.logger.warning(f"While working on sync_osimage_with_master task {next_id}, adding to journal returned: {mesg}")
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
        loop_counter=57
        node_log_counter=30
        osimage_log_counter=30
        self.logger.info("Starting invalid config thread")
        files_path = CONSTANT['FILES']['IMAGE_FILES']
        while True:
            try:
                loop_counter+=1
                if loop_counter > 60:
                    loop_counter=0
                    node_log_counter+=1
                    all_nodes = Database().get_record(None, "node")
                    if all_nodes:
                        for node in all_nodes:
                            status, node_response = Node().get_node(node['name'])
                            if status:
                                OK=True
                                for key, value in node_response['config']['node'][node['name']].items():
                                    if value == '!!Invalid!!':
                                        OK=False
                                        if node_log_counter > 30:
                                            self.logger.warning(f"Node {node['name']} has invalid config: {key} is {value}")
                                        new_state = f'Node configuration for {key} is invalid'
                                        state = {'monitor': {'status': {node['name']: {'state': new_state, 'status': '501'} } } }
                                        status, monitor_response = Monitor().get_nodestatus(node['name'])
                                        if status:
                                            current_state = monitor_response['monitor']['status'][node['name']]['state']
                                            if current_state != new_state:
                                                self.logger.info(f"{node['name']} current state: {current_state} transition to {new_state}")
                                                Monitor().update_nodestatus(node['name'], state)
                                        else:
                                            Monitor().update_nodestatus(node['name'], state)
                                if OK:
                                    status, monitor_response = Monitor().get_nodestatus(node['name'])
                                    if status:
                                        current_status = monitor_response['monitor']['status'][node['name']]['status']
                                        if current_status == '501':
                                            self.logger.warning(f"Node {node['name']} had invalid config but has been corrected")
                                            state = {'monitor': {'status': {node['name']: {'state': None, 'status': '200'} } } }
                                            Monitor().update_nodestatus(node['name'], state)
                            else:
                                self.logger.error(f"Node {node['name']} lookup returned {status}")
                        if node_log_counter > 30:
                            node_log_counter=0

                    osimage_log_counter+=1
                    all_images = Database().get_record(table='osimage')
                    if all_images:
                        for image in all_images:
                            current_status, current_state, new_state, OK = None, None, None, True
                            status, monitor_response = Monitor().get_itemstatus(item='osimage', name=image['name'])
                            if status:
                                current_status = monitor_response['monitor']['status'][image['name']]['status']
                                current_state = monitor_response['monitor']['status'][image['name']]['state']
                            for item in ['imagefile','kernelfile','initrdfile']:
                                if image[item] is None:
                                    if new_state is None:
                                        new_state=''
                                    new_state+=f'{item} defined as {image[item]};'
                                    OK=False
                                elif not os.path.isfile(files_path+'/'+image[item]):
                                    if new_state is None:
                                        new_state=''
                                    new_state+=f'non existent {item} {image[item]};'
                                    OK=False
                                if not OK:
                                    if osimage_log_counter > 30:
                                        self.logger.warning(f"OsImage {image['name']} has non existing {item} {image[item]}")
                            if OK:
                                if current_status == '501':
                                    self.logger.warning(f"OsImage {image['name']} had invalid config but has been corrected")
                                    state = {'monitor': {'status': {image['name']: {'state': new_state, 'status': '200'} } } }
                                    Monitor().update_itemstatus(item='osimage', name=image['name'], request_data=state)
                            else:
                                if current_status == '200':
                                    if current_state is None or current_state != new_state:
                                        self.logger.info(f"{image['name']} current state: {current_state} transition to {new_state}")
                                    state = {'monitor': {'status': {image['name']: {'state': new_state, 'status': '501'} } } }
                                    Monitor().update_itemstatus(item='osimage', name=image['name'], request_data=state)
                            if current_status is None:
                                state = {'monitor': {'status': {image['name']: {'state': new_state, 'status': OK} } } }
                                Monitor().update_itemstatus(item='osimage', name=image['name'], request_data=state)
                        if osimage_log_counter > 30:
                            osimage_log_counter=0

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
        sync_counter=0
        ping_counter=3
        ping_check=4
        sum_counter=0
        insync_check=140
        oosync_counter=0
        ping_status, check_status = True, True
        try:
            ha_object=HA()
            if not ha_object.get_hastate():
                self.logger.info(f"Currently not configured to run in H/A mode. Exiting journal thread")
                return
            me=ha_object.get_me()
            shadow=ha_object.get_shadow()
            if shadow:
                self.logger.info(f"I am {me} and i am a shadow controller")
            else:
                self.logger.info(f"I am {me}")
            journal_object=Journal(me)
            tables_object=Tables()
            ha_object.set_insync(False)
            # ---------------------------- we keep asking the journal from others until successful
            while syncpull_status is False:
                try:
                    if sync_counter<1:
                        syncpull_status=journal_object.pullfrom_controllers()
                        sync_counter=2
                    sync_counter-=1
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"journal_mother thread encountered problem in initial sync: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                sleep(5)
                if event.is_set():
                    return
            # ---------------------------- good. now we can proceed with the main loop
            sync_counter=0
            ha_object.set_overrule(False)
            while True:
                try:
                    # --------------------------- am i a master or not?
                    master=ha_object.get_role()
                    # --------------------------- first we sync with the others. we push what's still in the journal
                    if sync_counter<1:
                        journal_object.pushto_controllers()
                        sync_counter=7
                    else:
                        journal_object.pushto_controllers(forward=True)
                    sync_counter-=1
                    # --------------------------- then we process what we have received
                    handled=journal_object.handle_requests()
                    if handled is True:
                        if ping_status and check_status:
                            ha_object.set_insync(True)
                        sum_counter=18
                    elif startup_controller is True:
                        startup_controller=False
                        ha_object.set_insync(True)
                    # --------------------------- we ping the others. if someone is down, we become paranoid
                    if ping_counter<1:
                        ping_status=ha_object.ping_controllers()
                        if master is False: # i am not a master
                            status = ping_status and check_status
                            ha_object.set_insync(status)
                        ping_counter=3
                    ping_counter-=1
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
                    # --------------------------- if we're the master but for some unknown reason we've been out of sync for too long...
                    if insync_check<1:
                        if master is True:
                            if ha_object.get_insync() is True:
                                oosync_counter=0
                            else:
                                oosync_counter+=1
                            if oosync_counter>2:
                                self.logger.warning(f"I am a master but somehow got stuck being out of sync? This should not happen....")
                                ha_object.set_insync(True)
                                oosync_counter=0
                        else:
                            oosync_counter=0
                        insync_check=120
                    insync_check-=1
                    # --------------------------- then on top of that, we verify checksums. if mismatch, we import from the master
                    if hardsync_enabled:
                        if sum_counter<1:
                            if master is False: # i am not a master
                                mismatch_tables=tables_object.verify_tablehashes_controllers()
                                if mismatch_tables:
                                    for mismatch in mismatch_tables:
                                        status, data=tables_object.fetch_table(mismatch['table'],mismatch['host'])
                                        if status:
                                            tables_object.import_table(table=mismatch['table'],data=data,emptyok=True)
                                    Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper', request_id='__table_fix__')
                                    Queue().add_task_to_queue(task='restart', param='dhcp6', subsystem='housekeeper', request_id='__table_fix__')
                                    Queue().add_task_to_queue(task='reload', param='dns', subsystem='housekeeper', request_id='__table_fix__')
                            sum_counter=720
                        sum_counter-=1
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

