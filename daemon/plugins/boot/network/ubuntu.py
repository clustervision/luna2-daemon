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
Plugin Class ::  Default Network Interface Plugin.
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
    This is default class for Network interfaces.
    """

    def __init__(self):
        """
        config = segment that handles interface configuration in template
        """

    interface = """
if [ ! -d $rootmnt/etc/netplan/ ]; then
    mkdir -p $rootmnt/etc/netplan/
fi
if [ ! -f $rootmnt/etc/netplan/99_config.yaml ]; then
cat << EOF > $rootmnt/etc/netplan/99_config.yaml
network:
  version: 2
  renderer: networkd
  ethernets:
EOF
fi

cat << EOF >> $rootmnt/etc/netplan/99_config.yaml
    ${DEVICE}:
      addresses:
        - $IPADDR/$PREFIX
EOF
        #$NETMASK
        #$ZONE
        #$OPTIONS
    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        echo "$HOSTNAME" > $rootmnt/etc/hostname
        chroot $rootmnt /usr/bin/hostnamectl --static set-hostname $HOSTNAME
    """

    gateway = """
cat << EOF >> $rootmnt/etc/netplan/99_config.yaml
      routes:
        - to: default
          via: $GATEWAY
          metric: $METRIC
EOF
    """

    dns = """
cat << EOF >> $rootmnt/etc/netplan/99_config.yaml
      nameservers:
          search: [$SEARCH]
          addresses: [$NAMESERVER]
EOF
        echo "search $SEARCH" > $rootmnt/etc/resolv.conf
        echo "nameserver $NAMESERVER" >> $rootmnt/etc/resolv.conf
        chroot $rootmnt netplan apply 2> /dev/null
    """

