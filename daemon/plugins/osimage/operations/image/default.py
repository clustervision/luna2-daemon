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
Plugin Class ::  Default OS Image Plugin.
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
from time import time
import sys
from utils.log import Log
#from utils.helper import Helper


class Plugin():
    """
    Class for operating with osimages records.
    """

    def __init__(self):
        """
        two defined methods are mandatory:
        - pack   returns kernel_file_name,ramdisk_file_name upon success
        - build  returns image_file_name upon success
        one variable:
        - systemroot   this is where the installer will unpack files (read: ramdisk image) to
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

        # osimage = just the name of the image
        # image_path = is the location where the image resides
        # files_path = is the location where the imagefile will be copied.
        # packed_image_file = the name of the actual imagefile
        # kernel_modules = list of drivers to be included/excluded
        # ramdisk_modules = list of ramdisk modules to be included/excluded

    # ---------------------------------------------------------------------------

    systemroot = "/sysroot"

    # ---------------------------------------------------------------------------

    def verify_space(self, image_path, dest_path):
        estimated_size, space_left = 0, 0
        dest_paths=[]
        try:
            if isinstance(dest_path, str):
                dest_paths=[dest_path]
            elif isinstance(dest_path, list):
                dest_paths=dest_path
            if len(dest_paths) == 0:
                return True, "destination paths not provided"
            if isinstance(image_path, int):
                estimated_size = image_path
            else:
                output = subprocess.run(['du', '-s', image_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if output.returncode == 0:
                    du = output.stdout.decode('ascii').split()
                    estimated_size = int(int(du[0])*0.45)
            if estimated_size > 0:
                for check_path in dest_paths:
                    output = subprocess.run(['df', check_path, '--output=avail'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if output.returncode == 0:
                        df=output.stdout.decode('ascii').split("\n")
                        space_left = int(df[1])
                        if estimated_size > space_left:
                            return False, f"No go as we might not have disk space: {estimated_size} > {space_left} for {check_path}"
                        self.logger.debug(f"Go as we have disk space: {estimated_size} < {space_left} for {check_path}")
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"plugin: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
        return True, "ok"


    def build(self, osimage=None, image_path=None, files_path=None, tmp_directory=None):
        # osimage = just the name of the image
        # image_path = is the location where the image resides
        # files_path = is the location where the imagefile will be copied.
        # --> a successful build returns True + the name of the imagefile
        # user = cluster.get('user')  # left in for future use if we want to run the daemon as non-root
        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        if not os.path.exists(files_path):
            os.makedirs(files_path)
            os.chown(files_path, user_id, grp_id)
            os.chmod(files_path, 0o755)

        if not os.path.exists(image_path):
            return False,f"Image path {image_path} does not exist"

        # uid = str(uuid.uuid4())
        epoch_time = int(time())
        packed_image_file = f"{osimage}-{epoch_time}.tar.bz2"

        if not os.path.exists('/usr/bin/tar'):
            return False,"/usr/bin/tar does not exist. please install tar"
        if not os.path.exists('/usr/bin/lbzip2'):
            return False,"/usr/bin/lbzip2 does not exist. please install lbzip2"

        tmp_dir=tmp_directory or '/tmp'
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        if not os.path.exists(tmp_dir):
            return False, f"could not create or use temp directory f{tmp_dir}"

        space_check = self.verify_space(image_path,[tmp_dir, files_path])
        if not space_check[0]:
            self.logger.error(f"Tarring {osimage} stopped: {space_check[1]}")
            return False,f"Tarring {osimage} stopped: {space_check[1]}"

        try:
            self.logger.debug(f"/usr/bin/tar -C {image_path} --one-file-system --xattrs --selinux --acls --checkpoint=100000 --use-compress-program=/usr/bin/lbzip2 -c -f {tmp_dir}/{packed_image_file} .")

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
                        '--exclude=/tmp/*',
                        '--checkpoint=100000',
                        '--use-compress-program=/usr/bin/lbzip2',
                        '-c', '-f', tmp_dir + '/' + packed_image_file, '.'
                    ],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True)
            except subprocess.CalledProcessError as exc:
                self.logger.info(f"Tarring failed with exit code {exc.returncode} {exc.output}:")
                if os.path.isfile(tmp_dir + '/' + packed_image_file):
                    os.remove(tmp_dir + '/' + packed_image_file)
                output=f"{exc.output}"
                outputs=output.split("\n")
                joined='. '.join(outputs[-5:])
                return False,f"Tarring {osimage} failed with exit code {exc.returncode}: {joined}"
            else:
                self.logger.info(f"Tarring {osimage} successful.")

        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"plugin: {exp}, {exc_type}, in {exc_tb.tb_lineno}")

            if os.path.isfile(tmp_dir + '/' + packed_image_file):
                os.remove(tmp_dir + '/' + packed_image_file)

            sys.stdout.write('\r')

            return False, "Tar went bonkers"

        # copy image, so permissions and selinux contexts
        # will be inherited from parent folder

        try:
            shutil.move(tmp_dir + '/' + packed_image_file, files_path)
            os.chown(files_path + '/' + packed_image_file, user_id, grp_id)
            os.chmod(files_path + '/' + packed_image_file, 0o644)
        except Exception as error:
            return False, f"Moving {osimage} imagefile failed with {error}"

        return True, "Success", packed_image_file


    # -------------------------------------------------------------------

    def pack(self, osimage=None, image_path=None, files_path=None, kernel_version=None, kernel_modules=[]):
        # files_path = location where ramdisk+kernel are being stored
        # kernel_file = name of the kernel/vmlinuz file
        # ramdisk_file = name  of the ramdisk/initrd file
        # kernel_modules = list of drivers to be included/excluded

        def mount(source, target, fs):
            try:
                subprocess.Popen(['/usr/bin/mount', '-t', fs, source, target])
            except Exception as error:
                self.logger(f"Mount {target} failed with {error}")

        def umount(source):
            try:
                subprocess.Popen(['/usr/bin/umount', source])
            except Exception as error:
                self.logger(f"Umount {source} failed with {error}")

        def prepare_mounts(path):
            mount('devtmpfs', f"{path}/dev", 'devtmpfs')
            mount('proc', f"{path}/proc", 'proc')
            mount('sysfs', f"{path}/sys", 'sysfs')

        def cleanup_mounts(path):
            umount(f"{path}/dev")
            umount(f"{path}/proc")
            umount(f"{path}/sys")

        if not os.path.exists(image_path):
            return False,f"Image path {image_path} does not exist"

        space_check = self.verify_space(120000,[image_path, files_path])
        if not space_check[0]:
            self.logger.error(f"Packing {osimage} stopped: {space_check[1]}")
            return False,f"Packing {osimage} stopped: {space_check[1]}"

        epoch_time = int(time())
        kernel_file = f"{osimage}-{epoch_time}-vmlinuz-{kernel_version}"
        ramdisk_file = f"{osimage}-{epoch_time}-initramfs-{kernel_version}"

        user_id = pwd.getpwnam('root').pw_uid
        grp_id = pwd.getpwnam('root').pw_gid

        if not os.path.exists(files_path):
            os.makedirs(files_path)
            #os.chown(files_path, user_id, grp_id)

        modules_add = []
        modules_remove = []
        drivers_add = []
        drivers_remove = []
        #grab_filesystems = ['/','/boot']

        # hard coded ramdisk modules
        ramdisk_modules = ['luna','-18n','-plymouth']
        if ramdisk_modules:
            for i in ramdisk_modules:
                s = i.replace(" ", "")
                if s[0] != '-':
                    modules_add.extend(['--add', s])
                else:
                    modules_remove.extend(['--omit', s[1:]])

        if kernel_modules:
            for i in kernel_modules:
                s = i.replace(" ", "")
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
                                               kernel_version, '--list-modules'],
                                              stdout=subprocess.PIPE)
            luna_exists = False

            while dracut_modules.poll() is None:
                line = dracut_modules.stdout.readline()
                line_clean = line.strip()
                line_clean = line_clean.decode('ASCII')
                if line_clean == 'luna':
                    luna_exists = True
                    break

            if not luna_exists:
                self.logger.info(f"No luna dracut module in osimage '{osimage}'. I add it as a safe measure.")
                # return False,"No luna dracut module in osimage"
                modules_add.extend(['--add', 'luna']) # this part is debatable. for now i add this. pending

            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernel_version] +
                          modules_add + modules_remove + drivers_add +
                          drivers_remove + ['/tmp/' + ramdisk_file])

            create = subprocess.Popen(dracut_cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            while create.poll() is None:
                line = create.stdout.readline()

        except:
            exc_type, exc_value, exc_traceback= sys.exc_info()
            self.logger.info(exc_value)
            self.logger.debug(exc_traceback.format_exc())
            dracut_succeed = False

        message = "Problem building initrd"
        if create and create.returncode:
            dracut_succeed = False
            all_messages = create.stderr.read().decode().split('\n')
            message = '.'.join(all_messages[:3])

        if not create:
            dracut_succeed = False
            message = "Could not open subprocess to run dracut"

        os.fchdir(real_root)
        os.chroot(".")
        os.close(real_root)
        os.close(chroot_path)
        cleanup_mounts(image_path)

        if not dracut_succeed:
            self.logger.info(f"Error while building initrd: {message}")
            return False,message

        # the defaults for redhat derivatives
        initrd_path = image_path + '/tmp/' + ramdisk_file
        kernel_path = image_path + '/boot/vmlinuz-' + kernel_version

        if not os.path.isfile(kernel_path):
            self.logger.info(f"Unable to find kernel in {kernel_path}")
            return False, f"Unable to find kernel in {kernel_path}"

        if not os.path.isfile(initrd_path):
            self.logger.info(f"Unable to find initrd in {initrd_path}")
            return False, f"Unable to find initrd in {initrd_path}"

        # move initrd file to inherit perms from parent folder
        shutil.move(initrd_path, files_path + '/' + ramdisk_file)
        shutil.copy(kernel_path, files_path + '/' + kernel_file)
        os.chown(files_path + '/' + ramdisk_file, user_id, grp_id)
        os.chmod(files_path + '/' + ramdisk_file, 0o644)
        os.chown(files_path + '/' + kernel_file, user_id, grp_id)
        os.chmod(files_path + '/' + kernel_file, 0o644)

        return True, "Success", kernel_file, ramdisk_file

