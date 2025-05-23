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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
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

    init = ""

    interface = """
        cd /sysroot
        cd etc/sysconfig/network-scripts
        echo DEVICE=$DEVICE >> ifcfg-$DEVICE
        echo NAME=$DEVICE >> ifcfg-$DEVICE
        echo IPADDR=$IPADDR >> ifcfg-$DEVICE
        echo PREFIX=$PREFIX >> ifcfg-$DEVICE
        echo NETMASK=$NETMASK >> ifcfg-$DEVICE
        #$ZONE
        #$OPTIONS
    """

    hostname = """
        cd /sysroot
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        echo "HOSTNAME=$HOSTNAME" >> etc/sysconfig/network
        echo "$HOSTNAME" > etc/hostname
    """

    gateway = """
        cd /sysroot
        EXISTMETRIC=$(grep GATEWAYMETRIC etc/sysconfig/network || echo "999")
        if [ "$GATEWAY" ] && [ "$EXISTMETRIC" -gt "$METRIC" ]; then
            grep -vi GATEWAY etc/sysconfig/network > network.tmp
            cat network.tmp > etc/sysconfig/network
            echo "# Gateway belonging to $DEVICE" >> etc/sysconfig/network
            echo "GATEWAY=$GATEWAY" >> etc/sysconfig/network
            echo "METRIC=$METRIC" >> etc/sysconfig/network
            rm -f network.tmp
        fi
    """

    dns = """
        cd /sysroot
        if [ ! -e tmp/resolv.clear ]; then
            echo -n '' > etc/resolv.conf
            search=$(echo $SEARCH | awk '{gsub(/,|;/, " "); print}')
            echo "search $search" >> etc/resolv.conf
            > tmp/resolv.clear
        fi
        for server in $(echo $NAMESERVER|tr ',;' ' '); do
            echo "nameserver $server" >> etc/resolv.conf
        done
    """

    interface_ipv6 = ""
    gateway_ipv6 = ""
    dns_ipv6 = ""

