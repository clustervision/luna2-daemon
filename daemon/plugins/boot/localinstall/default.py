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
This the default localdisk/grub plugin. It provides info for local install

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class Plugin():
    """
    Class for local install operations
    
    This plugin needs a mandatory variable set for template functionality
    -- grub
    """
        

    """ Other usefull info that can be used or incorporated:

cat << EOF > /sysroot/etc/default/grub
GRUB_DISABLE_OS_PROBER=true
EOF
chroot /sysroot /bin/bash -c \
    "/usr/sbin/grub2-mkconfig -o /boot/efi/EFI/centos/grub.cfg; \
     /usr/sbin/grub2-install /dev/disk/by-path/pci-0000:13:00.0-nvme-1; \
     /usr/sbin/grub2-install /dev/disk/by-path/pci-0000:14:00.0-nvme-1; \
     mdadm --detail --scan --verbose >> /etc/mdadm.conf; \
     dracut -f"
cat << EOF >> /sysroot/etc/fstab
/dev/md0 /boot ext4 defaults 0 0
/dev/md1 /boot/efi vfat defaults 0 0
/dev/md2 /     ext4     defaults        0 0
EOF
    """

    grub = """
# we need the next mounts
mount -t proc proc /sysroot/proc
mount -t devtmpfs devtmpfs /sysroot/dev
mount -t sysfs sysfs /sysroot/sys
# Remove (our) existing shim as it will not work after reinstall
# Note that this won't work with 9+ entries. i don't look for hex 10+ (a,b,c...)
SH=$(chroot /sysroot /bin/bash -c "efibootmgr -v|grep Shim1|grep -oE '^Boot[0-9]+'|grep -oE '[0-9]+'")
if [ "$SH" ]; then
        echo 'Shim found on boot '$SH
        chroot /sysroot /bin/bash -c "efibootmgr -B -b $SH"
        echo Remove
        chroot /sysroot /bin/bash -c "efibootmgr -v"
        echo Clean
fi
# install a fresh one...
chroot /sysroot /bin/bash -c "efibootmgr --verbose --disk /dev/sda --part 1 --create --label \"Shim1\" --loader /EFI/rocky/shimx64.efi"
# that we now point to Grub2
# note that we have 'rocky' in the path. this varies between distros
chroot /sysroot /bin/bash -c "grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg"
# cleanup
umount /sysroot/dev
umount /sysroot/proc
umount /sysroot/sys
    """


