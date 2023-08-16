#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
from time import sleep, time
import sys
import uuid
# from datetime import datetime
# import json
from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    Class for operating with osimages records.
    """

    def __init__(self):
        """
        three defined methods are mandatory:
        - pack   returns kernel_file_name,ramdisk_file_name upon success
        - build  returns image_file_name upon success
        - cleanup
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

    def cleanup(self, osimage=None, files_path=None, current_packed_image_file=None, current_kernel_file=None, current_ramdisk_file=None):
        # files_path = is the location where the imagefile will be copied.
        # current_packed_image_file is the currently used packed image
        # same goes for kernel + ramdisk file
        message = ''
        if current_packed_image_file:
            command = f"cd {files_path} && ls {osimage}-*.tar.bz2 | grep -vw \"{current_packed_image_file}\" | xargs rm -f"
            self.logger.info(f"I will run: {command}")
            message, exit_code = Helper().runcommand(command, True, 300)
            if exit_code == 0:
                command = f"cd {files_path} && ls {osimage}-*-vmlinuz* | grep -vw \"{current_kernel_file}\" | xargs rm -f"
                self.logger.info(f"I will run: {command}")
                message, exit_code = Helper().runcommand(command, True, 300)
                if exit_code == 0:
                    command = f"cd {files_path} && ls {osimage}-*-initramfs* | grep -vw \"{current_ramdisk_file}\" | xargs rm -f"
                    self.logger.info(f"I will run: {command}")
                    message, exit_code = Helper().runcommand(command, True, 300)
            if exit_code == 0:
                return True, message
        return False, message

    # ---------------------------------------------------------------------------
            
    def build(self, osimage=None, image_path=None, files_path=None):
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

        try:
            self.logger.debug(f"/usr/bin/tar -C {image_path} --one-file-system --xattrs --selinux --acls --checkpoint=100000 --use-compress-program=/usr/bin/lbzip2 -c -f /tmp/{packed_image_file} .")

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
                        '-c', '-f', '/tmp/' + packed_image_file, '.'
                    ],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True)
            except subprocess.CalledProcessError as exc:
                self.logger.info(f"Tarring failed with exit code {exc.returncode} {exc.output}:")
                if os.path.isfile('/tmp/' + packed_image_file):
                    os.remove('/tmp/' + packed_image_file)
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

            if os.path.isfile('/tmp/' + packed_image_file):
                os.remove('/tmp/' + packed_image_file)

            sys.stdout.write('\r')

            return False, "Tar went bonkers"

        # copy image, so permissions and selinux contexts
        # will be inherited from parent folder

        try:
            shutil.copy(f"/tmp/{packed_image_file}", files_path)
            os.remove(f"/tmp/{packed_image_file}")
            os.chown(files_path + '/' + packed_image_file, user_id, grp_id)
            os.chmod(files_path + '/' + packed_image_file, 0o644)
        except Exception as error:
            return False, f"Moving {osimage} imagefile failed with {error}"

        return True, "Success", packed_image_file


    # -------------------------------------------------------------------

    def pack(self, osimage=None, image_path=None, files_path=None, kernel_version=None, kernel_modules=[], ramdisk_modules=[]):
        # files_path = location where ramdisk+kernel are being stored
        # kernel_file = name of the kernel/vmlinuz file
        # ramdisk_file = name  of the ramdisk/initrd file
        # kernel_modules = list of drivers to be included/excluded
        # ramdisk_modules = list of ramdisk modules to be included/excluded

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

        if not os.path.exists(image_path):
            return False,f"Image path {image_path} does not exist"

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
        grab_filesystems = ['/','/boot']



        # add modules goes in /image/etc/initramfs-tools/modules
        
#        if ramdisk_modules:
#            for i in ramdisk_modules:
#                s = i.replace(" ", "")
#                if s[0] != '-':
#                    modules_add.extend(['--add', s])
#                else:
#                    modules_remove.extend(['--omit', s[1:]])
#
#        if kernel_modules:
#            for i in kernel_modules:
#                s = i.replace(" ", "")
#                if s[0] != '-':
#                    drivers_add.extend(['--add-drivers', s])
#                else:
#                    drivers_remove.extend(['--omit-drivers', s[1:]])

        prepare_mounts(image_path)
        real_root = os.open("/", os.O_RDONLY)
        os.chroot(image_path)
        chroot_path = os.open("/", os.O_DIRECTORY)
        os.fchdir(chroot_path)

        initramfs_succeed = True
        create = None

        try:
#            dracut_modules = subprocess.Popen(['/usr/bin/dracut', '--kver',
#                                               kernel_version, '--list-modules'],
#                                              stdout=subprocess.PIPE)
#            luna_exists = False

            # add luna module manually to above mentioned file

#            while dracut_modules.poll() is None:
#                line = dracut_modules.stdout.readline()
#                line_clean = line.strip()
#                line_clean = line_clean.decode('ASCII')
#                if line_clean == 'luna':
#                    luna_exists = True
#                    break

#            if not luna_exists:
#                self.logger.info(f"No luna dracut module in osimage '{osimage}'. I add it as a safe measure.")
#                # return False,"No luna dracut module in osimage"
#                modules_add.extend(['--add', 'luna']) # this part is debatable. for now i add this. pending

#            dracut_cmd = (['/usr/bin/dracut', '--force', '--kver', kernel_version] +
#                          modules_add + modules_remove + drivers_add +
#                          drivers_remove + ['/tmp/' + ramdisk_file])

            initramfs_cmd = (['/usr/sbin/mkinitramfs', '-o', '/tmp/' + ramdisk_file, kernel_version ]);

            create = subprocess.Popen(initramfs_cmd, stdout=subprocess.PIPE)
            while create.poll() is None:
                line = create.stdout.readline()

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.info(exc_value)
            # self.logger.debug(traceback.format_exc())
            initramfs_succeed = False

        if create and create.returncode:
            initramfs_succeed = False

        if not create:
            initramfs_succeed = False

        os.fchdir(real_root)
        os.chroot(".")
        os.close(real_root)
        os.close(chroot_path)
        cleanup_mounts(image_path)

        if not initramfs_succeed:
            self.logger.info("Error while building ramdisk.")
            return False,"Problem building ramdisk"

        # the defaults for redhat derivatives
        initrd_path = image_path + '/tmp/' + ramdisk_file
        kernel_path = image_path + '/boot/vmlinuz-' + kernel_version

        if not os.path.isfile(kernel_path):
            self.logger.info(f"Unable to find kernel in {kernel_path}")
            return False, f"Unable to find kernel in {kernel_path}"

        if not os.path.isfile(initrd_path):
            self.logger.info(f"Unable to find initrd in {initrd_path}")
            return False, f"Unable to find initrd in {initrd_path}"

        # copy initrd file to inherit perms from parent folder
        shutil.copy(initrd_path, files_path + '/' + ramdisk_file)
        os.remove(initrd_path)
        shutil.copy(kernel_path, files_path + '/' + kernel_file)
        os.chown(files_path + '/' + ramdisk_file, user_id, grp_id)
        os.chmod(files_path + '/' + ramdisk_file, 0o644)
        os.chown(files_path + '/' + kernel_file, user_id, grp_id)
        os.chmod(files_path + '/' + kernel_file, 0o644)

        return True, "Success", kernel_file, ramdisk_file

