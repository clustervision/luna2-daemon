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
export MY_LOCAL_DISK_NAME=/dev/sda
export MY_LOCAL_DISK_SECTORS=   # nr of sectors, optional. if defined, then verified.
export PARTITION_MY_DISK=yes
export FORMAT_MY_DISK=yes
export MAKE_BOOT=yes            # configures and installs grub/shim for standalone boots
EOF
chmod 755 /tmp/my-local-disk.sh
else
  echo "** DISKFULL script: my-local-disk override found"
fi
cat /tmp/my-local-disk.sh
echo "*** DISKFULL script \$rootmnt: $rootmnt"
    """

    partscript = """
. /tmp/my-local-disk.sh
echo "*** DISKFULL script: === Using disk [$MY_LOCAL_DISK_NAME] ==="
cat << 'DISKEOF' > /tmp/my-fetch-disk.sh
export BYUUID=$(echo $MY_LOCAL_DISK_NAME | grep 'by-uuid' &> /dev/null && echo yes)
if [ "$BYUUID" ]; then
    export MY_LOCAL_DISK_NAME=$(readlink -f $MY_LOCAL_DISK_NAME)
    echo "*** DISKFULL script: UUID translates to $MY_LOCAL_DISK_NAME"
fi
if [ ! -e $MY_LOCAL_DISK_NAME ]; then
    echo "!!! DISKFULL script: \$MY_LOCAL_DISK_NAME [$MY_LOCAL_DISK_NAME] does not exist - Have to STOP !!!"
    exit 1
fi
export DP=$(echo $MY_LOCAL_DISK_NAME | grep -i nvme &> /dev/null && echo p)
export BYID=$(echo $MY_LOCAL_DISK_NAME | grep 'by-id' &> /dev/null && echo yes)
export BYPATH=$(echo $MY_LOCAL_DISK_NAME | grep 'by-path' &> /dev/null && echo yes)
if [ "$BYID" ] || [ "$BYPATH" ]; then
    export DP="-part"
fi
DISKEOF
. /tmp/my-fetch-disk.sh

if [ "$MY_LOCAL_DISK_SECTORS" ]; then
        SECTORS=$(cat /sys/block/${MY_LOCAL_DISK_NAME}/size)
        if [ "$SECTORS" != "$MY_LOCAL_DISK_SECTORS" ]; then
                echo "!!! Disk $MY_LOCAL_DISK_NAME has $SECTORS sectors, but expected $MY_LOCAL_DISK_SECTORS sectors - Have to STOP !!!"
                exit 1
        fi
fi
if [ "$PARTITION_MY_DISK" == "yes" ]; then
        echo "*** DISKFULL script: creating partitions"
        for t in 1 2 3 4 5 6; do
                parted $MY_LOCAL_DISK_NAME -s rm $t 2> /dev/null
        done
        parted $MY_LOCAL_DISK_NAME -s 'mklabel gpt'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart efi fat32 1 1g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart boot ext4 1g 2g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart swap linux-swap 2g 4g'
        parted $MY_LOCAL_DISK_NAME -s 'mkpart root ext4 4g 100%'
        parted $MY_LOCAL_DISK_NAME -s 'set 2 boot on'
        parted $MY_LOCAL_DISK_NAME -s 'name 1"EFI System Partition"'
fi
echo "*** DISKFULL script: waiting for partitions"
while [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}1 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}2 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}3 ]] || [[ ! -b ${MY_LOCAL_DISK_NAME}${DP}4 ]]; do sleep 1; done

if [ "$FORMAT_MY_DISK" == "yes" ]; then
        echo "*** DISKFULL script: formatting partitions"
        mkswap ${MY_LOCAL_DISK_NAME}${DP}3
        swaplabel -L swappart ${MY_LOCAL_DISK_NAME}${DP}3

        mkfs.fat -F 16 ${MY_LOCAL_DISK_NAME}${DP}1
        mkfs.ext4 ${MY_LOCAL_DISK_NAME}${DP}2
        mkfs.ext4 ${MY_LOCAL_DISK_NAME}${DP}4
fi
echo "*** DISKFULL script: mounting disks"
umount -l "$rootmnt" &> /dev/null
mount ${MY_LOCAL_DISK_NAME}${DP}4 "$rootmnt"
mkdir "$rootmnt"/boot
mount ${MY_LOCAL_DISK_NAME}${DP}2 "$rootmnt"/boot
mkdir "$rootmnt"/boot/efi
mount ${MY_LOCAL_DISK_NAME}${DP}1 "$rootmnt"/boot/efi
    """

    postscript = """
. /tmp/my-local-disk.sh
. /tmp/my-fetch-disk.sh

mkdir "$rootmnt"/proc "$rootmnt"/dev "$rootmnt"/sys &> /dev/null
mount -t proc proc "$rootmnt"/proc 
mount -t devtmpfs devtmpfs "$rootmnt"/dev
mount -t sysfs sysfs "$rootmnt"/sys

echo "*** DISKFULL script: writing fstab"
FSTAB_DISK=${MY_LOCAL_DISK_NAME}
FSTAB_DP=${DP}
if [ "$BYPATH" ]; then
    FSTAB_DISK=$(readlink -f ${MY_LOCAL_DISK_NAME})
    FSTAB_DP=$(echo $FSTAB_DISK | grep -i nvme &> /dev/null && echo p)
fi

FSTAB_DISK_P1=$(blkid -o export ${FSTAB_DISK}${FSTAB_DP}1 | grep -w UUID || echo ${FSTAB_DISK}${FSTAB_DP}1)
FSTAB_DISK_P2=$(blkid -o export ${FSTAB_DISK}${FSTAB_DP}2 | grep -w UUID || echo ${FSTAB_DISK}${FSTAB_DP}2)
FSTAB_DISK_P3=$(blkid -o export ${FSTAB_DISK}${FSTAB_DP}3 | grep -w UUID || echo ${FSTAB_DISK}${FSTAB_DP}3)
FSTAB_DISK_P4=$(blkid -o export ${FSTAB_DISK}${FSTAB_DP}4 | grep -w UUID || echo ${FSTAB_DISK}${FSTAB_DP}4)

grep -v -e "${FSTAB_DISK}" -e "${FSTAB_DISK_P4}" -e "${FSTAB_DISK_P3}" \
        -e "${FSTAB_DISK_P2}" -e "${FSTAB_DISK_P1}" "$rootmnt"/etc/fstab > /tmp/fstab
grep -v -w '/' /tmp/fstab > "$rootmnt"/etc/fstab

cat << EOF >> "$rootmnt"/etc/fstab
${FSTAB_DISK_P4}   /       ext4    defaults        1 1
${FSTAB_DISK_P2}   /boot   ext4    defaults        1 2
${FSTAB_DISK_P1}   /boot/efi   vfat    defaults        1 2
${FSTAB_DISK_P3}   swap    swap    defaults        0 0
EOF

if [ "$MAKE_BOOT" == "yes" ]; then
    echo "*** DISKFULL script: configuring grub/shim boot partition"
    rm -rf "$rootmnt"/lib/dracut/modules.d/95luna/
    mkdir -p "$rootmnt"/boot/efi/EFI

    OS_ID=$(chroot "$rootmnt" /bin/bash -c '. /etc/os-release >/dev/null 2>&1; echo $ID')
    DISTRO=$(ls "$rootmnt"/boot/efi/EFI/ 2>/dev/null | grep -im1 -e ubuntu -e rocky -e redhat -e alma -e centos)
    if [ ! "$DISTRO" ]; then
        DISTRO=$(echo "$OS_ID" | grep -iw ubuntu >/dev/null 2>&1 && echo ubuntu || echo rocky)
    fi

    EFI_TARGET=x86_64-efi
    EFI_SHIM=shimx64.efi
    EFI_GRUB=grubx64.efi
    if chroot "$rootmnt" /bin/bash -c "[ -e /usr/lib/shim/shimaa64.efi.signed ] || uname -m | grep -Eq '^(aarch64|arm64)$'"; then
        EFI_TARGET=arm64-efi
        EFI_SHIM=shimaa64.efi
        EFI_GRUB=grubaa64.efi
    fi

    CHROOT_GRUB_INSTALL=$(chroot "$rootmnt" /bin/bash -c 'if command -v grub2-install >/dev/null 2>&1; then echo grub2-install; elif command -v grub-install >/dev/null 2>&1; then echo grub-install; fi')
    CHROOT_GRUB_MKCONFIG=$(chroot "$rootmnt" /bin/bash -c 'if command -v grub2-mkconfig >/dev/null 2>&1; then echo grub2-mkconfig; elif command -v grub-mkconfig >/dev/null 2>&1; then echo grub-mkconfig; fi')

    if [ "$OS_ID" == "ubuntu" ] && [ "$CHROOT_GRUB_INSTALL" ]; then
        echo "*** DISKFULL script: installing ubuntu EFI bootloader [$EFI_TARGET]"
        chroot "$rootmnt" /bin/bash -c "$CHROOT_GRUB_INSTALL --target=${EFI_TARGET} --efi-directory=/boot/efi --bootloader-id=ubuntu --no-nvram"
        chroot "$rootmnt" /bin/bash -c "$CHROOT_GRUB_INSTALL --target=${EFI_TARGET} --efi-directory=/boot/efi --bootloader-id=ubuntu --removable --no-nvram"
        DISTRO=ubuntu
    fi

    EFI_LOADER=$EFI_SHIM
    if [ ! -e "$rootmnt"/boot/efi/EFI/${DISTRO}/${EFI_LOADER} ]; then
        EFI_LOADER=$EFI_GRUB
    fi

    if [ -e "$rootmnt"/boot/efi/EFI/${DISTRO}/${EFI_LOADER} ]; then
        BOOT_DISK=$(readlink -f ${MY_LOCAL_DISK_NAME} 2>/dev/null || echo ${MY_LOCAL_DISK_NAME})
        SH=$(chroot "$rootmnt" /bin/bash -c "efibootmgr -v 2>/dev/null|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'")
        if [ "$SH" ]; then
            chroot "$rootmnt" /bin/bash -c "efibootmgr -B -b $SH"
        fi
        chroot "$rootmnt" /bin/bash -c "if command -v efibootmgr >/dev/null 2>&1 && efibootmgr -v >/dev/null 2>&1; then efibootmgr --disk \"${BOOT_DISK}\" --part 1 --create --label \"Shim1\" --loader /EFI/${DISTRO}/${EFI_LOADER}; else echo '*** DISKFULL script: efibootmgr unavailable or EFI vars inaccessible, relying on fallback bootloader'; fi"
    fi

    if [ "$OS_ID" == "ubuntu" ]; then
        if [ "$CHROOT_GRUB_MKCONFIG" ]; then
            chroot "$rootmnt" /bin/bash -c "$CHROOT_GRUB_MKCONFIG -o /boot/grub/grub.cfg"
        fi
    elif [ "$CHROOT_GRUB_MKCONFIG" ]; then
        chroot "$rootmnt" /bin/bash -c "$CHROOT_GRUB_MKCONFIG -o /boot/efi/EFI/${DISTRO}/grub.cfg"
    fi
    # commented out next command as it imposes reboots. When netboot is set to no and with correct bios settings,
    # this would impose desired behavior. To cover all bases, we now relabel before the pivot. See below.
    #$null > "$rootmnt"/.autorelabel
fi

chroot "$rootmnt" /bin/bash -c "cd /boot && ln -s /boot boot; \
                              restorecon -r -p / 2> /dev/null"

umount "$rootmnt"/sys
umount "$rootmnt"/dev
umount "$rootmnt"/proc
echo "*** DISKFULL script: done"
    """
