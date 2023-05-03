#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

import os
import pwd
import subprocess
import shutil
import queue
import json
import ipaddress
from configparser import RawConfigParser
from netaddr import IPNetwork
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT, LUNAKEY
from utils.helper import Helper
import concurrent.futures
import threading
from time import sleep, time
from datetime import datetime
import sys
import uuid
import shutil
from utils.status import Status
from utils.queue import Queue
from utils.torrent import Torrent


class OsImage(object):
    """Class for operating with osimages records"""

    def __init__(self):
        """
        path      - path to / of the image (will be converted to absolute)
        kernver   - kernel version (will be checked on creation)
        kernopt   - kernel options
        grab_list - rsync exclude list for grabbing live node to image
        """

        self.logger = Log.get_logger()



    def create_tarball(self,osimage):

        if 'FILES' not in CONSTANT:
            return False,"FILES config setting not defined"
        if 'TARBALL' not in CONSTANT['FILES']:
            return False,"TARBALL config setting not defined in FILES"
        path_to_store = CONSTANT['FILES']['TARBALL']

        #user = cluster.get('user')  # left in for future use if we want to run the daemon as non-root
        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
            os.chown(path_to_store, user_id, grp_id)
            os.chmod(path_to_store, 0o755)

        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if not image:
            return False,f"Image {osimage} does not exist?"

        image_id=image[0]['id']  # we might need it later. at least once at the bottom

        if ('path' not in image[0]) or (image[0]['path'] is None):
            return False,"Image path not defined"

        image_path = image[0]['path']
        if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
            if 'IMAGE_DIRECTORY' in CONSTANT['FILES']:
                image_path = f"{CONSTANT['FILES']['IMAGE_DIRECTORY']}/{image[0]['path']}"
            else:
                return False,f"image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined"

        if not os.path.exists(image_path):
            return False,f"Image path {image_path} does not exist"

        #uid = str(uuid.uuid4())
        epoch_time = int(time())
        tarfile = f"{osimage}-{epoch_time}.tar.bz2"

        if not os.path.exists('/usr/bin/tar'):
            return False,"/usr/bin/tar does not exist. please install tar"
        if not os.path.exists('/usr/bin/lbzip2'):
            return False,"/usr/bin/lbzip2 does not exist. please install lbzip2"

        try:
            self.logger.debug(f"/usr/bin/tar -C {image_path} --one-file-system --xattrs --selinux --acls --checkpoint=100000 --use-compress-program=/usr/bin/lbzip2 -c -f /tmp/{tarfile} .")

            try:
                output = subprocess.check_output(
                    [
                        '/usr/bin/tar',
                        '-C', f"{image_path}",
                        '--one-file-system',
                        '--xattrs',
                        '--selinux',
                        '--acls',
                        '--ignore-failed-read',
                        '--exclude=/proc/*',
                        '--exclude=/dev/*',
                        '--exclude=/sys/*',
                        '--checkpoint=100000',
                        '--use-compress-program=/usr/bin/lbzip2',
                        '-c', '-f', '/tmp/' + tarfile, '.'
                    ],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True)
            except subprocess.CalledProcessError as exc:
                self.logger.info(f"Tarring failed with exit code {exc.returncode} {exc.output}:")
                if os.path.isfile('/tmp/' + tarfile):
                    os.remove('/tmp/' + tarfile)
                output=f"{exc.output}"
                outputs=output.split("\n")
                joined='. '.join(outputs[-5:])
                return False,f"Tarring {osimage} failed with exit code {exc.returncode}: {joined}"
            else:
                self.logger.info(f"Tarring {osimage} successful.")


        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_type == exceptions.KeyboardInterrupt:
                self.logger.error('Keyboard interrupt.')
            else:
                self.logger.error(exc_value)
                self.logger.debug(traceback.format_exc())

            if os.path.isfile('/tmp/' + tarfile):
                os.remove('/tmp/' + tarfile)

            sys.stdout.write('\r')

            return False,"Tar went bonkers"

        # copy image, so permissions and selinux contexts
        # will be inherited from parent folder

        try:
            shutil.copy(f"/tmp/{tarfile}", path_to_store)
            os.remove(f"/tmp/{tarfile}")
            os.chown(path_to_store + '/' + tarfile, user_id, grp_id)
            os.chmod(path_to_store + '/' + tarfile, 0o644)
        except Exception as error:
            return False,f"Moving {osimage} tarbal failed with {error}"

        row = [{"column": "tarball", "value": f"{tarfile}"}]
        where = [{"column": "id", "value": f"{image_id}"}]
        status = Database().update('osimage', row, where)

        return True,"Success for {tarfile}"




    """
    Antoine: kept here so i know how the columns are named
    `id`  INTEGER  NOT NULL ,  
    `name`  VARCHAR ,  
    `dracutmodules`  VARCHAR ,  
    `grab_filesystems`  VARCHAR ,  
    `grab_exclude`  TEXT ,  
    `initrdfile`  VARCHAR ,  
    `kernelfile`  VARCHAR ,  
    `kernelmodules`  VARCHAR ,  
    `kerneloptions`  VARCHAR ,  
    `kernelversion`  VARCHAR ,  
    `path`  VARCHAR ,  
    `tarball`  VARCHAR ,  
    `torrent`  VARCHAR ,  
    `distribution`  VARCHAR ,  
    `comment`  VARCHAR , 
    PRIMARY KEY (`id` AUTOINCREMENT), UNIQUE (`name`)
    """

    def pack_image_rhel(self,osimage):

        def mount(source, target, fs):
            try:
                subprocess.Popen(['/usr/bin/mount', '-t', fs, source, target])
            except Exception as error:
                self.logger(f"Mount {target} failed with {error}")

        def umount(source):
            try:
                subprocess.Popen(['/usr/bin/umount', source])
            except Exception as error:
                self.logger(f"Umount {target} failed with {error}")

        def prepare_mounts(path):
            mount('devtmpfs', f"{path}/dev", 'devtmpfs')
            mount('proc', f"{path}/proc", 'proc')
            mount('sysfs', f"{path}/sys", 'sysfs')

        def cleanup_mounts(path):
            umount(f"{path}/dev")
            umount(f"{path}/proc")
            umount(f"{path}/sys")

        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if not image:
            return False,f"Image {osimage} does not exist?"

        if ('path' not in image[0]) or (image[0]['path'] is None):
            return False,"Image path not defined"
        if ('kernelversion' not in image[0]) or (image[0]['kernelversion'] is None):
            return False,"Kernel version not defined"

        ##path_to_store = f"{image[0]['path']}/boot"  # <-- we will store all files in this path, but add the name of the image to it.
        if 'FILES' not in CONSTANT:
            return False,"FILES config setting not defined"
        if 'TARBALL' not in CONSTANT['FILES']:
            return False,"TARBALL config setting not defined in FILES"
        path_to_store = CONSTANT['FILES']['TARBALL']

        tmp_path = '/tmp'  # in chroot env
        image_path = str(image[0]['path'])
        if not os.path.exists(image_path):
            return False,f"Image path {image_path} does not exist"

        kernver = str(image[0]['kernelversion'])
        kernfile = f"{osimage}-vmlinuz-{kernver}"
        initrdfile = f"{osimage}-initramfs-{kernver}"
        if ('kernelfile' in image[0]) and (image[0]['kernelfile']):
            kernfile = f"{osimage}-{image[0]['kernelfile']}"
        if ('initrdfile' in image[0]) and (image[0]['initrdfile']):
            initrdfile = f"{osimage}-{image[0]['initrdfile']}"

        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
            #os.chown(path_to_store, user_id, grp_id)

        modules_add = []
        modules_remove = []
        drivers_add = []
        drivers_remove = []
        grab_filesystems = ['/','/boot']
        
        if 'dracutmodules' in image[0] and image[0]['dracutmodules']:
            for i in image[0]['dracutmodules'].split(','):
                s=i.replace(" ", "")
                if s[0] != '-':
                    modules_add.extend(['--add', s])
                else:
                    modules_remove.extend(['--omit', s[1:]])

        if 'kernelmodules' in image[0] and image[0]['kernelmodules']:
            for i in image[0]['kernelmodules'].split(','):
                s=i.replace(" ", "")
                if s[0] != '-':
                    drivers_add.extend(['--add-drivers', s])
                else:
                    drivers_remove.extend(['--omit-drivers', s[1:]])

        prepare_mounts(image_path)
        real_root = os.open("/", os.O_RDONLY)
        os.chroot(image_path)
        chroot_path = os.open("/", os.O_DIRECTORY)
        os.fchdir(chroot_path)

        dracut_succeed = True

        create = None

        try:
            dracut_modules = subprocess.Popen(['/usr/bin/dracut', '--kver',
                                               kernver, '--list-modules'],
                                              stdout=subprocess.PIPE)
            luna_exists = False

            while dracut_modules.poll() is None:
                line = dracut_modules.stdout.readline()
                line_clean=line.strip()
                line_clean=line_clean.decode('ASCII')
                if line_clean == 'luna':
                    luna_exists = True
                    break

            if not luna_exists:
                self.logger.info(f"No luna dracut module in osimage '{osimage}'. I add it as a safe meassure.")
                #return False,"No luna dracut module in osimage"
                modules_add.extend(['--add', 'luna']) # this part is debatable. for now i add this. pending

            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernver] +
                          modules_add + modules_remove + drivers_add +
                          drivers_remove + [tmp_path + '/' + initrdfile])

            create = subprocess.Popen(dracut_cmd, stdout=subprocess.PIPE)
            while create.poll() is None:
                line = create.stdout.readline()

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.info(exc_value)
            #self.logger.debug(traceback.format_exc())
            dracut_succeed = False

        if create and create.returncode:
            dracut_succeed = False

        if not create:
            dracut_succeed = False

        os.fchdir(real_root)
        os.chroot(".")
        os.close(real_root)
        os.close(chroot_path)
        cleanup_mounts(image_path)

        if not dracut_succeed:
            self.logger.info("Error while building initrd.")
            return False,"Problem building initrd"

        initrd_path = image_path + tmp_path + '/' + initrdfile
        kernel_path = image_path + '/boot/vmlinuz-' + kernver

        if not os.path.isfile(kernel_path):
            self.logger.info("Unable to find kernel in {}".format(kernel_path))
            return False,f"Unable to find kernel in {kernel_path}"

        if not os.path.isfile(initrd_path):
            self.logger.info("Unable to find initrd in {}".format(initrd_path))
            return False,f"Unable to find initrd in {initrd_path}"

        # copy initrd file to inherit perms from parent folder
        shutil.copy(initrd_path, path_to_store + '/' + initrdfile)
        os.remove(initrd_path)
        shutil.copy(kernel_path, path_to_store + '/' + kernfile)
        os.chown(path_to_store + '/' + initrdfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + initrdfile, 0o644)
        os.chown(path_to_store + '/' + kernfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + kernfile, 0o644)

        return True,"Success"

    # ---------------------------------------------------------------------------

    def pack_image_based_on_distribution(self,osimage):
        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        distribution='redhat'
        if image and 'distribution' in image[0]:
            distribution=image[0]['distribution'] or 'redhat'
            distribution=distribution.lower()

        # --------------------------- distri switch ---------------------------------

        self.logger.info(f"image {osimage} will be packed based on {distribution}")
        ret,mesg=None,"distribution not supported"
        if distribution == 'rhel' or distribution == 'redhat':
            ret,mesg=self.pack_image_rhel(osimage)
        
        return ret,mesg

    # ---------------------------------------------------------------------------

    def pack_osimage(self,taskid,request_id):

        self.logger.info(f"pack_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=(details['task'].split(':')+[None]+[None])

            if action == "pack_osimage":
                Status().add_message(request_id,"luna",f"packing osimage {osimage}")
   
                # --- let's pack and rack

                ret,mesg=self.pack_image_based_on_distribution(osimage)
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if ret is True:
                    self.logger.info(f'OS image {osimage} packed successfully.')
                    Status().add_message(request_id,"luna",f"finished packing osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} pack error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error packing osimage {osimage}: {mesg}")

                if not noeof:
                    Status().add_message(request_id,"luna",f"EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            self.logger.error(f"pack_osimage has problems: {exp}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna",f"EOF")
            except Exception as nexp:
                self.logger.error(f"pack_osimage has problems during exception handling: {nexp}")
            return False
            
    # ---------------------------------------------------------------------------

    def tar_osimage(self,taskid,request_id):

        self.logger.info(f"tar_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=(details['task'].split(':')+[None]+[None])

            if action == "tar_osimage":
                Status().add_message(request_id,"luna",f"tarring osimage {osimage}")

                ret,mesg=self.create_tarball(osimage)
                sleep(1) # same for this one
                if ret is True:
                    self.logger.info(f'OS image {osimage} tarred successfully.')
                    Status().add_message(request_id,"luna",f"finished tarring osimage {osimage}")
                    result=True
                else:
                    self.logger.info(f'OS image {osimage} tar error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error tarring osimage {osimage}: {mesg}")

                if not noeof:
                    Status().add_message(request_id,"luna",f"EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            self.logger.error(f"pack_n_tar_osimage has problems: {exp}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna",f"EOF")
            except Exception as nexp:
                self.logger.error(f"pack_n_tar_osimage has problems during exception handling: {nexp}")
            return False
            

    # ---------------------------------------------------------------------------

    def copy_osimage(self,taskid,request_id):

        self.logger.info(f"copy_osimage called")
        try:

            result=False
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,src,dst,noeof,*_=(details['task'].split(':')+[None]+[None])

            if action == "copy_osimage":
                Status().add_message(request_id,"luna",f"copying osimage {src}->{dst}")
   
                # --- let's copy

                srcimage,dstimage,mesg=None,None,None
                if src and dst:
                    srcimage = Database().get_record(None, 'osimage', f"WHERE name='{src}'")
                    dstimage = Database().get_record(None, 'osimage', f"WHERE name='{dst}'")
                    if srcimage and dstimage:
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
                                    #command=f"rsync -a \"{srcimage[0]['path']}\"/* \"{dstimage[0]['path']}\"/" 
                                    command=f"tar -C \"{srcimage[0]['path']}\"/ --one-file-system --exclude=/proc/* --exclude=/sys/* --xattrs --acls --selinux -cf - . | (cd \"{dstimage[0]['path']}\"/ && tar -xf -)" 
                                    mesg,exit_code = Helper().runcommand(command,True,3600)
                                    if exit_code == 0:
                                        result=True

                    sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                    if result is True:
                        self.logger.info(f'OS image copied successfully.')
                        Status().add_message(request_id,"luna",f"finished copying osimage")

                    else:
                        self.logger.info(f'Copy osimage {src}->{dst} error: {mesg}.')
                        Status().add_message(request_id,"luna",f"error copying osimage: {mesg}")

                else:
                    self.logger.info(f'Copy osimage src and/or dst not provided.')
                    Status().add_message(request_id,"luna",f"error copying osimage as 'src' and/or 'dst' not provided.")

                if not noeof:
                    Status().add_message(request_id,"luna",f"EOF")
                return result
            else:
                self.logger.info(f"{details['task']} is not for us.")

        except Exception as exp:
            self.logger.error(f"copy_osimage has problems: {exp}")
            try:
                Status().add_message(request_id,"luna",f"Packing failed: {exp}")
                Status().add_message(request_id,"luna",f"EOF")
            except Exception as nexp:
                self.logger.error(f"copy_osimage has problems during exception handling: {nexp}")
            return False 
 
    # ---------------------------------------------------------------------------

    def torrent_osimage(self,taskid,request_id):

        self.logger.info(f"torrent_osimage called")
        try:

            result,mesg=False,None
            details=Queue().get_task_details(taskid)
            request_id=details['request_id']
            action,osimage,noeof,*_=(details['task'].split(':')+[None]+[None])

            if action == "torrent_osimage":
                Status().add_message(request_id,"luna",f"creating torrent for osimage {osimage}")
   
                # --- let's torrent

                image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
                if not image:
                    result=False
                    mesg=f"Image {osimage} does not exist?"

                else:
                    image_id=image[0]['id']
                    if (not 'tarball' in image[0]) and (not image[0]['tarball']):
                        result=False
                        mesg=f"Tarball for {osimage} does not exist?"

                    else:
                        ret,mesg=Torrent().create_torrent(image[0]['tarball'])
                        if ret:
                            result=True
                            torrentfile=mesg # create_torrent returns the torrent file on success.
                            row = [{"column": "torrent", "value": f"{torrentfile}"}]
                            where = [{"column": "id", "value": f"{image_id}"}]
                            status = Database().update('osimage', row, where)
                            mesg=f"Success for {image[0]['tarball']}"
 
                sleep(1) # needed to prevent immediate concurrent access to the database. Pooling,WAL,WIF,WAF,etc won't fix this. Only sleep
                if result is True:
                    self.logger.info(f'OS image {osimage} torrent successfully.')
                    Status().add_message(request_id,"luna",f"finished creating torrent for osimage {osimage}")
                else:
                    self.logger.info(f'OS image {osimage} torrent error: {mesg}.')
                    Status().add_message(request_id,"luna",f"error creating torrent for osimage {osimage}: {mesg}")

                if not noeof:
                    Status().add_message(request_id,"luna",f"EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
            return result

        except Exception as exp:
            self.logger.error(f"torrent_osimage has problems: {exp}")
            try:
                Status().add_message(request_id,"luna",f"Torrent failed: {exp}")
                Status().add_message(request_id,"luna",f"EOF")
            except Exception as nexp:
                self.logger.error(f"torrent_osimage has problems during exception handling: {nexp}")
            return False


    # ------------------------------------------------------------------- 
    # The mother of all.

    def osimage_mother(self,request_id):

        self.logger.info(f"osimage_mother called")
        try:

#            # Below section is already done in config/pack GET call but kept here in case we want to move it back
#            queue_id,response = Queue().add_task_to_queue(f'pack_n_tar_osimage:{osimage}','osimage',request_id)
#            if not queue_id:
#                self.logger.info(f"pack_n_tar_mother cannot get queue_id")
#                Status().add_message(request_id,"luna",f"error queuing my task")
#                return
#            self.logger.info(f"pack_n_tar_mother added task to queue: {queue_id}")
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

            while next_id := Queue().next_task_in_queue('osimage','queued'):
                details=Queue().get_task_details(next_id)
                request_id=details['request_id']
                action,first,second,*_=(details['task'].split(':')+[None]+[None])
                self.logger.info(f"osimage_mother sees job {action} in queue as next: {next_id}")

                if action == "clone_osimage":
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if first and second:
                        queue_id,queue_response = Queue().add_task_to_queue(f"copy_osimage:{first}:{second}:noeof",'osimage',request_id)
                        if queue_id:
                            queue_id,queue_response = Queue().add_task_to_queue(f"pack_n_tar_osimage:{second}",'osimage',request_id)
                            if queue_id:
                                queue_id,queue_response = Queue().add_task_to_queue(f"close_task:{next_id}",'osimage',request_id)

                elif action == "pack_n_tar_osimage":
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if first:
                        queue_id,queue_response = Queue().add_task_to_queue(f"pack_osimage:{first}:noeof",'osimage',request_id)
                        if queue_id:
                            queue_id,queue_response = Queue().add_task_to_queue(f"tar_osimage:{first}:noeof",'osimage',request_id)
                            if queue_id:
                                queue_id,queue_response = Queue().add_task_to_queue(f"torrent_osimage:{first}",'osimage',request_id)
                                if queue_id:
                                    queue_id,queue_response = Queue().add_task_to_queue(f"close_task:{next_id}",'osimage',request_id)

                # below are internal calls.

                elif action == "copy_osimage":
                    if first and second:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.copy_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna",f"EOF")

                elif action == "pack_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.pack_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna",f"EOF")

                elif action == "tar_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.tar_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna",f"EOF")

                elif action == "torrent_osimage":
                    if first:
                        Queue().update_task_status_in_queue(next_id,'in progress')
                        ret=self.torrent_osimage(next_id,request_id)
                        Queue().remove_task_from_queue(next_id)
                        if not ret:
                            Queue().remove_task_from_queue_by_request_id(request_id)
                            Status().add_message(request_id,"luna",f"EOF")

                elif action == "close_task" and first:
                    Queue().remove_task_from_queue(first)
                    Queue().remove_task_from_queue(next_id)

                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)

        except Exception as exp:
            self.logger.error(f"osimage_mother has problems: {exp}")
            try:
                Status().add_message(request_id,"luna",f"Cloning failed: {exp}")
                Status().add_message(request_id,"luna",f"EOF")
            except Exception as nexp:
                self.logger.error(f"osimage_mother has problems during exception handling: {nexp}")
            

