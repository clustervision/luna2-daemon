
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
from time import sleep
from datetime import datetime
import sys
import uuid
import shutil


class OsImage(object):
    """Class for operating with osimages records"""

    def __init__(self):
        """
                 , name=None, mongo_db=None, create=False, id=None,
                 path='', kernver='', kernopts='', comment='',
                 grab_list='grab_default_centos.lst'):
        """
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

        #user = cluster.get('user')
        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
            os.chown(path_to_store, user_id, grp_id)
            os.chmod(path_to_store, 0o755)

        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if ('path' not in image[0]) or (image[0]['path'] is None):
            return False,"Image path not defined"

        image_path = image[0]['path']
        if image_path[0] != '/': # means that we don't have an absolute path. good, let's prepend what's in luna.ini
            if 'IMAGE_DIRECTORY' in CONSTANT['FILES']:
                image_path = f"{CONSTANT['FILES']['IMAGE_DIRECTORY']}/{image[0]['path']}"
            else:
                return False,f"image path {image_path} is not an absolute path while IMAGE_DIRECTORY setting in FILES is not defined"

        if not os.path.exists(image_path):
            return False,"Image path {image_path} does not exist"

        uid = str(uuid.uuid4())
        tarfile = uid + ".tar.bz2"

        if not os.path.exists('/usr/bin/tar'):
            return False,"/usr/bin/tar does not exist. please install tar"
        if not os.path.exists('/usr/bin/lbzip2'):
            return False,"/usr/bin/lbzip2 does not exist. please install lbzip2"

#        os.chdir(f"{image_path}") # needed for tar to not have leading dirs in path

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

    def pack_image(self,osimage):

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
        

        print(f"{image[0]}")

        if 'dracutmodules' in image[0]:
            for i in image[0]['dracutmodules'].split(','):
                s=i.replace(" ", "")
                print(f" module: [{s[0]}] [{s}]")
                if s[0] != '-':
                    modules_add.extend(['--add', s])
                else:
                    modules_remove.extend(['--omit', s[1:]])

        if 'kernelmodules' in image[0]:
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
                self.logger.info = (f"No luna dracut module in osimage '{osimage}'")
                return False,"No luna dracut module in osimage"

            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernver] +
                          modules_add + modules_remove + drivers_add +
                          drivers_remove + [tmp_path + '/' + initrdfile])
            print(f"{dracut_cmd}")

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


    def pack_n_tar_mother(self,osimage,request_id):

        self.logger.info(f"pack_n_tar_mother called")
#        Below section is already done in config/pack GET call but kept here in case we want to move it back
#        try:
#            queue_id = Helper().add_task_to_queue(f'pack_n_tar_osimage:{osimage}','osimage',request_id)
#        except:
#            exc_type, exc_value, exc_traceback = sys.exc_info()
#            self.logger.info(f"--------> {exc_type} {exc_value} {exc_traceback}")
#        if not queue_id:
#            self.logger.info(f"pack_n_tar_mother cannot get queue_id")
#            Helper().insert_mesg_in_status(request_id,"luna",f"error queuing my task")
#            return
#        self.logger.info(f"pack_n_tar_mother added task to queue: {queue_id}")
#        Helper().insert_mesg_in_status(request_id,"luna",f"queued pack osimage {osimage} with queue_id {queue_id}")
#
#        next_id = Helper().next_task_in_queue('osimage')
#        if queue_id != next_id:
#            # little tricky. we assume that another mother proces was spawned that took care of the runs... 
#            # we need a check based on last hear queue entry, then we continue. pending in next_task_in_queue.
#            return

        while Helper().tasks_in_queue('osimage'):
            next_id = Helper().next_task_in_queue('osimage')
            self.logger.info(f"pack_n_tar_mother sees job in queue as next: {next_id}")
            details=Helper().get_task_details(next_id)
            request_id=details['request_id']
            action,osimage=details['task'].split(':')

            if action == "pack_n_tar_osimage":

                Helper().update_task_status_in_queue(next_id,'in progress')
                Helper().insert_mesg_in_status(request_id,"luna",f"packing osimage {osimage}")

            # --- let's pack and rack

                ret,mesg=self.pack_image(osimage)
                if ret is True:
                    self.logger.info(f'OS image {osimage} packed successfully.')
                    Helper().insert_mesg_in_status(request_id,"luna",f"finished packing osimage {osimage}")
                    Helper().insert_mesg_in_status(request_id,"luna",f"tarring osimage {osimage}")

                    rett,mesgt=self.create_tarball(osimage)
                    if rett is True:
                        self.logger.info(f'OS image {osimage} tarred successfully.')
                        Helper().insert_mesg_in_status(request_id,"luna",f"finished tarring osimage {osimage}")
                    else:
                        self.logger.info(f'OS image {osimage} tar error: {mesgt}.')
                        Helper().insert_mesg_in_status(request_id,"luna",f"error tarring osimage {osimage}: {mesgt}")
                else:
                    self.logger.info(f'OS image {osimage} pack error: {mesg}.')
                    Helper().insert_mesg_in_status(request_id,"luna",f"error packing osimage {osimage}: {mesg}")

                Helper().remove_task_from_queue(next_id)
                Helper().insert_mesg_in_status(request_id,"luna",f"EOF")
            else:
                self.logger.info(f"{details['task']} is not for us.")
                sleep(10)





