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
if [ ! -f /tmp/my-local-disk.sh ]; then
cat << EOF > /tmp/my-local-disk.sh
export MY_LOCAL_DISK1_NAME=/dev/sda
export MY_LOCAL_DISK2_NAME=/dev/sdb
export MY_LOCAL_DISK1_SECTORS=   # nr of sectors, optional. if defined, then verified.
export MY_LOCAL_DISK2_SECTORS=   # nr of sectors, optional. if defined, then verified.
export PARTITION_MY_DISK=yes
export FORMAT_MY_DISK=yes
export MAKE_BOOT=yes             # configures and installs grub/shim for standalone boots
EOF
chmod 755 /tmp/my-local-disk.sh
else
  echo "*** RAID1 script: my-local-disk override found"
fi
cat /tmp/my-local-disk.sh
    """

    partscript = """
. /tmp/my-local-disk.sh
echo "*** RAID1 script: === Using disk [$MY_LOCAL_DISK1_NAME] + [$MY_LOCAL_DISK2_NAME] ==="
cat << 'DISKEOF' > /tmp/my-fetch-disk.sh
if [ ! -e $MY_LOCAL_DISK1_NAME ]; then
    echo "!!! RAID1 script: \$MY_LOCAL_DISK1_NAME [$MY_LOCAL_DISK1_NAME] does not exist - Have to STOP !!!"
    exit 1
fi
if [ ! -e $MY_LOCAL_DISK2_NAME ]; then
    echo "!!! RAID1 script: \$MY_LOCAL_DISK2_NAME [$MY_LOCAL_DISK2_NAME] does not exist - Have to STOP !!!"
    exit 1
fi
export BYUUID1=$(echo $MY_LOCAL_DISK1_NAME | grep 'by-uuid' &> /dev/null && echo yes)
export BYUUID2=$(echo $MY_LOCAL_DISK2_NAME | grep 'by-uuid' &> /dev/null && echo yes)
if [ "$BYUUID1" ]; then
    export MY_LOCAL_DISK1_NAME=$(readlink -f $MY_LOCAL_DISK1_NAME)
    echo "*** RAID1 script: UUID1 translates to $MY_LOCAL_DISK1_NAME"
fi
if [ "$BYUUID2" ]; then
    export MY_LOCAL_DISK2_NAME=$(readlink -f $MY_LOCAL_DISK2_NAME)
    echo "*** RAID1 script: UUID2 translates to $MY_LOCAL_DISK2_NAME"
fi
export DP1=$(echo $MY_LOCAL_DISK1_NAME | grep -i nvme &> /dev/null && echo p)
export DP2=$(echo $MY_LOCAL_DISK2_NAME | grep -i nvme &> /dev/null && echo p)
export BYID1=$(echo $MY_LOCAL_DISK1_NAME | grep 'by-id' &> /dev/null && echo yes)
export BYPATH1=$(echo $MY_LOCAL_DISK1_NAME | grep 'by-path' &> /dev/null && echo yes)
if [ "$BYID1" ] || [ "$BYPATH1" ]; then
    export DP1="-part"
fi
export BYID2=$(echo $MY_LOCAL_DISK2_NAME | grep 'by-id' &> /dev/null && echo yes)
export BYPATH2=$(echo $MY_LOCAL_DISK2_NAME | grep 'by-path' &> /dev/null && echo yes)
if [ "$BYID2" ] || [ "$BYPATH2" ]; then
    export DP2="-part"
fi
DISKEOF
. /tmp/my-fetch-disk.sh

if [ "$MY_LOCAL_DISK1_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK1_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK1_SECTORS" ]; then
                echo "!!! RAID1 script: Disk $MY_LOCAL_DISK1_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK1_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$MY_LOCAL_DISK2_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK2_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK2_SECTORS" ]; then
                echo "!!! RAID1 script: Disk $MY_LOCAL_DISK2_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK2_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$PARTITION_MY_DISK" == "yes" ]; then
        echo "*** RAID1 script: creating partitions"
        for RAID_DISK in $MY_LOCAL_DISK1_NAME $MY_LOCAL_DISK2_NAME; do
                for t in 1 2 3 4 5 6; do
                        parted $RAID_DISK -s rm $t 2> /dev/null
                done
                parted $RAID_DISK -s 'mklabel gpt'
                parted $RAID_DISK -s 'mkpart efi fat32 1 1g'
                parted $RAID_DISK -s 'mkpart boot ext4 1g 2g'
                parted $RAID_DISK -s 'mkpart swap linux-swap 2g 4g'
                parted $RAID_DISK -s 'mkpart root ext4 4g 100%'
                parted $RAID_DISK -s 'set 1 boot on'
                parted $RAID_DISK -s 'set 4 raid on'
                parted $RAID_DISK -s 'name 1 "EFI System Partition"'
        done
fi
echo "*** RAID1 script: waiting for partitions"
while [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}1 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}2 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}3 ]] || [[ ! -b ${MY_LOCAL_DISK1_NAME}${DP1}4 ]]; do echo -n .; sleep 1; done
while [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}1 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}2 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}3 ]] || [[ ! -b ${MY_LOCAL_DISK2_NAME}${DP2}4 ]]; do echo -n .; sleep 1; done; echo

if [ "$FORMAT_MY_DISK" == "yes" ]; then
        echo "*** RAID1 script: formatting partitions"
        mkfs.fat -F 16 ${MY_LOCAL_DISK1_NAME}${DP1}1
        mkfs.ext4 ${MY_LOCAL_DISK1_NAME}${DP1}2
        MY_LOCAL_DISK1_UUID=$(blkid -o export ${MY_LOCAL_DISK1_NAME}${DP1}4 | grep -w UUID | awk -F '=' '{ print $2 }')
        MY_LOCAL_DISK2_UUID=$(blkid -o export ${MY_LOCAL_DISK2_NAME}${DP2}4 | grep -w UUID | awk -F '=' '{ print $2 }')
        # there is a fair share the RAID labeled disks are not availabe as a UUID block device. We test, try and move on.
        if [ "${MY_LOCAL_DISK1_UUID}" ] && [ "${MY_LOCAL_DISK2_UUID}" ] && [ -e /dev/disk/by-uuid/${MY_LOCAL_DISK1_UUID} ] && [ -e /dev/disk/by-uuid/${MY_LOCAL_DISK2_UUID} ]; then
            echo "*** RAID1 script: making RAID1 on [/dev/disk/by-uuid/${MY_LOCAL_DISK1_UUID}] + [/dev/disk/by-uuid/${MY_LOCAL_DISK2_UUID}]"
            echo y | mdadm --create /dev/md0 --metadata 1.2 --force --assume-clean --level=mirror --raid-devices=2 /dev/disk/by-uuid/${MY_LOCAL_DISK1_UUID} /dev/disk/by-uuid/${MY_LOCAL_DISK2_UUID}
        else
            echo "*** RAID1 script: making RAID1 on [${MY_LOCAL_DISK1_NAME}${DP1}4] + [${MY_LOCAL_DISK2_NAME}${DP2}4]"
            echo y | mdadm --create /dev/md0 --metadata 1.2 --force --assume-clean --level=mirror --raid-devices=2 ${MY_LOCAL_DISK1_NAME}${DP1}4 ${MY_LOCAL_DISK2_NAME}${DP2}4
        fi
        sleep 3
        mkfs.ext4 /dev/md0

        mkswap ${MY_LOCAL_DISK1_NAME}${DP1}3
        swaplabel -L swappart ${MY_LOCAL_DISK1_NAME}${DP1}3
        mkswap ${MY_LOCAL_DISK2_NAME}${DP2}3
        swaplabel -L swappart ${MY_LOCAL_DISK2_NAME}${DP2}3
fi
echo "*** RAID1 script: mounting disks"
umount -l /sysroot &> /dev/null
mount /dev/md0 /sysroot
mkdir /sysroot/boot
mount ${MY_LOCAL_DISK1_NAME}${DP1}2 /sysroot/boot
mkdir /sysroot/boot/efi
mount ${MY_LOCAL_DISK1_NAME}${DP1}1 /sysroot/boot/efi
    """

    postscript = """
. /tmp/my-local-disk.sh
. /tmp/my-fetch-disk.sh

mkdir /sysroot/proc /sysroot/dev /sysroot/sys &> /dev/null
mount -t proc proc /sysroot/proc 
mount -t devtmpfs devtmpfs /sysroot/dev
mount -t sysfs sysfs /sysroot/sys

echo "*** RAID1 script: writing fstab"
FSTAB_DISK1=${MY_LOCAL_DISK1_NAME}
FSTAB_DP1=${DP1}
if [ "$BYPATH1" ]; then
    FSTAB_DISK1=$(readlink -f ${MY_LOCAL_DISK1_NAME})
    FSTAB_DP1=$(echo $FSTAB_DISK1 | grep -i nvme &> /dev/null && echo p)
fi
FSTAB_DISK2=${MY_LOCAL_DISK2_NAME}
FSTAB_DP2=${DP2}
if [ "$BYPATH2" ]; then
    FSTAB_DISK2=$(readlink -f ${MY_LOCAL_DISK2_NAME})
    FSTAB_DP2=$(echo $FSTAB_DISK2 | grep -i nvme &> /dev/null && echo p)
fi

FSTAB_MD0=$(blkid -o export /dev/md0 | grep -w UUID || echo '/dev/md0')
FSTAB_DISK1_P1=$(blkid -o export ${FSTAB_DISK1}${FSTAB_DP1}1 | grep -w UUID || echo ${FSTAB_DISK1}${FSTAB_DP1}1)
FSTAB_DISK1_P2=$(blkid -o export ${FSTAB_DISK1}${FSTAB_DP1}2 | grep -w UUID || echo ${FSTAB_DISK1}${FSTAB_DP1}2)
FSTAB_DISK1_P3=$(blkid -o export ${FSTAB_DISK1}${FSTAB_DP1}3 | grep -w UUID || echo ${FSTAB_DISK1}${FSTAB_DP1}3)
FSTAB_DISK2_P3=$(blkid -o export ${FSTAB_DISK2}${FSTAB_DP2}3 | grep -w UUID || echo ${FSTAB_DISK2}${FSTAB_DP2}3)

grep -v -e md0 -e "${FSTAB_DISK1}" -e "${FSTAB_DISK2}" \
    -e "${FSTAB_MD0}" -e "${FSTAB_DISK1_P1}" -e "${FSTAB_DISK1_P2}" \
    -e "${FSTAB_DISK1_P3}" -e "${FSTAB_DISK2_P3}" /sysroot/etc/fstab > /tmp/fstab
grep -v -w '/' /tmp/fstab > /sysroot/etc/fstab

cat << EOF >> /sysroot/etc/fstab
${FSTAB_MD0}   /       ext4    defaults        1 1
${FSTAB_DISK1_P2}   /boot   ext4    defaults        1 2
${FSTAB_DISK1_P1}   /boot/efi   vfat    defaults        1 2
${FSTAB_DISK1_P3}   swap    swap    defaults        0 0
${FSTAB_DISK2_P3}   swap    swap    defaults        0 0
EOF

if [ "$MAKE_BOOT" == "yes" ]; then
    echo "*** RAID1 script: building new ramdisk"
    echo "AUTO -all" > /sysroot/etc/mdadm.conf
    chroot /sysroot /bin/bash -c "mdadm --detail --scan --verbose | grep ARRAY >> /etc/mdadm.conf"

    rm -rf /sysroot/lib/dracut/modules.d/95luna/
    chroot /sysroot /bin/bash -c "dracut -f --mdadmconf --add=mdraid --add-drivers='raid1'"

    echo "*** RAID1 script: configuring shim boot partition"
    GRUB_CMDLINE_LINUX=$(grep GRUB_CMDLINE_LINUX /sysroot/etc/default/grub || echo 'GRUB_CMDLINE_LINUX=')
    GRUB_CMDLINE_LINUX=$(echo $GRUB_CMDLINE_LINUX | tr -d '"')
    GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} rd.md=1 rd.md.conf=1 rd.auto=1 net.ifnames=1 biosdevname=0"
    GRUB_CMDLINE_LINUX=$(echo $GRUB_CMDLINE_LINUX | sed -e 's/GRUB_CMDLINE_LINUX=/GRUB_CMDLINE_LINUX="/' | sed -e 's/$/"/')
    grep -v GRUB_CMDLINE_LINUX /sysroot/etc/default/grub > /tmp/grub-def
    cat /tmp/grub-def > /sysroot/etc/default/grub
    echo "$GRUB_CMDLINE_LINUX" >> /sysroot/etc/default/grub

    SH=`chroot /sysroot /bin/bash -c "efibootmgr -v|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'"`
    if [ "$SH" ]; then
        chroot /sysroot /bin/bash -c "efibootmgr -B -b $SH"
    fi
    DISTRO=$(ls /sysroot/boot/efi/EFI/ | grep -ie rocky -e redhat -e alma -e centos || echo rocky)
    chroot /sysroot /bin/bash -c "efibootmgr --disk ${MY_LOCAL_DISK1_NAME}${DP1} --part 1 --create --label \"Shim1\" --loader /EFI/${DISTRO}/shimx64.efi; \
                                  grub2-mkconfig -o /boot/efi/EFI/${DISTRO}/grub.cfg"
    # commented out next command as it imposes reboots. When netboot is set to no and with correct bios settings,
    # this would impose desired behavior. To cover all bases, we now relabel before the pivot. See below.
    #$null > /sysroot/.autorelabel
fi

chroot /sysroot /bin/bash -c "cd /boot && ln -s /boot boot; \
                              restorecon -r -p / 2> /dev/null"

umount /sysroot/sys
umount /sysroot/dev
umount /sysroot/proc
echo "*** RAID1 script: done"
    """
