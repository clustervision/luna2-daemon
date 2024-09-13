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
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
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
export MY_LOCAL_DISK1_NAME=/dev/sda
export MY_LOCAL_DISK2_NAME=/dev/sdb
export MY_LOCAL_DISK1_SECTORS=   # nr of sectors, optional. if defined, then verified.
export MY_LOCAL_DISK2_SECTORS=   # nr of sectors, optional. if defined, then verified.
export PARTITION_MY_DISK=yes
export FORMAT_MY_DISK=yes
EOF
chmod 755 /tmp/my-local-disk.sh
    """

    partscript = """
. /tmp/my-local-disk.sh
echo "=== Using disk [$MY_LOCAL_DISK1_NAME] + [$MY_LOCAL_DISK2_NAME] for RAID1 ==="
DP1=$(echo $MY_LOCAL_DISK1_NAME | grep -i nvme && echo p)
DP2=$(echo $MY_LOCAL_DISK2_NAME | grep -i nvme && echo p)
if [ "$MY_LOCAL_DISK1_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK1_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK1_SECTORS" ]; then
                echo "!!! Disk $MY_LOCAL_DISK1_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK1_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$MY_LOCAL_DISK2_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK2_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK2_SECTORS" ]; then
                echo "!!! Disk $MY_LOCAL_DISK2_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK2_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$PARTITION_MY_DISK" == "yes" ]; then
        for RAID_DISK in $MY_LOCAL_DISK1_NAME $MY_LOCAL_DISK2_NAME; do
                for t in 1 2 3 4 5 6; do
                        parted $RAID_DISK -s rm $t
                done
                parted $RAID_DISK -s 'mklabel gpt'
                parted $RAID_DISK -s 'mkpart efi fat32 1 1g'
                parted $RAID_DISK -s 'mkpart boot ext4 1g 2g'
                parted $RAID_DISK -s 'mkpart swap linux-swap 2g 4g'
                parted $RAID_DISK -s 'mkpart root ext4 4g 100%'
                parted $RAID_DISK -s 'set 2 boot on'
                parted $RAID_DISK -s 'name 1"EFI System Partition"'
        done
fi
while [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}1 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}2 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}3 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}4 ]]; do sleep 1; done
while [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}1 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}2 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}3 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}4 ]]; do sleep 1; done

if [ "$FORMAT_MY_DISK" == "yes" ]; then
        echo y | mdadm --create /dev/md0 --metadata 1.0 --force --assume-clean --level=mirror --raid-devices=2 ${MY_LOCAL_DISK1_NAME}${DP1}1 ${MY_LOCAL_DISK2_NAME}${DP2}1
        sleep 3
        mkfs.fat -F 16 /dev/md0
        echo y | mdadm --create /dev/md1 --metadata 1.0 --force --assume-clean --level=mirror --raid-devices=2 ${MY_LOCAL_DISK1_NAME}${DP1}2 ${MY_LOCAL_DISK2_NAME}${DP2}2
        sleep 3
        mkfs.ext4 /dev/md1
        echo y | mdadm --create /dev/md2 --metadata 1.2 --force --assume-clean --level=mirror --raid-devices=2 ${MY_LOCAL_DISK1_NAME}${DP1}4 ${MY_LOCAL_DISK2_NAME}${DP2}4
        sleep 3
        mkfs.ext4 /dev/md2

        mkswap ${MY_LOCAL_DISK1_NAME}${DP1}3
        swaplabel -L swappart ${MY_LOCAL_DISK1_NAME}${DP1}3
        mkswap ${MY_LOCAL_DISK2_NAME}${DP2}3
        swaplabel -L swappart ${MY_LOCAL_DISK2_NAME}${DP2}3
fi
umount -l /sysroot &> /dev/null
mount /dev/md2 /sysroot
mkdir /sysroot/boot
mount /dev/md1 /sysroot/boot
mkdir /sysroot/boot/efi
mount /dev/md0 /sysroot/boot/efi
    """

    postscript = """
. /tmp/my-local-disk.sh
DP1=$(echo $MY_LOCAL_DISK1_NAME | grep -i nvme && echo p)
DP2=$(echo $MY_LOCAL_DISK2_NAME | grep -i nvme && echo p)
mkdir /sysroot/proc /sysroot/dev /sysroot/sys &> /dev/null
mount -t proc proc /sysroot/proc 
mount -t devtmpfs devtmpfs /sysroot/dev
mount -t sysfs sysfs /sysroot/sys

if [ ! -d /tmp ]; then mkdir /tmp; fi
grep -v -e md0 -e md1 -e md2 /sysroot/etc/fstab > /tmp/fstab
grep -v -w '/' /tmp/fstab > /sysroot/etc/fstab

cat << EOF >> /sysroot/etc/fstab
/dev/md2   /       ext4    defaults        1 1
/dev/md1   /boot   ext4    defaults        1 2
/dev/md0   /boot/efi   vfat    defaults        1 2
${MY_LOCAL_DISK1_NAME}${DP1}3   swap    swap    defaults        0 0
${MY_LOCAL_DISK2_NAME}${DP2}3   swap    swap    defaults        0 0
EOF

SH=`chroot /sysroot /bin/bash -c "efibootmgr -v|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'"`
if [ "$SH" ]; then
        echo 'Shim found on boot '$SH
        chroot /sysroot /bin/bash -c "efibootmgr -B -b $SH"
        echo Remove
        chroot /sysroot /bin/bash -c "efibootmgr -v"
        echo Clean
fi
chroot /sysroot /bin/bash -c "efibootmgr --verbose --disk /dev/md0 --part 1 --create --label \"Shim1\" --loader /EFI/rocky/shimx64.efi"
chroot /sysroot /bin/bash -c "grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg"

umount /sysroot/sys
umount /sysroot/dev
umount /sysroot/proc
    """
