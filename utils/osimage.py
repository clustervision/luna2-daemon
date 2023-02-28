
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
        #self.packing = queue.Queue()
        #self.log.debug("function args {}".format(self._debug_function()))

        # Define the schema used to represent osimage objects

#        self._collection_name = 'osimage'
#        self._keylist = {'path': type(''), 'kernver': type(''),
#                         'kernopts': type(''), 'kernmodules': type(''),
#                         'dracutmodules': type(''), 'tarball': type(''),
#                         'torrent': type(''), 'kernfile': type(''),
#                         'initrdfile': type(''), 'grab_exclude_list': type(''),
#                         'grab_filesystems': type(''), 'comment': type('')}

        # Check if this osimage is already present in the datastore
        # Read it if that is the case

    def create_tarball(self,osimage):
        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        #TARBALL = /trinity/local/luna/files
        if 'FILES' not in CONSTANT:
            return False,"FILES config setting not defined"
        if 'TARBALL' not in CONSTANT['FILES']:
            return False,"TARBALL config setting not defined in FILES"
        path = CONSTANT['FILES']['TARBALL']
        #user = cluster.get('user')
        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        #path_to_store = path + "/torrents"
        #if not os.path.exists(path_to_store):
        #    os.makedirs(path_to_store)
        #    os.chown(path_to_store, user_id, grp_id)
        #    os.chmod(path_to_store, 0644)

        if 'path' not in image[0]:
            return False,"Image path not defined"
        if image[0]['path'] is None:
            return False,"Image path not defined"
        image_path = image[0]['path']

        real_root = os.open("/", os.O_RDONLY)
        os.chroot(image_path)

        os.chdir('/')
        os.system('mount -t proc none /proc')

        uid = str(uuid.uuid4())
        tarfile = uid + ".tar.bz2"

        try:
            # dirty, but 4 times faster
            tar_out = subprocess.Popen(
                [
                    '/usr/bin/tar',
                    '-C', '/',
                    '--one-file-system',
                    '--xattrs',
                    '--selinux',
                    '--acls',
                    '--checkpoint=100',
                    '--exclude=./tmp/' + tarfile,
                    '--use-compress-program=/usr/bin/lbzip2',
                    '-c', '-f', '/tmp/' + tarfile, '.'
                ],
                stderr=subprocess.PIPE
            )

            stat_symb = ['\\', '|', '/', '-']
            i = 0
            while True:
                line = tar_out.stderr.readline()
                if line == '':
                    break
                i = i + 1
                sys.stdout.write(stat_symb[i % len(stat_symb)])
                sys.stdout.write('\r')

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

            os.fchdir(real_root)
            os.chroot(".")
            os.close(real_root)

            return False

        os.system('umount /proc || umount -lf /proc')

        os.fchdir(real_root)
        os.chroot(".")
        os.close(real_root)

        # copy image, so permissions and selinux contexts
        # will be inherited from parent folder
        shutil.copy(image_path + '/tmp/' + tarfile, path_to_store)
        os.remove(image_path + '/tmp/' + tarfile)
        os.chown(path_to_store + '/' + tarfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + tarfile, stat.S_IREAD)
        os.chmod(path_to_store + '/' + tarfile, stat.S_IWRITE)
        os.chmod(path_to_store + '/' + tarfile, stat.S_IRGRP)
        os.chmod(path_to_store + '/' + tarfile, stat.S_IROTH )
        #self.set('tarball', str(uid))

        return True


    """
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
            subprocess.Popen(['/usr/bin/mount', '-t', fs, source, target])

        def umount(source):
            subprocess.Popen(['/usr/bin/umount', source])

        def prepare_mounts(path):
            mount('devtmpfs', f"{path}/dev", 'devtmpfs')
            mount('proc', f"{path}/proc", 'proc')
            mount('sysfs', f"{path}/sys", 'sysfs')

        def cleanup_mounts(path):
            umount(f"{path}/dev")
            umount(f"{path}/proc")
            umount(f"{path}/sys")

        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")

        if 'path' not in image[0]:
            return False,"Image path not defined"
        if image[0]['path'] is None:
            return False,"Image path not defined"
        if 'kernelversion' not in image[0]:
            return False,"Kernel version not defined"
        if image[0]['kernelversion'] is None:
            return False,"Kernel version not defined"

        tmp_path = '/tmp'  # in chroot env
        image_path = str(image[0]['path'])
        kernver = str(image[0]['kernelversion'])
        kernfile = f"{osimage}-vmlinuz-{kernver}"
        initrdfile = f"{osimage}-initramfs-{kernver}"

        path_to_store = f"{image[0]['path']}/boot"
        #user_id = pwd.getpwnam(user).pw_uid
        #grp_id = pwd.getpwnam(user).pw_gid

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
            #os.chown(path_to_store, user_id, grp_id)

        modules_add = ['ipmi_devintf','ipmi_si','ipmi_msghandler']
        modules_remove = []
        drivers_add = ['luna','-plymouth']
        drivers_remove = ['-i18n']
        grab_filesystems = ['/','/boot']

        """
            osimage = {'name': name, 'path': path,
                       'kernver': kernver, 'kernopts': kernopts,
                       'kernfile': '', 'initrdfile': '',
                       'dracutmodules': 'luna,-i18n,-plymouth',
                       'kernmodules': 'ipmi_devintf,ipmi_si,ipmi_msghandler',
                       'grab_exclude_list': grab_list_content,
                       'grab_filesystems': '/,/boot', 'comment': comment}
        """

        #dracutmodules = self.get('dracutmodules')
        #if dracutmodules:
        if 'dracutmodules' in image[0]:
            for i in image[0]['dracutmodules'].split(','):
                if i[0] != '-':
                    modules_add.extend(['--add', i])
                else:
                    modules_remove.extend(['--omit', i[1:]])

        #kernmodules = self.get('kernmodules')
        #if kernmodules:
        if 'kernelmodules' in image[0]:
            for i in image[0]['kernelmodules'].split(','):
                if i[0] != '-':
                    drivers_add.extend(['--add-drivers', i])
                else:
                    drivers_remove.extend(['--omit-drivers', i[1:]])

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
                if line.strip() == 'luna':
                    luna_exists = True
                    break

            if not luna_exists:
                self.logger.info = (f"No luna dracut module in osimage 'osimage'")
                return False,"No luna dracut module in osimage"
                #raise RuntimeError, err_msg

            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernver] +
                          modules_add + modules_remove + drivers_add +
                          drivers_remove + [tmp_path + '/' + initrdfile])
#            print dracut_cmd

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
            return False

        initrd_path = image_path + tmp_path + '/' + initrdfile
        kernel_path = image_path + '/boot/vmlinuz-' + kernver

        if not os.path.isfile(kernel_path):
            self.logger.info("Unable to find kernel in {}".format(kernel_path))
            return False

        if not os.path.isfile(initrd_path):
            self.logger.info("Unable to find initrd in {}".format(initrd_path))
            return False

        # copy initrd file to inherit perms from parent folder
        shutil.copy(initrd_path, path_to_store + '/' + initrdfile)
        os.remove(initrd_path)
        shutil.copy(kernel_path, path_to_store + '/' + kernfile)
        os.chown(path_to_store + '/' + initrdfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + initrdfile, 0o644)
        os.chown(path_to_store + '/' + kernfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + kernfile, 0o644)

        #self.set('kernfile', kernfile)
        #self.set('initrdfile', initrdfile)

        return True

