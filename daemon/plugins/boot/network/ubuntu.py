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

    init = """
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

if [ ! "$(grep $DEVICE $rootmnt/etc/netplan/99_config.yaml)" ]; then
cat << EOF >> $rootmnt/etc/netplan/99_config.yaml
    ${DEVICE}:
      addresses:
        # ip_ipv4_${DEVICE}
        # ip_ipv6_${DEVICE}
      routes:
        # route_ipv4_${DEVICE}
        # route_ipv6_${DEVICE}
      nameservers:
        # ns_ipv4_${DEVICE}
        # ns_ipv6_${DEVICE}
EOF
fi
    """

    # ipv4
    interface = """
        sed -i 's/# ip_ipv4_'$DEVICE'/- '$IPADDR'\/'$PREFIX'/' $rootmnt/etc/netplan/99_config.yaml
    """

    gateway = """
cat << EOF > /tmp/99_config.yaml
        - to: default
          via: $GATEWAY
          metric: $METRIC
EOF
        sed -i '/# route_ipv4_'$DEVICE'/r /tmp/99_config.yaml' $rootmnt/etc/netplan/99_config.yaml
        chroot $rootmnt netplan apply 2> /dev/null
    """

    dns = """
cat << EOF > /tmp/99_config.yaml
          search: [$SEARCH]
          addresses: [$NAMESERVER]
EOF
        sed -i '/# ns_ipv4_'$DEVICE'/r /tmp/99_config.yaml' $rootmnt/etc/netplan/99_config.yaml
        echo "search $SEARCH" > $rootmnt/etc/resolv.conf
        echo "nameserver $NAMESERVER" >> $rootmnt/etc/resolv.conf
        chroot $rootmnt netplan apply 2> /dev/null
    """

    # ipv6
    interface_ipv6 = """
        sed -i 's/# ip_ipv6_'$DEVICE'/- '$IPADDR'\/'$PREFIX'/' $rootmnt/etc/netplan/99_config.yaml
    """

    gateway_ipv6 = """
cat << EOF > /tmp/99_config.yaml
        - to: default
          via: $GATEWAY
          metric: $METRIC
EOF
        sed -i '/# route_ipv6_'$DEVICE'/r /tmp/99_config.yaml' $rootmnt/etc/netplan/99_config.yaml
        chroot $rootmnt netplan apply 2> /dev/null
    """

    dns_ipv6 = """
cat << EOF > /tmp/99_config.yaml
          search: [$SEARCH]
          addresses: [$NAMESERVER]
EOF
        sed -i '/# ns_ipv6_'$DEVICE'/r /tmp/99_config.yaml' $rootmnt/etc/netplan/99_config.yaml
        echo "search $SEARCH" > $rootmnt/etc/resolv.conf
        echo "nameserver $NAMESERVER" >> $rootmnt/etc/resolv.conf
        chroot $rootmnt netplan apply 2> /dev/null
    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        echo "$HOSTNAME" > $rootmnt/etc/hostname
        chroot $rootmnt /usr/bin/hostnamectl --static set-hostname $HOSTNAME
    """

