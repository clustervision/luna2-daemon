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
This Is the osimage Class, which takes care of images

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import re
import os
import sys
import threading
from time import sleep
import concurrent.futures
from base64 import b64decode, b64encode
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT
from utils.helper import Helper
from utils.status import Status
from utils.queue import Queue
from utils.request import Request


class OsImage(object):
    """Class for operating with osimages records"""

    def __init__(self):
        """
        room for comments/help
        """

        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.osimage_plugins = Helper().plugin_finder(f'{plugins_path}/osimage')
        self.boot_plugins = Helper().plugin_finder(f'{plugins_path}/boot')


    # ---------------------------------------------------------------------------

    def grab_osimage(self,taskid,request_id):

        self.logger.info("grab_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,node,osimage,nodry,noeof,*_=details['task'].split(':')+[None]+[None]+[None]+[None]
            runtype='DRY RUN'
            if not nodry:
                nodry=False
                runtype='REAL/NODRY RUN'
            nodry = Helper().make_bool(nodry)

            if action == "grab_osimage":
                image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: Image {osimage} does not exist?")
                    return False

                dbnode = Database().get_record_join(['node.name as nodename', 'group.name as groupname'], ['group.id=node.groupid'], [f'node.name="{node}"'])
                if not dbnode:
                    Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: Node {node} does not exist?")
                    return False

                if not image[0]['path']:
                    filesystem_plugin = 'default'
                    if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                        filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                    os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                    ret, data = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                    if ret is True:
                        image[0]['path'] = data
                    else:
                        Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: Image path not defined")
                        return False

                image_path = str(image[0]['path'])
                if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
                    if len(image_directory) > 1:
                        image_path = f"{image_directory}/{image[0]['path']}"
                    else:
                        Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined")
                        return False

                if image_path == "/" or image_path == "." or image_path == "..":
                    Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: image path {image_path} is invalid or dangerous")
                    return False

                if not os.path.exists(image_path):
                    os.mkdir(image_path, 0o755)

                distribution = str(image[0]['distribution']) or 'redhat'
                distribution=distribution.lower()

                # loading the plugin depending on OS
                os_grab_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/operations/osgrab',[dbnode[0]['nodename'],distribution,osimage,dbnode[0]['groupname']])

                #------------------------------------------------------
                grab_fs=[]
                grab_ex=[]
                regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
                if image[0]['grab_filesystems']:
                    if regex.match(image[0]['grab_filesystems']):
                        data = b64decode(image[0]['grab_filesystems'])
                        try:
                            image[0]['grab_filesystems'] = data.decode("ascii")
                        except:
                            # apparently we were not base64! it can happen when a string seems like base64 but is not.
                            # is it safe to assume we can then just pass what's in the DB?
                            pass
                    for char in [' ',',,','\r\n','\n']:
                        image[0]['grab_filesystems']=image[0]['grab_filesystems'].replace(char,',')
                    grab_fs=image[0]['grab_filesystems'].split(",")
                if image[0]['grab_exclude']:
                    if regex.match(image[0]['grab_exclude']):
                        data = b64decode(image[0]['grab_exclude'])
                        try:
                            image[0]['grab_exclude'] = data.decode("ascii")
                        except:
                            # apparently we were not base64! it can happen when a string seems like base64 but is not.
                            # is it safe to assume we can then just pass what's in the DB?
                            pass
                    for char in [' ',',,','\r\n','\n']:
                        image[0]['grab_exclude']=image[0]['grab_exclude'].replace(char,',')
                    grab_ex=image[0]['grab_exclude'].split(",")
                Status().add_message(request_id,"luna",f"grabbing osimage {osimage} [{runtype}]")
                response=os_grab_plugin().grab(
                                            osimage=osimage,
                                            image_path=image_path,
                                            node=dbnode[0]['nodename'],
                                            grab_filesystems=grab_fs,
                                            grab_exclude=grab_ex,
                                            nodry=nodry)
                ret=response[0]
                mesg=response[1]
                kernel_version=None
                if len(response)>2:
                    kernel_version=response[2]
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if ret is True:
                    self.logger.info(f'OS image {osimage} grabbing successfully.')
                    if kernel_version:
                        row = [{"column": "kernelversion", "value": kernel_version}]
                        where = [{"column": "id", "value": f"{image[0]['id']}"}]
                        status = Database().update('osimage', row, where)
                    Status().add_message(request_id,"luna",f"finished grabbing osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} grab error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error grabbing osimage {osimage}: {mesg}")
                
                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"grab_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Grabbing failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"grab_osimage has problems during exception handling: {nexp}")
            return False
            

    # ---------------------------------------------------------------------------

    def pack_osimage(self,taskid,request_id):

        self.logger.info("pack_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=details['task'].split(':')+[None]+[None]

            if action == "pack_osimage":
                image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: Image {osimage} does not exist?")
                    return False

                if not image[0]['path']:
                    filesystem_plugin = 'default'
                    if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                        filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                    os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                    ret, data = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                    if ret is True:
                        image[0]['path'] = data
                    else:
                        Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: Image path not defined")
                        return False
                if ('kernelversion' not in image[0]) or (image[0]['kernelversion'] is None):
                    Status().add_message(request_id,"luna",f"error assembling kernel and/or ramdisk for osimage {osimage}: Kernel version not defined")
                    return False

                image_path = str(image[0]['path'])
                if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
                    if len(image_directory) > 1:
                        image_path = f"{image_directory}/{image[0]['path']}"
                    else:
                        Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined")
                        return False

                files_path = CONSTANT['FILES']['IMAGE_FILES']
       
                kernel_version = str(image[0]['kernelversion'])
                distribution = 'redhat'
                if image[0]['distribution']:
                    distribution = str(image[0]['distribution'])
                distribution=distribution.lower()
                osrelease = 'default'
                if image[0]['osrelease']:
                    osrelease = str(image[0]['osrelease'])

                kernel_modules = []
                if image[0]['kernelmodules']:
                    kernel_modules = image[0]['kernelmodules'].split(',')

                # loading the plugin depending on OS
                os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/operations/image',distribution,osrelease)

                #------------------------------------------------------
                Status().add_message(request_id,"luna",f"assembling kernel and ramdisk for osimage {osimage}")
                response=os_image_plugin().pack(
                                            osimage=osimage,
                                            image_path=image_path,
                                            files_path=files_path,
                                            kernel_version=kernel_version,
                                            kernel_modules=kernel_modules)
                ret=response[0]
                mesg=response[1]
                kernel_file,ramdisk_file=None,None
                if len(response)>2:
                    kernel_file=response[2]
                if len(response)>3:
                    ramdisk_file=response[3]
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if ret is True:
                    self.logger.info(f'OS image {osimage} kernel and ramdisk assembled successfully.')
                    row = [{"column": "kernelfile", "value": kernel_file},
                           {"column": "initrdfile", "value": ramdisk_file}]
                    where = [{"column": "id", "value": f"{image[0]['id']}"}]
                    status = Database().update('osimage', row, where)
                    Status().add_message(request_id,"luna",f"finished assembling kernel and ramdisk for osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} assemble error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: {mesg}")
                
                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"pack_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"pack_osimage has problems during exception handling: {nexp}")
            return False
            
    # ---------------------------------------------------------------------------

    def build_osimage(self,taskid,request_id):

        self.logger.info("build_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=details['task'].split(':')+[None]+[None]

            if action == "build_osimage":
                image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    Status().add_message(request_id,"luna",f"error packing osimage {osimage}: Image {osimage} does not exist?")
                    return False

                if not image[0]['path']:
                    filesystem_plugin = 'default'
                    if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                        filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                    os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                    ret, data = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                    if ret is True:
                        image[0]['path'] = data
                    else:
                        Status().add_message(request_id,"luna",f"error packing osimage {osimage}: Image path not defined")
                        return False

                image_path = str(image[0]['path'])
                if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
                    if len(image_directory) > 1:
                        image_path = f"{image_directory}/{image[0]['path']}"
                    else:
                        Status().add_message(request_id,"luna",f"error packing osimage {osimage}: image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined")
                        return False

                distribution = str(image[0]['distribution']) or 'redhat'
                distribution=distribution.lower()
                osrelease = 'default'
                if image[0]['osrelease']:
                    osrelease = str(image[0]['osrelease'])

                files_path = CONSTANT['FILES']['IMAGE_FILES']
                tmp_directory = CONSTANT['FILES']['TMP_DIRECTORY']
        
                # loading the plugin depending on OS
                os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/operations/image',distribution,osrelease)

                Status().add_message(request_id,"luna",f"building osimage {osimage}")
                response=os_image_plugin().build(
                                       osimage=osimage,
                                       image_path=image_path,
                                       files_path=files_path,
                                       tmp_directory=tmp_directory)
                ret=response[0]
                mesg=response[1]
                image_file=None
                if len(response)>2:
                    image_file=response[2]
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if ret is True:
                    self.logger.info(f'OS image {osimage} build successfully.')
                    row = [{"column": "imagefile", "value": image_file}]
                    where = [{"column": "id", "value": f"{image[0]['id']}"}]
                    status = Database().update('osimage', row, where)
                    Status().add_message(request_id,"luna",f"finished building osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} build error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error building osimage {osimage}: {mesg}")
                
                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"build_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"build_osimage has problems during exception handling: {nexp}")
            return False
            
    # ---------------------------------------------------------------------------

    def copy_osimage(self,taskid,request_id):

        self.logger.info("copy_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,src,tag,dst,noeof,*_=details['task'].split(':')+[None]+[None]+[None]

            if tag and tag == "None":
                tag = None

            if action == "copy_osimage" or action == "clone_osimage":
                Status().add_message(request_id,"luna",f"copying osimage {src}->{dst}")
   
                # --- let's copy

                srcimage,dstimage,mesg=None,None,None
                if src and dst:
                    image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
                    srcimage = Database().get_record(None, 'osimage', f"WHERE name='{src}'")
                    dstimage = Database().get_record(None, 'osimage', f"WHERE name='{dst}'")
                    distribution = str(dstimage[0]['distribution']) or 'redhat'
                    distribution=distribution.lower()
                    osrelease = str(dstimage[0]['osrelease']) or 'default.py'
                    if srcimage and dstimage:
                        # loading the plugin depending on setting in luna.ini
                        filesystem_plugin = 'default'
                        if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                            filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                        os_clone_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                        if (not srcimage[0]['path']) or srcimage[0]['tagid'] or tag:
                            tagname = tag or None
                            if (not tag) and srcimage[0]['tagid']:
                                tagname = Database().name_by_id('osimagetag', srcimage[0]['tagid'])
                            ret, data = os_clone_plugin().getpath(image_directory=image_directory, osimage=srcimage[0]['name'], tag=tagname)
                            if ret is True:
                                srcimage[0]['path'] = data
                        if not dstimage[0]['path']:
                            ret, data = os_clone_plugin().getpath(image_directory=image_directory, osimage=dstimage[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                            if ret is True:
                                dstimage[0]['path'] = data
                        if not os.path.exists(srcimage[0]['path']):
                            mesg=f"{src}:{srcimage[0]['path']} does not exist"
                        elif dstimage[0]['path'] and len(dstimage[0]['path'])>1:
                            if srcimage[0]['path'] == dstimage[0]['path']:
                                mesg=f"{src}:{srcimage[0]['path']} and {dst}:{dstimage[0]['path']} are the same"
                            else:
                                exit_code=0
                                if not os.path.exists(dstimage[0]['path']):
                                    command=f"mkdir -p \"{dstimage[0]['path']}\""
                                    mesg,exit_code = Helper().runcommand(command,True,10)
                                if exit_code == 0:
                                    self.logger.info(f"Copy image from \"{srcimage[0]['path']}\" to \"{dstimage[0]['path']}\"")
                                    response=os_clone_plugin().clone(source=srcimage[0]['path'],destination=dstimage[0]['path'])
                                    result=response[0]
                                    mesg=response[1]

                    sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                    if result is True:
                        self.logger.info(f'OS image copied successfully.')
                        Status().add_message(request_id,"luna","finished copying osimage")

                    else:
                        self.logger.info(f'Copy osimage {src}->{dst} error: {mesg}.')
                        Status().add_message(request_id,"luna",f"error copying osimage: {mesg}")

                else:
                    self.logger.info(f'Copy osimage src and/or dst not provided.')
                    Status().add_message(request_id,"luna","error copying osimage as 'src' and/or 'dst' not provided.")

                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
                return result
            else:
                self.logger.info(f"{details['task']} is not for us.")

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"copy_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"copy_osimage has problems during exception handling: {nexp}")
            return False 
 
    # ---------------------------------------------------------------------------

    def push_osimage(self,taskid,request_id,object='node'):

        self.logger.info("push_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,dst,osimage,nodry,noeof,*_=details['task'].split(':')+[None]+[None]+[None]
            runtype='DRY RUN'
            if not nodry:
                nodry=False
                runtype='REAL/NODRY RUN'
            nodry = Helper().make_bool(nodry)

            if action == "push_osimage_to_node" or action == "push_osimage_to_group":
                Status().add_message(request_id,"luna",f"pushing osimage {osimage}->{object} {dst} [{runtype}]")
   
                # --- let's push

                image,mesg=None,None
                if osimage and dst:
                    image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                    if image:
                        distribution = str(image[0]['distribution']) or 'redhat'
                        distribution=distribution.lower()
                        grab_fs=[]
                        grab_ex=[]
                        regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
                        if image[0]['grab_filesystems']:
                            if regex.match(image[0]['grab_filesystems']):
                                data = b64decode(image[0]['grab_filesystems'])
                                try:
                                    image[0]['grab_filesystems'] = data.decode("ascii")
                                except:
                                    # apparently we were not base64! it can happen when a string seems like base64 but is not.
                                    # is it safe to assume we can then just pass what's in the DB?
                                    pass
                            for char in [' ',',,','\r\n','\n']:
                                image[0]['grab_filesystems']=image[0]['grab_filesystems'].replace(char,',')
                            grab_fs=image[0]['grab_filesystems'].split(",")
                        if image[0]['grab_exclude']:
                            if regex.match(image[0]['grab_exclude']):
                                data = b64decode(image[0]['grab_exclude'])
                                try:
                                    image[0]['grab_exclude'] = data.decode("ascii")
                                except:
                                    # apparently we were not base64! it can happen when a string seems like base64 but is not.
                                    # is it safe to assume we can then just pass what's in the DB?
                                    pass
                            for char in [' ',',,','\r\n','\n']:
                                image[0]['grab_exclude']=image[0]['grab_exclude'].replace(char,',')
                            grab_ex=image[0]['grab_exclude'].split(",")
                    else:
                        self.logger.info(f'Push osimage {osimage} does not exist.')
                        Status().add_message(request_id,"luna",f"error pushing osimage as osimage {osimage} does not exist.")
                        return False

                    if not image[0]['path']:
                        filesystem_plugin = 'default'
                        if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                            filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                        os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                        ret, data = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                        if ret is True:
                            image[0]['path'] = data
                        else:
                            Status().add_message(request_id,"luna",f"error pushing osimage {osimage}: Image path not defined")
                            return False

                    if not os.path.exists(image[0]['path']):
                        mesg=f"{osimage}:{image[0]['path']} does not exist"
                    elif image[0]['path'] and len(image[0]['path'])>1:
                        if object == 'node':
                            dbnode = Database().get_record_join(['node.name as nodename', 'group.name as groupname'], ['group.id=node.groupid'], [f'node.name="{dst}"'])
                            if not dbnode:
                                Status().add_message(request_id,"luna",f"error pushing osimage {osimage}: Node {dst} does not exist?")
                                return False
                            # loading the plugin depending on OS
                            os_push_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/operations/ospush',[dbnode[0]['nodename'],distribution,osimage,dbnode[0]['groupname']])

                            self.logger.info(f"Push image from \"{image[0]['path']}\" to \"{dst}\"")
                            response=os_push_plugin().push(osimage=osimage,
                                                         image_path=image[0]['path'],
                                                         node=dst,
                                                         grab_filesystems=grab_fs,
                                                         grab_exclude=grab_ex,
                                                         nodry=nodry)
                            result=response[0]
                            mesg=response[1]

                        if object == 'group':
                            dbnodes = Database().get_record_join(['node.name as nodename'], ['group.id=node.groupid'], [f'`group`.name="{dst}"'])
                            if not dbnodes:
                                Status().add_message(request_id,"luna",f"error pushing osimage {osimage}: Group {dst} does not exist?")
                                return False
                            os_push_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/operations/ospush',[distribution,osimage,dst])

                            try:
                                batch=10
                                delay=0
                                result=True  # as i report individual results in status
                                pipeline = Helper().Pipeline()
                                for dbnode in dbnodes:
                                    nodename=dbnode['nodename']
                                    pipeline.add_nodes({nodename: 'ospush'})
                                while pipeline.has_nodes():

                                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                                        _ = [executor.submit(self.ospush_child, pipeline, t, os_push_plugin, osimage, image[0]['path'], grab_fs, grab_ex, nodry) for t in range(1,batch)]

                                    sleep(0.1) # not needed but just in case a child does a lock right after i fetch the list.
                                    results=pipeline.get_messages()

                                    for key in list(results):
                                        self.logger.info(f"ospush_mother result: {key}: {results[key]}")
                                        ret,mesg,*_ = (results[key].split('=')+[None]+[None])
                                        if ret is True or ret == "True":
                                            Status().add_message(request_id,"luna",f"{key}:success")
                                        else:
                                            Status().add_message(request_id,"luna",f"{key}:Failed -> {mesg}")
                                        pipeline.del_message(key)
                                    sleep(delay)

                            except Exception as exp:
                                self.logger.error(f"ospush_mother has problems: {exp}")


                    sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                    if result is True:
                        self.logger.info(f'OS image pushed successfully.')
                        Status().add_message(request_id,"luna","finished pushing osimage")

                    else:
                        self.logger.info(f'Push osimage {osimage}->{dst} error: {mesg}.')
                        Status().add_message(request_id,"luna",f"error pushing osimage: {mesg}")

                else:
                    self.logger.info(f'Push osimage src and/or dst not provided.')
                    Status().add_message(request_id,"luna","error pushing osimage as 'osimage' and/or 'destination' not provided.")

                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
                return result
            else:
                self.logger.info(f"{details['task']} is not for us.")

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"push_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Pushing failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"push_osimage has problems during exception handling: {nexp}")
            return False 
 
    # ---------------------------------------------------------------------------

    def provision_osimage(self,taskid,request_id):

        self.logger.info("provision_osimage called")
        try:

            result,mesg=False,None
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=details['task'].split(':')+[None]+[None]

            if action == "provision_osimage":
                Status().add_message(request_id,"luna",f"creating provisioning for osimage {osimage}")
   
                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    result=False
                    mesg=f"Image {osimage} does not exist?"
                    
                else:
                    cluster_provision_methods=[]
                    cluster = Database().get_record(None, 'cluster', None)
                    if cluster:
                        cluster_provision_methods.append(cluster[0]['provision_method'])
                        cluster_provision_methods.append(cluster[0]['provision_fallback'])
                    else:
                        cluster_provision_methods.append('http')

                    image_id=image[0]['id']
                    if (not 'imagefile' in image[0]) and (not image[0]['imagefile']):
                        mesg=f"Imagefile for {osimage} does not exist?"
                        return False
           
                    server_ipaddress,server_port,server_protocol=None,None,None
                    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
                    if controller:
                        server_ipaddress = controller[0]['ipaddress']
                        server_port     = controller[0]['serverport']
                        server_protocol = CONSTANT['API']['PROTOCOL']
         
                    files_path = CONSTANT['FILES']['IMAGE_FILES']

                    for method in cluster_provision_methods:
                        provision_plugin=Helper().plugin_load(self.boot_plugins,'boot/provision',method)
                        ret,mesg=provision_plugin().create(image_file=image[0]['imagefile'],
                                                          files_path=files_path,
                                                          server_ipaddress=server_ipaddress,
                                                          server_port=server_port,
                                                          server_protocol=server_protocol)

                        sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                        if ret:
                            Status().add_message(request_id,"luna",f"created {method} provisioning for osimage {osimage}")
                            self.logger.info(f'created {method} provisioning for osimage {osimage}')
                            mesg=f"Success for {image[0]['imagefile']}"
                        else:
                            Status().add_message(request_id,"luna",f"failed creating {method} provisioning for osimage {osimage}")
                            self.logger.info(f'failed creating {method} provisioning for osimage {osimage}')
 
                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return True

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"provision_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Create provision failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"provision_osimage has problems during exception handling: {nexp}")
            return False

    # -------------------------------------------------------------------

    def unpack_osimage(self,taskid,request_id):

        self.logger.info("unpack_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=details['task'].split(':')+[None]+[None]

            if action == "unpack_osimage":
                image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    Status().add_message(request_id,"luna",f"error unpacking osimage {osimage}: Image {osimage} does not exist?")
                    return False

                filesystem_plugin = 'default'
                if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                    filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
                if not image[0]['path']:
                    os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
                    ret, data = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
                    if ret is True:
                        image[0]['path'] = data
                    else:
                        Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: Image path not defined")
                        return False

                image_path = str(image[0]['path'])
                if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
                    if len(image_directory) > 1:
                        image_path = f"{image_directory}/{image[0]['path']}"
                    else:
                        Status().add_message(request_id,"luna",f"error unpacking osimage {osimage}: image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined")
                        return False

                files_path = CONSTANT['FILES']['IMAGE_FILES']
                tmp_directory = CONSTANT['FILES']['TMP_DIRECTORY']
                image_file = str(image[0]['imagefile'])

                # loading the plugin depending on OS
                os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)

                #------------------------------------------------------
                Status().add_message(request_id,"luna",f"unpacking osimage {osimage}")
                response=os_image_plugin().extract(
                                            image_path=image_path,
                                            files_path=files_path,
                                            image_file=image_file,
                                            tmp_directory=tmp_directory)
                ret=response[0]
                mesg=response[1]
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if ret is True:
                    self.logger.info(f'OS image {osimage} unpacked successfully.')
                    Status().add_message(request_id,"luna",f"finished unpacking osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} unpack error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error assembling osimage {osimage}: {mesg}")
                
                if not noeof:
                    Status().add_message(request_id,"luna","EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"unpack_osimage has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Unpacking failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"unpack_osimage has problems during exception handling: {nexp}")
            return False

    # -------------------------------------------------------------------
  
    def cleanup_file(self,file_to_remove):
        self.logger.info(f"I was called to cleanup old file: {file_to_remove}")
        inuse = Database().get_record(None, 'osimage', f"WHERE kernelfile='{file_to_remove}' or initrdfile='{file_to_remove}' or imagefile='{file_to_remove}'")
        if inuse:
            return False, f"will not remove {file_to_remove} as it is still in use by {inuse[0]['name']}"
        else:
            inusebytag = Database().get_record(None, 'osimagetag', f"WHERE kernelfile='{file_to_remove}' or initrdfile='{file_to_remove}' or imagefile='{file_to_remove}'")
            if inusebytag:
                return False, f"will not remove {file_to_remove} as it is still in use by tag {inusebytag[0]['name']}"
        files_path = CONSTANT['FILES']['IMAGE_FILES']
        os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/other','cleanup')
        ret,mesg=os_image_plugin().cleanup(files_path=files_path,file_to_remove=file_to_remove)
        return ret, mesg

    # -------------------------------------------------------------------

    def cleanup_provisioning(self,image_file):
        self.logger.info(f"I was called to cleanup old provisioning: {image_file}")
        inuse = Database().get_record(None, 'osimage', f"WHERE imagefile='{image_file}'")
        if inuse:
            return False, f"will not remove {image_file} as it is still in use by {inuse[0]['name']}"
        else:
            inusebytag = Database().get_record(None, 'osimagetag', f"WHERE imagefile='{image_file}'")
            if inusebytag:
                return False, f"will not remove {image_file} as it is still in use by tag {inusebytag[0]['name']}"
        cluster_provision_methods=[]
        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            cluster_provision_methods.append(cluster[0]['provision_method'])
            cluster_provision_methods.append(cluster[0]['provision_fallback'])
        else:
            cluster_provision_methods.append('http')
        files_path = CONSTANT['FILES']['IMAGE_FILES']
        for method in cluster_provision_methods:
            provision_plugin=Helper().plugin_load(self.boot_plugins,'boot/provision',method)
            ret,mesg=provision_plugin().cleanup(files_path=files_path, image_file=image_file)
        return ret, mesg

    # ------------------------------------------------------------------- 
  
    def schedule_cleanup(self,osimage,request_id=None): 
        if not request_id:
            request_id='__internal__'
        queue_id=None
        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if image:
            for item in ['kernelfile','initrdfile','imagefile']:
                if image[0][item]:
                    inusebytag = Database().get_record(None, 'osimagetag', f"WHERE osimageid='{image[0]['id']}' AND {item}='"+image[0][item]+"'")
                    if not inusebytag:
                        queue_id,queue_response = Queue().add_task_to_queue(f'cleanup_old_file:'+image[0][item],'housekeeper',request_id,None,'1h')
                        if item == 'imagefile':
                            queue_id,queue_response = Queue().add_task_to_queue(f'cleanup_old_provisioning:'+image[0][item],'housekeeper',request_id,None,'1h')
        return queue_id

    def schedule_provision(self,osimage,subsystem=None,request_id=None):
        if not request_id:
            request_id='__internal__'
        if not subsystem:
            subsystem='osimage'
        queue_id,queue_response = Queue().add_task_to_queue(f"provision_osimage:{osimage}",subsystem,request_id)
        return queue_id

    # ------------------------------------------------------------------- 
    # The mother of all.

    def osimage_mother(self,only_request_id=None):

        self.logger.info(f"osimage_mother called with request_id {only_request_id}")
        try:

#            # Below section is already done in config/pack GET call but kept here in case we want to move it back
#            queue_id,response = Queue().add_task_to_queue(f'pack_n_build_osimage:{osimage}','osimage',request_id)
#            if not queue_id:
#                self.logger.info(f"pack_n_build_mother cannot get queue_id")
#                Status().add_message(request_id,"luna",f"error queuing my task")
#                return
#            self.logger.info(f"pack_n_build_mother added task to queue: {queue_id}")
#            Status().add_message(request_id,"luna",f"queued pack osimage {osimage} with queue_id {queue_id}")
#
#            next_id = Queue().next_task_in_queue('osimage')
#            if queue_id != next_id:
#                # little tricky. we assume that another mother proces was spawned that took care of the runs... 
#                # we need a check based on last hear queue entry, then we continue. pending in next_task_in_queue.
#                return

#           we make the whole step process as tasks. benefit is that we can add multiple independent but also dependent tasks.
#           a bit of a draw back is that the placeholder tasks has to remain in the queue (so that other similar CLI requests will be ditched)
#           we clean up the placeholder request as a last task to do. it's like eating its own tail :)  --Antoine

            while next_id := Queue().next_task_in_queue('osimage','queued',only_request_id):
                details=Queue().get_task_details(next_id)
                request_id=details['request_id']
                action,first,second,third,*_=details['task'].split(':')+[None]+[None]+[None]
                self.logger.info(f"osimage_mother sees job {action} in queue as next: {next_id}")

                if action == "clone_n_pack_osimage":
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if first and second:
                        queue_id,queue_response = Queue().add_task_to_queue(f"copy_osimage:{first}:{second}:{third}:noeof",'osimage',request_id)
                        if queue_id:
                            queue_id,queue_response = Queue().add_task_to_queue(f"pack_n_build_osimage:{third}:nocleanup",'osimage',request_id)
                            if queue_id:
                                queue_id,queue_response = Queue().add_task_to_queue(f"close_task:{next_id}",'osimage',request_id)

                elif action == "pack_n_build_osimage" or action == "pack_n_tar_osimage":  # in future, pack_n_tar should go. only pack_n_build stays. it's just here for legacy reasons. pending
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if first:
                        queue_id,queue_response = Queue().add_task_to_queue(f"pack_osimage:{first}:noeof",'osimage',request_id)
                        if queue_id:
                            queue_id,queue_response = Queue().add_task_to_queue(f"build_osimage:{first}:noeof",'osimage',request_id)
                            if queue_id:
                                queue_id,queue_response = Queue().add_task_to_queue(f"provision_osimage:{first}",'osimage',request_id)
                                if queue_id:
                                    if (not second) or (second != "nocleanup"):
                                        self.schedule_cleanup(first,request_id)
                                    if queue_id:
                                        queue_id,queue_response = Queue().add_task_to_queue(f"close_task:{next_id}",'osimage',request_id)

                elif action == "grab_n_pack_n_build_osimage":
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if first and second:
                        queue_id,queue_response = Queue().add_task_to_queue(f"grab_osimage:{first}:{second}:noeof",'osimage',request_id)
                        if queue_id:
                            queue_id,queue_response = Queue().add_task_to_queue(f"pack_n_build_osimage:{second}",'osimage',request_id)
                            if queue_id:
                                queue_id,queue_response = Queue().add_task_to_queue(f"close_task:{next_id}",'osimage',request_id)


                # below are internal calls.

                elif action == "copy_osimage" or action == "clone_osimage":
                    if first and second:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.copy_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")
 
                elif action == "pack_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.pack_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "build_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.build_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "provision_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.provision_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "grab_osimage":
                    if first and second:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.grab_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "push_osimage_to_group":
                    if first and second:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.push_osimage(next_id,request_id,'group')
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "push_osimage_to_node":
                    if first and second:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.push_osimage(next_id,request_id,'node')
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna","EOF")

                elif action == "close_task" and first:
                    Queue().remove_task_from_queue(first)
                    Queue().remove_task_from_queue(next_id)

                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)


            # parked tasks are there to be there. it should be seen as a placeholder for something else.
            while next_id := Queue().next_task_in_queue('osimage','parked',only_request_id):
                details=Queue().get_task_details(next_id)
                request_id=details['request_id']
                action,first,second,third,*_=details['task'].split(':')+[None]+[None]+[None]
                self.logger.info(f"osimage_mother sees parked job {action} in queue as next: {next_id}")

                # though we have this task, it's there to make sure all image related activities are done
                # before we continue let the housekeeper do this. The housekeeper will then send this
                # pull request to the other controllers (H/A mode)
                if action == "sync_osimage_with_master":
                    if first and second:
                        Queue().change_subsystem(next_id,'housekeeper')
                        Queue().update_task_status_in_queue(next_id,'queued')

                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)


        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"osimage_mother has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            try:
                Status().add_message(request_id,"luna",f"Operation failed: {exp}")
                Status().add_message(request_id,"luna","EOF")
            except Exception as nexp:
                self.logger.error(f"osimage_mother has problems during exception handling: {nexp}")
           
        self.logger.info(f"osimage_mother finished with request_id {only_request_id}")

    # ---------------------- child for bulk parallel operations --------------------------------

    def ospush_child(self,pipeline,t,def_plugin,osimage,image_path,grab_fs,grab_ex,nodry):
        nodename,action=pipeline.get_node()
        self.logger.info("control_child thread "+str(t)+" called for: "+nodename+" ospush")
        if nodename:
            response=def_plugin().push(osimage=osimage,image_path=image_path,node=nodename,
                                           grab_filesystems=grab_fs,
                                           grab_exclude=grab_ex,nodry=nodry)
            result=response[0]
            mesg=response[1]
            pipeline.add_message({nodename: f"{result}={mesg}"})

