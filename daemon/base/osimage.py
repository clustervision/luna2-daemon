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
OSImage Class will handle all os image operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import re
from time import sleep, time
from os import getpid, path
from random import randint
from base64 import b64decode, b64encode
from concurrent.futures import ProcessPoolExecutor
from common.constant import CONSTANT
from utils.status import Status
from utils.osimage import OsImage as OsImager
from utils.database import Database
from utils.log import Log
from utils.queue import Queue
from utils.helper import Helper
from utils.model import Model
from utils.database import Database

class OSImage():
    """
    This class is responsible for all operations for osimage.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'osimage'
        self.table_cap = 'OS Image'
        self.image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
        self.files_path = CONSTANT['FILES']['IMAGE_FILES']
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.osimage_plugins = Helper().plugin_finder(f'{plugins_path}/osimage')


    def get_all_osimages(self):
        """
        This method will return all the osimage in detailed format.
        """
        status = False
        response = "No osimage is available"
        filesystem_plugin = 'default'
        if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
            filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
        os_image_plugin=Helper().plugin_load(self.osimage_plugins,
                                           'osimage/filesystem',filesystem_plugin)
        all_records = Database().get_record(table='osimage')
        if all_records:
            status = True
            response = {'config': {self.table: {} }}
            for record in all_records:
                record_id = record['id']
                del record['id']
                del record['changed']
                tagname = None
                if record['tagid']:
                    tagname = Database().name_by_id('osimagetag', record['tagid'])
                del record['tagid']
                if (not record['path']) or tagname:
                    record['path'] = '!!undefined!!'
                    try:
                        ret, data = os_image_plugin().getpath(image_directory=self.image_directory,
                                                              osimage=record['name'], tag=tagname)
                        if ret is True:
                            record['path'] = data
                    except Exception as exp:
                        self.logger.error(f"Plugin exception in getpath: {exp}")

                for item in ['imagefile','kernelfile','initrdfile']:
                    if (record[item] is not None) and (not os.path.isfile(self.files_path+'/'+record[item])):
                        record[item]='!!'+record[item]+'!!'

                record['tag'] = tagname or 'default'
                response['config'][self.table][record['name']] = record
        return status, response


    def get_osimage(self, name=None):
        """
        This method will return requested osimage in detailed format.
        """
        status = False
        response = f"No {name} is available"
        filesystem_plugin = 'default'
        if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
            filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
        os_image_plugin=Helper().plugin_load(self.osimage_plugins,
                                           'osimage/filesystem',filesystem_plugin)
        all_records = Database().get_record(table='osimage', where=f' WHERE name = "{name}"')
        if all_records:
            status = True
            response = {'config': {self.table: {} }}
            record = all_records[0]
            record_id = record['id']
            del record['id']
            del record['changed']
            tagname = None
            if record['tagid']:
                tagname = Database().name_by_id('osimagetag', record['tagid'])
            del record['tagid']
            if (not record['path']) or tagname:
                record['path'] = '!!undefined!!'
                try:
                    ret, data = os_image_plugin().getpath(image_directory=self.image_directory,
                                                          osimage=record['name'], tag=tagname)
                    if ret is True:
                        record['path'] = data
                except Exception as exp:
                    self.logger.error(f"Plugin exception in getpath: {exp}")

            for item in ['imagefile','kernelfile','initrdfile']:
                if (record[item] is not None) and (not os.path.isfile(self.files_path+'/'+record[item])):
                    record[item]='!!'+record[item]+'!!'

            record['tag'] = tagname or 'default'
            image_tags = []
            all_tags = Database().get_record(table='osimagetag',
                                             where=f' WHERE osimageid = "{record_id}"')
            if all_tags:
                for tag in all_tags:
                    image_tags.append(tag['name'])
                record['assigned_tags'] = ','.join(image_tags)

            regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
            try:
                for item in ['grab_filesystems','grab_exclude','kerneloptions']:
                    if record[item] and not regex.match(record[item]):
                        data = record[item]
                        data = b64encode(data.encode())
                        record[item] = data.decode("ascii")
            except Exception as exp:
                self.logger.error(f"{exp}")

            response['config'][self.table][record['name']] = record
        return status, response


    def get_osimage_member(self, name=None):
        """
        This method will return all the list of all the member node names for a osimage.
        """
        status, response = Model().get_member(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def get_all_osimagetags(self, name=None):
        """
        This method will return all the osimage tags in detailed format.
        """
        status = False
        response = "No osimagetag is available"
        filesystem_plugin = 'default'
        where = None
        if name:
            where = f"osimage.name='{name}'"
        if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
            filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
        os_image_plugin=Helper().plugin_load(self.osimage_plugins,
                                           'osimage/filesystem',filesystem_plugin)
        image_details = Database().get_record_join(
            ['osimagetag.*','osimage.path','osimage.name as osimagename',
             'osimage.id as osid','osimagetag.id as tagid'],
            ['osimagetag.osimageid=osimage.id'],
            where
        )
        if image_details:
            status = True
            allgroups = Database().get_record(table='group')
            allnodes = Database().get_record(table='node')
            groups = Helper().convert_list_to_dict(allgroups, 'id')
            nodes = Helper().convert_list_to_dict(allnodes, 'id')
            response = {'config': {'osimagetag': {} }}
            for image in image_details:
                nodes_using = []
                groups_using = []
                data = {}
                data['name'] = image['name']
                data['osimage'] = image['osimagename']
                data['kernelfile'] = image['kernelfile']
                data['initrdfile'] = image['initrdfile']
                data['imagefile'] = image['imagefile']
                if (not image['path']) or image['tagid']:
                    data['path'] = '!!undefined!!'
                    try:
                        ret, path = os_image_plugin().getpath(image_directory=self.image_directory,
                                                              osimage=image['osimagename'],
                                                              tag=image['name'])
                        if ret:
                            data['path'] = path
                    except Exception as exp:
                        self.logger.error(f"Plugin exception in getpath: {exp}")

                for item in ['imagefile','kernelfile','initrdfile']:
                    if (data[item] is not None) and (not os.path.isfile(self.files_path+'/'+data[item])):
                        data[item]='!!'+data[item]+'!!'

                for node in nodes.keys():
                    if str(nodes[node]['osimagetagid']) == str(image['tagid']):
                        nodes_using.append(nodes[node]['name'])
                if nodes_using:
                    data['nodes'] = ', '.join(nodes_using)
                for group in groups.keys():
                    if str(groups[group]['osimagetagid']) == str(image['tagid']):
                        groups_using.append(groups[group]['name'])
                if groups_using:
                    data['groups'] = ', '.join(groups_using)
                response['config']['osimagetag'][data['name']] = data
        return status, response


    def update_osimage(self, name=None, request_data=None):
        """
        This method will create or update a osimage.
        """
        data = {}
        status=False
        response="Internal error"
        create, update, move, oldosimage = False, False, False, None
        current_tag, tagname, new_tagid = None, None, None
        # things we have to set for a group
        items = {
            'grab_filesystems': '/, /boot',
            'grab_exclude': '/proc/*, /sys/*, /dev/*, /tmp/*, /run/*, /var/log/*',
            'kernelmodules': 'ipmi_devintf, ipmi_si, ipmi_msghandler'
        }
        if request_data:
            data = request_data['config']['osimage'][name]
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                image_id = image[0]['id']
                if 'tag' in data:
                    current_tag = Database().name_by_id('osimagetag', image[0]['tagid'])
                    tagname = data['tag']
                if 'newosimage' in data:
                    newosimage = data['newosimage']
                    where = f' WHERE `name` = "{newosimage}"'
                    osimage_check = Database().get_record(None, 'osimage', where)
                    if osimage_check:
                        status=False
                        return status, f'{newosimage} Already present in database'
                    else:
                        oldosimage=data['name']
                        data['name'] = data['newosimage']
                        del data['newosimage']
                        data['changed']=1
                        move=True
                update = True
            else:
                if 'newosimage' in data:
                    status=False
                    return status, f'{name} not present in database for rename'
                create = True

            for key, value in items.items():
                if key in data:
                    data[key] = data[key]
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                elif create:
                    data[key] = value
                    if isinstance(value, bool):
                        data[key] = str(Helper().bool_to_string(data[key]))
                if key in data and (not data[key]) and (key not in items):
                    del data[key]

            if 'tag' in data:
                del data['tag']

            osimage_columns = Database().get_columns('osimage')
            column_check = Helper().compare_list(data, osimage_columns)
            if column_check:
                if update:
                    if move:
                        status, mesg = OsImager().rename_osimage(oldosimage, data['name'])
                        if not status:
                            return status, mesg
                    if tagname == "": # to clear tag
                        data['tagid'] = ""
                    elif tagname != current_tag:
                        imagetag = Database().get_record(None, 'osimagetag', f' WHERE osimageid = "{image_id}" AND name = "{tagname}"')
                        if imagetag:
                            new_tagid = imagetag[0]['id']
                        if (not new_tagid) and image_id:
                            tag_data = {}
                            tag_data['name'] = tagname
                            tag_data['osimageid'] = image_id
                            tag_data['kernelfile'] = image[0]['kernelfile']
                            tag_data['initrdfile'] = image[0]['initrdfile']
                            tag_data['imagefile'] = image[0]['imagefile']
                            tag_row = Helper().make_rows(tag_data)
                            new_tagid = Database().insert('osimagetag', tag_row)
                        if new_tagid:
                            data['tagid'] = new_tagid
                    if not data:
                        status=True
                        return status, f'OS Image {name} updated'
                    where = [{"column": "id", "value": image_id}]
                    row = Helper().make_rows(data)
                    Database().update('osimage', row, where)
                    response = f'OS Image {name} updated'
                    status=True
                if create:
                    data['name'] = name
                    row = Helper().make_rows(data)
                    Database().insert('osimage', row)
                    response = f'OS Image {name} created'
                    status=True
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def clone_osimage(self, name=None, request_data=None):
        """
        This method will clone a osimage.
        """
        data = {}
        status=False
        response="Internal error"
        items = {
            'grab_filesystems',
            'grab_exclude',
            'initrdfile',
            'kernelfile',
            'kernelmodules',
            'kerneloptions',
            'kernelversion',
            'distribution',
            'osrelease'
        }
        response = {"message": 'OS image copy failed. No sign of life of spawned thread'}
        if request_data:
            data = request_data['config']['osimage'][name]
            bare = False
            nocopy = False
            tag = None
            if 'bare' in data:
                bare = data['bare']
                bare = Helper().make_bool(bare)
                del data['bare']
            if 'nocopy' in data:
                nocopy = data['nocopy']
                nocopy = Helper().make_bool(nocopy)
                del data['nocopy']
            if 'tag' in data and data['tag']:
                tag = data['tag']
                del data['tag']
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                if 'newosimage' in data:
                    newosimage = data['newosimage']
                    where = f' WHERE `name` = "{newosimage}"'
                    osimage_check = Database().get_record(None, 'osimage', where)
                    if osimage_check:
                        status=False
                        return status, f'{newosimage} Already present in database'
                    else:
                        data['name'] = data['newosimage']
                        for item in items:
                            if (item not in data) and item in image[0] and image[0][item]:
                                data[item]=image[0][item]
                        del data['newosimage']
                        if 'path' in data and data['path'] and path.exists(data['path']):
                            status=False
                            return status, f"Destination path {data['path']} already exists."
                else:
                    status=False
                    return status, 'Invalid request: New OS Image name not provided'
            else:
                status=False
                return status, f'OS Image {name} not present in the database'

            osimage_columns = Database().get_columns('osimage')
            column_check = Helper().compare_list(data, osimage_columns)
            if column_check:
                row = Helper().make_rows(data)
                img_id = Database().insert('osimage', row)
                if not img_id:
                    status = False
                    return status, "Failed cloning image"
                if nocopy is True:
                    status = True
                    return status, "OS Image cloned successfully"
                request_id  = str(time()) + str(randint(1001, 9999)) + str(getpid())
                if bare is not False:
                    param = f"{name}:{tag}:{data['name']}"
                    task_id, text = Queue().add_task_to_queue(task='clone_osimage', param=param, 
                                                              subsystem='osimage', request_id=request_id)
                else:
                    param = f"{name}:{tag}:{data['name']}"
                    task_id, text = Queue().add_task_to_queue(task='clone_n_pack_osimage', param=param, 
                                                              subsystem='osimage', request_id=request_id)
                if not task_id:
                    self.logger.info("config_osimage_clone cannot get queue_id")
                    status=False
                    return status, f"Internal error: OS image {name}->{data['name']} clone queuing failed."

                if text != "added":
                    # this means we already have an equal request in the queue
                    Status().add_message(text, "luna", f"similar task with id {task_id} is already queued. its progress is listed here")
                    response = f"osimage clone for {data['name']} already queued"
                    #response = {"message": message, "request_id": text}
                    self.logger.info(f"my response [{response}] [{text}]")
                    status=True
                    return status, response, text
                self.logger.info(f"config_osimage_clone added task with id {task_id} to queue")
                message = f"queued clone osimage {name}->{data['name']} with id {task_id}"
                Status().add_message(request_id, "luna", message)
                next_id = Queue().next_task_in_queue('osimage')
                if task_id == next_id:
                    executor = ProcessPoolExecutor(max_workers=1)
                    executor.submit(OsImager().osimage_mother)
                    executor.shutdown(wait=False)
                else:
                    next_id = Queue().next_parallel_task_in_queue('osimage',name,'queued')
                    if task_id == next_id:
                        # ok, so we are not the first mother running... let's only do our own request
                        executor = ProcessPoolExecutor(max_workers=1)
                        executor.submit(OsImager().osimage_mother, request_id)
                        executor.shutdown(wait=False)
                    else:
                        Status().add_message(request_id, "luna", f"other task with id {next_id} is being processed first. please wait")
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
                sleep(1)
                where = f' WHERE request_id = "{request_id}"'
                status = Database().get_record(None , 'status', where)
                if status:
                    response = f"osimage clone for {data['name']} queued"
                    status=True
                    return status, response, request_id
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_osimage(self, name=None):
        """
        This method will delete a osimage.
        """
        inuse_node = Database().get_record_join(['node.*'], ['osimage.id=node.osimageid'],
                                                f'osimage.name="{name}"')
        inuse_group = Database().get_record_join(['group.*'], ['osimage.id=group.osimageid'],
                                                f'osimage.name="{name}"')
        inuse = []
        if inuse_node:
            inuse += inuse_node                                   
        if inuse_group:
            inuse += inuse_group                                   
        if inuse:
            inuseby=[]
            while len(inuse) > 0 and len(inuseby) < 11:
                node=inuse.pop(0)
                inuseby.append(node['name'])
            response = f"osimage {name} currently in use by "+', '.join(inuseby)+" ..."
            return False, response

        image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if image:
            for item in ['kernelfile','initrdfile','imagefile']:
                if image[0][item]:
                    queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_file', param=image[0][item],
                                                                        subsystem='housekeeper', request_id='__image_delete__', when='1h')
            if image[0]['imagefile']:
                queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_provisioning', param=image[0]['imagefile'],
                                                                    subsystem='housekeeper', request_id='__image_delete__', when='1h')
        tag_details = Database().get_record_join(
            ['osimagetag.id as tagid','osimagetag.*','osimage.id as osimageid'],
            ['osimagetag.osimageid=osimage.id'],
            [f'osimage.name="{name}"']
        )
        if tag_details:
            for tag_detail in tag_details:
                for item in ['kernelfile','initrdfile','imagefile']:
                    if tag_detail[item]:
                        queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_file', param=tag_detail[item],
                                                                            subsystem='housekeeper', request_id='__tag_delete__', when='1h')
                if tag_detail['imagefile']:
                    queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_provisioning', param=tag_detail['imagefile'],
                                                                        subsystem='housekeeper', request_id='__tag_delete__', when='1h')
                status, response = Model().delete_record_by_id(
                    id = tag_detail['tagid'],
                    table = 'osimagetag',
                    table_cap = 'OS image tag'
                )
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return status, response


    def delete_osimagetag(self, name=None, tagname=None):
        """
        This method will delete an osimagetag.
        """
        tag_details = Database().get_record_join(
            ['osimagetag.id as tagid','osimagetag.*','osimage.id as osimageid','osimage.kernelfile as osimagekernelfile',
             'osimage.initrdfile as osimageinitrdfile','osimage.imagefile as osimageimagefile'],
            ['osimagetag.osimageid=osimage.id'],
            [f'osimage.name="{name}"',f'osimagetag.name="{tagname}"']
        )
        if not tag_details:
            status = False
            return status, f"image {name} and/or tag {tagname} not found or incorrect combination"
        cur_tag = Database().get_record(None , 'osimage', f' WHERE name="{name}"')
        if cur_tag and cur_tag[0]['tagid'] == tag_details[0]['tagid']:
            udata={}
            udata['tagid'] = ""
            where = [{"column": "id", "value": tag_details[0]['osimageid']}]
            row = Helper().make_rows(udata)
            Database().update('osimage', row, where)
        status, response = Model().delete_record_by_id(
            id = tag_details[0]['tagid'],
            table = 'osimagetag',
            table_cap = 'OS image tag'
        )
        for item in ['kernelfile','initrdfile','imagefile']:
            if tag_details[0][item]:
                if tag_details[0]['osimage'+item] == tag_details[0][item]:
                    # meaning: we are still using one for osimage itself! Antoine
                    continue
                queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_file', param=tag_details[0][item],
                                                                    subsystem='housekeeper', request_id='__tag_delete__', when='1h')
                if item == 'imagefile':
                    queue_id,queue_response = Queue().add_task_to_queue(task='cleanup_old_provisioning', param=tag_details[0][item],
                                                                        subsystem='housekeeper', request_id='__tag_delete__', when='1h')
        return status, response


    def grab(self, node=None, request_data=None):
        """
        This method will grab a osimage.
        """
        data = {}
        status=False
        response="Internal error"
        if request_data:
            data = request_data['config']['node'][node]
            bare=False
            if 'bare' in data:
                bare = Helper().make_bool(data['bare'])
            nodry = False
            # means default dry=True
            if 'nodry' in data:
                nodry = Helper().make_bool(data['nodry'])
            osimage = None
            if 'osimage' in data:
                osimage=data['osimage']
            else:
                image_details = Database().get_record_join(
                    ['osimage.name as osimagename', 'osimage.id as osimageid'],
                    ['osimage.id=node.osimageid'],
                    [f'node.name="{node}"']
                )
                if not image_details:
                    #meaning, node does not have osimage override. we check the group
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['group.id=node.groupid', 'osimage.id=group.osimageid'],
                        [f'node.name="{node}"']
                    )
                if image_details:
                    osimage=image_details[0]['osimagename']
                else:
                    status=False
                    ret_msg=f"Grab failed for {osimage}. This node has osimage or group configured?"
                    return status, ret_msg

            request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
            task_id, text = None, None
            if (bare is not False) or (nodry is False):
                param = f'{node}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task='grab_osimage', param=param, 
                                                          subsystem='osimage', request_id=request_id)
            else:
                param = f'{node}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task='grab_n_pack_n_build_osimage', param=param,
                                                          subsystem='osimage', request_id=request_id)
            if not task_id:
                self.logger.info("config_osimage_grab cannot get queue_id")
                status=False
                return status, f'OS image {osimage} grab queuing failed'
            if text != "added":
                # this means we already have an equal request in the queue
                Status().add_message(text, "luna", f"similar task with id {task_id} is already queued. its progress is listed here")
                response = f"osimage grab for {osimage} already queued"
                self.logger.info(f"my response [{response}] [{text}]")
                status=True
                return status, response, text

            self.logger.info(f"config_osimage_grab added task with id {task_id} to queue")
            message = f"queued grab osimage {osimage} with id {task_id}"
            Status().add_message(request_id, "luna", message)

            next_id = Queue().next_task_in_queue('osimage')
            if task_id == next_id:
                # we're first in the queue. wake up mother!
                executor = ProcessPoolExecutor(max_workers=1)
                executor.submit(OsImager().osimage_mother)
                executor.shutdown(wait=False)
                # OsImager().osimage_mother(request_id)
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
            else:
                next_id = Queue().next_parallel_task_in_queue('osimage',osimage,'queued')
                if task_id == next_id:
                    # ok, so we are not the first mother running... let's only do our own request
                    executor = ProcessPoolExecutor(max_workers=1)
                    executor.submit(OsImager().osimage_mother, request_id)
                    executor.shutdown(wait=False)
                else:
                    Status().add_message(request_id, "luna", f"other task with id {next_id} is being processed first. please wait")
            sleep(1)
            status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
            if status:
                response = f"osimage grab from {node} to {osimage} queued"
                status=True
                self.logger.info(f"my response [{response}] [{request_id}]")
                return status, response, request_id
        status=False
        return status, "osimage grab missing data"


    def push(self, entity_name=None, request_data=None):
        """
        This method will push a osimage.
        """
        data = {}
        status=False
        response="Internal error"
        if request_data:
            data, to_group = None, False
            nodry = False
            # means default dry=True
            if 'nodry' in request_data['config']:
                nodry = Helper().make_bool(data['nodry'])
            if 'group' in request_data['config']:
                data = request_data['config']['group'][entity_name]
                to_group = True
            else:
                data = request_data['config']['node'][entity_name]
            osimage=None
            if 'osimage' in data:
                osimage=data['osimage']
            else:
                image_details = None
                if to_group is True:
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['osimage.id=group.osimageid'],
                        [f'`group`.name="{entity_name}"']
                    )
                else:
                    image_details = Database().get_record_join(
                        ['osimage.name as osimagename', 'osimage.id as osimageid'],
                        ['osimage.id=node.osimageid'],
                        [f'node.name="{entity_name}"']
                    )
                    if not image_details:
                        # meaning, node does not have osimage override. we check the group
                        image_details = Database().get_record_join(
                            ['osimage.name as osimagename', 'osimage.id as osimageid'],
                            ['group.id=node.groupid', 'osimage.id=group.osimageid'],
                            [f'node.name="{entity_name}"']
                        )
                if image_details:
                    osimage=image_details[0]['osimagename']
                else:
                    status=False
                    ret_msg=f"Push failed for {osimage}. No osimage configured for this node or group?"
                    return status, ret_msg

            request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
            task_id, text = None, None
            if to_group is True:
                param = f'{entity_name}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task='push_osimage_to_group', param=param,
                                                          subsystem='osimage', request_id=request_id)
            else:
                param = f'{entity_name}:{osimage}:{nodry}'
                task_id, text = Queue().add_task_to_queue(task='push_osimage_to_node', param=param,
                                                          subsystem='osimage', request_id=request_id)
            if not task_id:
                self.logger.info("config_osimage_push cannot get queue_id")
                status=False
                return status, f'Internal error: OS image {osimage} push queuing failed'
            if text != "added":
                # this means we already have an equal request in the queue
                Status().add_message(text, "luna", f"similar task with id {task_id} is already queued. its progress is listed here")
                response = f"osimage push for {osimage} already queued"
                status=True
                self.logger.info(f"my response [{response}] [{text}]")
                return status, response, text

            self.logger.info(f"config_osimage_push added task with id {task_id} to queue")
            message = f"queued push osimage {osimage} with id {task_id}"
            Status().add_message(request_id, "luna", message)

            next_id = Queue().next_task_in_queue('osimage')
            if task_id == next_id:
                # w're first in the queue. let's wake up mother
                executor = ProcessPoolExecutor(max_workers=1)
                executor.submit(OsImager().osimage_mother)
                executor.shutdown(wait=False)
                # OsImager().osimage_mother(request_id)
                # we should check after a few seconds if there is a status update for us.
                # if so, that means mother is taking care of things
            else:
                next_id = Queue().next_parallel_task_in_queue('osimage',osimage,'queued')
                if task_id == next_id:
                    # We're not the first mother running... we only do our own stuff
                    executor = ProcessPoolExecutor(max_workers=1)
                    executor.submit(OsImager().osimage_mother, request_id)
                    executor.shutdown(wait=False)
                else:
                    Status().add_message(request_id, "luna", f"other task with id {next_id} is being processed first. please wait")
            sleep(1)
            status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
            if status:
                status=True
                response = f"osimage push from {entity_name} to {osimage} queued"
                self.logger.info(f"my response [{response}] [{request_id}]")
                return status, response, request_id
        status=False
        return status, "osimage push missing data"


    def pack(self, name=None):
        """
        This method will pack requested osimage.
        """
        status=False
        response="unknown state"
        response = {"message": f'OS image {name} packing failed. No sign of life of spawned thread'}
        # Antoine
        image = Database().get_record(None , 'osimage', f' WHERE name = "{name}"')
        force = False
        if image and 'changed' in image[0] and image[0]['changed']:
            force=True
            where = [{"column": "name", "value": name}]
            row = [{"column": "changed", "value": '0'}]
            Database().update('osimage', row, where)
        request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
        queue_id, queue_response = Queue().add_task_to_queue(task='pack_n_build_osimage', param=name,
                                                             subsystem='osimage', request_id=request_id, force=force)
        if not queue_id:
            self.logger.info("config_osimage_pack cannot get queue_id")
            status=False
            return status, f'Internal error: OS image {name} pack queuing failed'
        if queue_response != "added":
            # this means we already have an equal request in the queue
            Status().add_message(queue_response, "luna", f"similar task with id {queue_id} is already queued. its progress is listed here")
            response = f"osimage pack for {name} already queued"
            self.logger.info(f"my response [{response}] [{queue_response}]")
            status=True
            return status, response, queue_response

        self.logger.info(f"config_osimage_pack added task with id {queue_id} to queue")
        message = f"queued pack osimage {name} with id {queue_id}"
        Status().add_message(request_id, "luna", message)

        next_id = Queue().next_task_in_queue('osimage')
        if queue_id == next_id:
            # w're first in the queue. let's wake up mother
            executor = ProcessPoolExecutor(max_workers=1)
            executor.submit(OsImager().osimage_mother)
            executor.shutdown(wait=False)
            # OsImager().osimage_mother(request_id)
            # we should check after a few seconds if there is a status update for us.
            # if so, that means mother is taking care of things
        else:
            next_id = Queue().next_parallel_task_in_queue('osimage',name,'queued')
            if queue_id == next_id:
                # We're not the first mother running... we only do our own stuff
                executor = ProcessPoolExecutor(max_workers=1)
                executor.submit(OsImager().osimage_mother, request_id)
                executor.shutdown(wait=False)
            else:
                Status().add_message(request_id, "luna", f"other task with id {next_id} is being processed first. please wait")
        sleep(1)
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            status=True
            response = f"osimage pack for {name} queued"
            self.logger.info(f"my response [{response}] [{request_id}]")
            return status, response, request_id
        return status, response


    def change_kernel(self, name=None, request_data=None):
        """
        This method will change the kernel of an image and pack again that image.
        """
        data = {}
        status=False
        response="Internal error"
        if request_data:
            data = request_data['config']['osimage'][name]
            bare = False
            if 'bare' in data:
                bare = data['bare']
                bare = Helper().make_bool(bare)
                del data['bare']
            image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
            if image:
                image_id = image[0]['id']
                osimage_columns = Database().get_columns('osimage')
                column_check = Helper().compare_list(data, osimage_columns)
                if column_check:
                    where = [{"column": "id", "value": image_id}]
                    row = Helper().make_rows(data)
                    img_id = Database().update('osimage', row, where)
                    if not img_id:
                        status = False
                        return status, "Failed updating image"
                    if bare is True:
                        status=True
                        response = f'OS Image {name} Kernel updated'
                        return status, f'OS Image {name} Kernel updated'
                    request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
                    task_id, text = None,None
                    task_id, text = Queue().add_task_to_queue(task='pack_n_build_osimage', param=name,
                                                              subsystem='osimage', request_id=request_id)
                    if not task_id:
                        self.logger.info("config_osimage_kernel cannot get queue_id")
                        status=False
                        return status, f'OS image {name} pack queuing failed'
                    if text != "added":
                        # this means we already have an equal request in the queue
                        Status().add_message(text, "luna", f"similar task with id {task_id} is already queued. its progress is listed here")
                        response = f"osimage pack for {name} already queued"
                        self.logger.info(f"my response [{response}] [{text}]")
                        status=True
                        return status, response, text
                    self.logger.info(f"config_osimage_kernel added task with id {task_id} to queue")
                    message = f"queued pack osimage {name} with id {task_id}"
                    Status().add_message(request_id, "luna", message)
                    next_id = Queue().next_task_in_queue('osimage')
                    if task_id == next_id:
                        # we're first in the queue, let's wake up mother
                        executor = ProcessPoolExecutor(max_workers=1)
                        executor.submit(OsImager().osimage_mother)
                        executor.shutdown(wait=False)
                    else:
                        next_id = Queue().next_parallel_task_in_queue('osimage',name,'queued')
                        if task_id == next_id:
                            # there is another mother running so we focus on our own stuff
                            executor = ProcessPoolExecutor(max_workers=1)
                            executor.submit(OsImager().osimage_mother, request_id)
                            executor.shutdown(wait=False)
                        else:
                            Status().add_message(request_id, "luna", f"other task with id {next_id} is being processed first. please wait")
                    # we should check after a few seconds if there is a status update for us.
                    # if so, that means mother is taking care of things
                    sleep(1)
                    where = f' WHERE request_id = "{request_id}"'
                    status = Database().get_record(None , 'status', where)
                    if status:
                        response = f"osimage pack for {name} queued"
                        status=True
                        return status, response, request_id
                else:
                    response = 'Invalid request: Columns are incorrect'
                    status=False
            else:
                response = f'OS Image {name} does not exist'
                status=False
                return status, response
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def set_tag(self, name=None, request_data=None):
        """
        This method will change the tag of an image.
        """
        data = {}
        status=False
        response="Internal error"
        if request_data:
            data = request_data['config']['osimage'][name]
            if 'tag' in data:
                image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
                if image:
                    image_id = image[0]['id']
                    tagname, new_tagid = data['tag'], None
                    if tagname == "":
                        new_tagid = ""
                    else:
                        imagetag = Database().get_record(None, 'osimagetag', f' WHERE osimageid = "{image_id}" AND name = "{tagname}"')
                        if imagetag:
                            new_tagid = imagetag[0]['id']
                        if not new_tagid:
                            tag_data = {}
                            tag_data['name'] = tagname
                            tag_data['osimageid'] = image_id
                            tag_data['kernelfile'] = image[0]['kernelfile']
                            tag_data['initrdfile'] = image[0]['initrdfile']
                            tag_data['imagefile'] = image[0]['imagefile']
                            tag_data['kerneloptions'] = image[0]['kerneloptions']
                            tag_row = Helper().make_rows(tag_data)
                            new_tagid = Database().insert('osimagetag', tag_row)
                    if new_tagid is not None:
                        udata={}
                        udata['tagid'] = new_tagid
                        where = [{"column": "id", "value": image_id}]
                        row = Helper().make_rows(udata)
                        res = Database().update('osimage', row, where)
                        if res:
                            response=f"Tag {tagname} updated for OS Image {name}"
                            status=True
                    else:
                        response=f"Could not create tag for OS Image {name}"
                        status=False
                else:
                    response=f"OS Image {name} does not exist"
                    status=False
            else:
                response="Required field 'tag' not supplied"
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    # below has been 'moved' to utils/status
    def get_status(self, request_id=None):
        """
        This method will get the exact status from queue, depends on the request ID.
        """
        status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
        if status:
            message = []
            for record in status:
                if 'read' in record:
                    if record['read'] == 0:
                        if 'message' in record:
                            if record['message'] == "EOF":
                                Status().del_messages(request_id)
                            else:
                                created, *_ = record['created'].split('.') + [None]
                                message.append(created + " :: " + record['message'])
            response = {'message': (';;').join(message) }
            Status().mark_messages_read(request_id)
            return True, response
        return False, 'No data for this request'
