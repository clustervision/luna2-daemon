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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
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
# from utils.helper import Helper

# Debian and Ubuntu ship two initramfs builders and an image may carry either, so
# unlike the redhat plugin this one has to choose. Both spellings of each are probed
# because the packaging has moved them between sbin and bin over the years.
DRACUT_PATHS = ('/usr/bin/dracut', '/usr/sbin/dracut')
MKINITRAMFS_PATHS = ('/usr/sbin/mkinitramfs', '/usr/bin/mkinitramfs')


def initramfs_command(kernel_version, ramdisk_file, exists=os.path.exists):
    """Return (argv, builder_name) for building this image's initramfs, or (None, None).

    CALL THIS ONLY AFTER os.chroot(image_path). Every path it probes is absolute, so
    inside the chroot it asks "what was this IMAGE built with"; called before, the
    identical code asks the CONTROLLER and answers confidently for the wrong machine.
    That is what `exists` is for as well -- it keeps the probes injectable so the
    choice can be tested without a real image.

    The only question asked here is WHICH BUILDER THIS IMAGE HAS. dracut wins when it
    has both: before ubuntu 25.10 it is not a default and its presence is deliberate,
    and from 25.10 it is the native tool.

    Nothing about lpart is probed, deliberately. What ends up inside the ramdisk is
    the client package's business: it ships a dracut module, an initramfs-tools hook,
    or both, and each pulls in its own toolset.

    luna is the one exception, and it is named rather than left to dracut. dracut
    auto-includes an installed module only while every module that module depends on
    can also be installed; when one cannot it drops the module, prints an [E], and
    STILL EXITS 0. The initramfs then packs and serves like any other while
    containing no installer at all, and the node boots to "don't know how to handle
    root=luna" -- ubuntu 26 hit exactly this, because it packages dracut's network
    modules separately and 95luna depends on them. Naming it makes dracut fail (rc 1,
    no artifact) instead, which the caller already turns into a failed pack.

    The cost is that an image with dracut but no client no longer packs at all, where
    it used to produce a client-less ramdisk. That ramdisk could never install a node,
    so failing at pack time is the better of the two -- and it is the outcome the
    redhat plugin already produces, though by the opposite test: it force-adds luna
    only when --list-modules does NOT list it. That leaves redhat exposed to the case
    here, because --list-modules reports a module that is present on disk whether or
    not its dependencies can be resolved.
    """
    output = '/tmp/' + ramdisk_file
    dracut = next((path for path in DRACUT_PATHS if exists(path)), None)
    if dracut:
        return [dracut, '--force', '--add', 'luna', '--kver', kernel_version, output], 'dracut'
    mkinitramfs = next((path for path in MKINITRAMFS_PATHS if exists(path)), None)
    if mkinitramfs:
        return [mkinitramfs, '-o', output, kernel_version], 'mkinitramfs'
    return None, None


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
          systemroot   for debian/ubuntu this is whatever the initramfs mounted the target
          systemroot   root on, asked of both frameworks: initramfs-tools' $rootmnt, else
          systemroot   dracut's $NEWROOT. note: $ROOT (not $rootmnt) points to /luna
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

    # Ask each initramfs framework in its own language, because ubuntu can be packed
    # with either and they do not share a name for the target root: initramfs-tools
    # exports rootmnt=/root, dracut exports NEWROOT=/sysroot and has no notion of
    # rootmnt at all. Order matters -- rootmnt first keeps the passthrough that
    # initramfs-tools relies on, and the literal is only reached when neither answered.
    # A bare "$rootmnt" resolves to nothing under dracut, and every "/${rootmnt}/..."
    # in the installer then addresses the initramfs' own root instead of the image.
    systemroot = "${rootmnt:-${NEWROOT:-/sysroot}}"

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
            #os.remove(tmp_dir + '/' + packed_image_file)
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
        grab_filesystems = ['/','/boot']



        # add modules goes in /image/etc/initramfs-tools/modules

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
        builder = None

        try:
            # the image decides, not the ubuntu release, and not the controller --
            # see initramfs_command, which must be called from inside this chroot
            initramfs_cmd, builder = initramfs_command(kernel_version, ramdisk_file)
            if initramfs_cmd:
                self.logger.info(f"Building initramfs for osimage '{osimage}' with {builder}")
                create = subprocess.Popen(initramfs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                while create.poll() is None:
                    line = create.stdout.readline()

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.info(exc_value)
            self.logger.debug(exc_traceback.format_exc())
            initramfs_succeed = False

        message = "Problem building initrd"
        if create and create.returncode:
            initramfs_succeed = False
            all_messages = create.stderr.read().decode().split('\n')
            message = '.'.join(all_messages[:3])

        if not create:
            initramfs_succeed = False
            message = (
                f"Could not open subprocess to run {builder}" if builder else
                f"No initramfs builder in osimage '{osimage}': neither dracut nor "
                f"mkinitramfs is installed in the image"
            )

        os.fchdir(real_root)
        os.chroot(".")
        os.close(real_root)
        os.close(chroot_path)
        cleanup_mounts(image_path)

        if not initramfs_succeed:
            self.logger.info(f"Error while building ramdisk: {message}")
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

        # copy initrd file to inherit perms from parent folder
        shutil.move(initrd_path, files_path + '/' + ramdisk_file)
        shutil.copy(kernel_path, files_path + '/' + kernel_file)
        os.chown(files_path + '/' + ramdisk_file, user_id, grp_id)
        os.chmod(files_path + '/' + ramdisk_file, 0o644)
        os.chown(files_path + '/' + kernel_file, user_id, grp_id)
        os.chmod(files_path + '/' + kernel_file, 0o644)

        return True, "Success", kernel_file, ramdisk_file
