
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
        self.packing = queue.Queue()
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

    def pack(self, osimage):

        osimage = self._get_object(name, mongo_db, create, id)

        if bool(kernopts) and type(kernopts) is not str:
            err_msg = "Kernel options should be 'str' type"
            self.log.error(err_msg)
            raise RuntimeError, err_msg

        if create:
            cluster = Cluster(mongo_db=self._mongo_db)
            path = os.path.abspath(path)

            duplicate = self._mongo_collection.find_one({'path': path})
            if duplicate:
                err_msg = ("Path belongs to osimage '{}'"
                           .format(duplicate['name']))
                self.log.error(err_msg)
                raise RuntimeError, err_msg

            if not os.path.isdir(path):
                err_msg = "'{}' is not a valid directory".format(path)
                self.log.error(err_msg)
                raise RuntimeError, err_msg

            kernels = self.get_package_ver(path, 'kernel')
            if not kernels:
                err_msg = "No kernels installed in '{}'".format(path)
                self.log.error(err_msg)
                raise RuntimeError, err_msg
            elif not kernver:
                kernver = kernels[0]
            elif kernver not in kernels:
                err_msg = "Available kernels are '{}'".format(kernels)
                self.log.error(err_msg)
                raise RuntimeError, err_msg

            grab_list_path = cluster.get('path') + '/templates/' + grab_list
            if not os.path.isfile(grab_list_path):
                err_msg = "'{}' is not a file.".format(grab_list_path)
                self.log.error(err_msg)
                raise RuntimeError, err_msg

            with open(grab_list_path) as lst:
                grab_list_content = lst.read()

            # Store the new osimage in the datastore

            osimage = {'name': name, 'path': path,
                       'kernver': kernver, 'kernopts': kernopts,
                       'kernfile': '', 'initrdfile': '',
                       'dracutmodules': 'luna,-i18n,-plymouth',
                       'kernmodules': 'ipmi_devintf,ipmi_si,ipmi_msghandler',
                       'grab_exclude_list': grab_list_content,
                       'grab_filesystems': '/,/boot', 'comment': comment}

            self.log.debug("Saving osimage '{}' to the datastore"
                           .format(osimage))

            self.store(osimage)

            # Link this osimage to its dependencies and the current cluster

            self.link(cluster)

        self.log = logging.getLogger(__name__ + '.' + self._name)

    def pack_boot(self):
        def mount(source, target, fs):
            subprocess.Popen(['/usr/bin/mount', '-t', fs, source, target])

        def umount(source):
            subprocess.Popen(['/usr/bin/umount', source])

        def prepare_mounts(path):
            mount('devtmpfs', path + '/dev', 'devtmpfs')
            mount('proc', path + '/proc', 'proc')
            mount('sysfs', path + '/sys', 'sysfs')

        def cleanup_mounts(path):
            umount(path + '/dev')
            umount(path + '/proc')
            umount(path + '/sys')

        tmp_path = '/tmp'  # in chroot env
        image_path = self.get('path')
        kernver = self.get('kernver')
        kernfile = self.name + '-vmlinuz-' + kernver
        initrdfile = self.name + '-initramfs-' + kernver

        cluster = Cluster(mongo_db=self._mongo_db)
        path = cluster.get('path')
        user = cluster.get('user')

        path_to_store = path + "/boot"
        user_id = pwd.getpwnam(user).pw_uid
        grp_id = pwd.getpwnam(user).pw_gid

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
            os.chown(path_to_store, user_id, grp_id)

        modules_add = []
        modules_remove = []
        drivers_add = []
        drivers_remove = []

        dracutmodules = self.get('dracutmodules')
        if dracutmodules:
            for i in dracutmodules.split(','):
                if i[0] != '-':
                    modules_add.extend(['--add', i])
                else:
                    modules_remove.extend(['--omit', i[1:]])

        kernmodules = self.get('kernmodules')
        if kernmodules:
            for i in kernmodules.split(','):
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
                err_msg = ("No luna dracut module in osimage '{}'"
                           .format(self.name))
                self.log.error(err_msg)
                raise RuntimeError, err_msg

            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernver] +
                          modules_add + modules_remove + drivers_add +
                          drivers_remove + [tmp_path + '/' + initrdfile])
#            print dracut_cmd

            create = subprocess.Popen(dracut_cmd, stdout=subprocess.PIPE)
            while create.poll() is None:
                line = create.stdout.readline()

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.log.error(exc_value)
            self.log.debug(traceback.format_exc())
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
            self.log.error("Error while building initrd.")
            return False

        initrd_path = image_path + tmp_path + '/' + initrdfile
        kernel_path = image_path + '/boot/vmlinuz-' + kernver

        if not os.path.isfile(kernel_path):
            self.log.error("Unable to find kernel in {}".format(kernel_path))
            return False

        if not os.path.isfile(initrd_path):
            self.log.error("Unable to find initrd in {}".format(initrd_path))
            return False

        # copy initrd file to inherit perms from parent folder
        shutil.copy(initrd_path, path_to_store + '/' + initrdfile)
        os.remove(initrd_path)
        shutil.copy(kernel_path, path_to_store + '/' + kernfile)
        os.chown(path_to_store + '/' + initrdfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + initrdfile, 0644)
        os.chown(path_to_store + '/' + kernfile, user_id, grp_id)
        os.chmod(path_to_store + '/' + kernfile, 0644)

        self.set('kernfile', kernfile)
        self.set('initrdfile', initrdfile)

        return True

