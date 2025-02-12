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
Plugin Class ::  Default Install for pre, part, and post plugin while node install.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class Plugin():
    """
    This is default class for pre, part, and post plugins.
    """

    def __init__(self):
        """
        prescript = runs before mounting sysroot during install
        partscript = runs before mounting sysroot during install
        postscript = runs before OS pivot
        """

    prescript = """
if [ ! -d /tmp ]; then mkdir /tmp; fi
cat << EOF >> /tmp/my-local-disk.sh
export MY_LOCAL_DISK_NAME=/dev/sda
export MY_LOCAL_DISK_SECTORS=   # nr of sectors, optional. if defined, then verified.
export PARTITION_MY_DISK=yes
export FORMAT_MY_DISK=yes
export MAKE_BOOT=yes            # configures and installs grub/shim for standalone boots
EOF
chmod 755 /tmp/my-local-disk.sh
    """

    partscript = """
. /tmp/my-local-disk.sh
echo "=== Using disk [$MY_LOCAL_DISK_NAME] ==="
DP=$(echo $MY_LOCAL_DISK_NAME | grep -i nvme && echo p)
if [ "$MY_LOCAL_DISK_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK_SECTORS" ]; then
                echo "!!! Disk $MY_LOCAL_DISK_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$PARTITION_MY_DISK" == "yes" ]; then
        for t in 1 2 3 4 5 6; do
                parted $MY_LOCAL_DISK_NAME -s rm $t
        done
        parted $MY_LOCAL_DISK_NAME -s 'mklabel gpt'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart efi fat32 1 1g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart boot ext4 1g 2g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart swap linux-swap 2g 4g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart root ext4 4g 100%'
        parted $MY_LOCAL_DISK_NAME -s 'set 2 boot on'
        parted $MY_LOCAL_DISK_NAME -s 'name 1"EFI System Partition"'
fi
while [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}1 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}2 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}3 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}4 ]]; do sleep 1; done

if [ "$FORMAT_MY_DISK" == "yes" ]; then
        mkswap ${MY_LOCAL_DISK_NAME}${DP}3
        swaplabel -L swappart ${MY_LOCAL_DISK_NAME}${DP}3

        mkfs.fat -F 16 ${MY_LOCAL_DISK_NAME}${DP}1
        mkfs.ext4 ${MY_LOCAL_DISK_NAME}${DP}2
        mkfs.ext4 ${MY_LOCAL_DISK_NAME}${DP}4
fi
umount -l /sysroot &> /dev/null
mount ${MY_LOCAL_DISK_NAME}${DP}4 /sysroot
mkdir /sysroot/boot
mount ${MY_LOCAL_DISK_NAME}${DP}2 /sysroot/boot
mkdir /sysroot/boot/efi
mount ${MY_LOCAL_DISK_NAME}${DP}1 /sysroot/boot/efi
    """

    postscript = """
. /tmp/my-local-disk.sh
DP=$(echo $MY_LOCAL_DISK_NAME | grep -i nvme && echo p)
mkdir /sysroot/proc /sysroot/dev /sysroot/sys &> /dev/null
mount -t proc proc /sysroot/proc 
mount -t devtmpfs devtmpfs /sysroot/dev
mount -t sysfs sysfs /sysroot/sys

grep -v ${MY_LOCAL_DISK_NAME} /sysroot/etc/fstab > /tmp/fstab
grep -v -w '/' /tmp/fstab > /sysroot/etc/fstab

cat << EOF >> /sysroot/etc/fstab
${MY_LOCAL_DISK_NAME}${DP}4   /       ext4    defaults        1 1
${MY_LOCAL_DISK_NAME}${DP}2   /boot   ext4    defaults        1 2
${MY_LOCAL_DISK_NAME}${DP}1   /boot/efi   vfat    defaults        1 2
${MY_LOCAL_DISK_NAME}${DP}3   swap    swap    defaults        0 0
EOF

if [ "$MAKE_BOOT" ]; then
    rm -rf /sysroot/lib/dracut/modules.d/95luna/

    SH=$(chroot /sysroot /bin/bash -c "efibootmgr -v|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'")
    if [ "$SH" ]; then
        chroot /sysroot /bin/bash -c "efibootmgr -B -b $SH"
    fi
    DISTRO=$(ls /sysroot/boot/efi/EFI/ | grep -ie rocky -e redhat -e alma -e centos || echo rocky)
    chroot /sysroot /bin/bash -c "efibootmgr --disk ${MY_LOCAL_DISK_NAME} --part 1 --create --label \"Shim1\" --loader /EFI/${DISTRO}/shimx64.efi"
    chroot /sysroot /bin/bash -c "grub2-mkconfig -o /boot/efi/EFI/${DISTRO}/grub.cfg"
    $null > /sysroot/.autorelabel
fi

umount /sysroot/sys
umount /sysroot/dev
umount /sysroot/proc
    """
