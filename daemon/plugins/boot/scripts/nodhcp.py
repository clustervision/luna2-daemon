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
    """

    partscript = """
parted /dev/sda -s 'mklabel gpt'
parted /dev/sda -s 'mkpart efi fat32 1 1g'
parted /dev/sda -s 'mkpart boot ext4 1g 2g'
parted /dev/sda -s 'mkpart swap linux-swap 2g 4g'
parted /dev/sda -s 'mkpart root ext4 4g 100%'
parted /dev/sda -s 'set 2 boot on'
parted /dev/sda -s 'name 1"EFI System Partition"'

while [[ ! -b /dev/sda1 ]] || [[ ! -b /dev/sda2 ]] || [[ ! -b /dev/sda3 ]] || [[ ! -b /dev/sda4 ]]; do sleep 1; done

mkswap /dev/sda3
swaplabel -L swappart /dev/sda3

mkfs.fat -F 16 /dev/sda1
mkfs.ext4 /dev/sda2
mkfs.ext4 /dev/sda4
mount /dev/sda4 /sysroot
mkdir /sysroot/boot
mount /dev/sda2 /sysroot/boot
mkdir /sysroot/boot/efi
mount /dev/sda1 /sysroot/boot/efi
    """

    postscript = """
if [ -f /sysroot/lib/dracut/modules.d/95luna/module-setup.sh-old ]; then
	mv /sysroot/lib/dracut/modules.d/95luna/module-setup.sh{-old,}
fi
mkdir /sysroot/luna
#chroot /sysroot /bin/bash -c "mkinitrd /boot/initramfs-$(uname -r).img $(uname -r) --force"
#dracut --add luna --force --kver=$(uname -r) /boot/initramfs-$(uname -r).img
#chroot /sysroot /bin/bash -c "dracut --force --add luna --add-drivers \"ipmi_devintf ipmi_si ipmi_msghandler\" --kver=$(uname -r)"
#chroot /sysroot /bin/bash -c "dracut --force --add luna --add syslog --add-drivers \"ipmi_devintf ipmi_si ipmi_msghandler\" --kver=$(uname -r) /boot/initramfs-$(uname -r).img"

mkdir /sysroot/proc /sysroot/dev /sysroot/sys
mount -t proc proc /sysroot/proc
mount -t devtmpfs devtmpfs /sysroot/dev
mount -t sysfs sysfs /sysroot/sys

# ----------------------------------------

cat << EOF > /sysroot/etc/systemd/system/luna-postinstall.service
[Unit]
Description=Luna post install script
Requires=local-fs.target
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/luna/post-install.sh

[Install]
WantedBy=multi-user.target
EOF

chroot /sysroot /bin/bash -c "systemctl enable luna-postinstall"

# ----------------------------------------

cat << EOF > /sysroot/usr/local/luna/post-install.sh
#!/bin/bash

# -------- luna stuff -------
# to be run AFTER an install and only once
# ---------------------------

#LOCALBOOT=`grep luna_netboot /lib/dracut/modules.d/95luna/params.dat 2> /dev/null | cut -f2 -d'='`
#if [ "$LOCALBOOT" == "0" ] || [ "$LOCALBOOT" == "no" ]; then
#	echo 'Luna: no netboot so we wont alter the ramdisk'
#	exit
#fi
echo 'Luna2: preparing the ramdisk for secure boot'

cd /lib/dracut/modules.d/95luna/
#mv luna-start.sh{,-old}
#mv module-setup.sh{,-old}
#mv luna-start{-local,}.sh
#mv module-setup{-local,}.sh
KVER=\$(uname -r)
dracut --kver $KVER --force
#dracut --force --add luna --add syslog --add-drivers \"ipmi_devintf ipmi_si ipmi_msghandler\" --kver=$(uname -r) 
systemctl disable luna-postinstall.service
EOF

# ----------------------------------------


cat << EOF >> /sysroot/etc/fstab                                                                                                                                                                                   
/dev/sda4   /       ext4    defaults        1 1                                                                                                                                                                    
/dev/sda2   /boot   ext4    defaults        1 2                                                                                                                                                                    
/dev/sda1   /boot/efi   vfat    defaults        1 2                                                                                                                                                                
/dev/sda3   swap    swap    defaults        0 0                                                                                                                                                                    
EOF

SH=`chroot /sysroot /bin/bash -c "efibootmgr -v|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'"`
if [ "$SH" ]; then
        echo 'Shim found on boot '$SH
        chroot /sysroot /bin/bash -c "efibootmgr -B -b $SH"
        echo Remove
        chroot /sysroot /bin/bash -c "efibootmgr -v"
        echo Clean
fi
DISTRO=$(ls /sysroot/boot/efi/EFI/ | grep -ie rocky -e redhat -e alma -e centos || echo rocky)
chroot /sysroot /bin/bash -c "efibootmgr --verbose --disk /dev/sda --part 1 --create --label \"Shim1\" --loader /EFI/${DISTRO}/shimx64.efi; \
                              grub2-mkconfig -o /boot/efi/EFI/${DISTRO}/grub.cfg; \
                              cd /boot && ln -s /boot boot; \
                              restorecon -r -p / 2> /dev/null"

umount /sysroot/sys
umount /sysroot/dev
umount /sysroot/proc
    """
