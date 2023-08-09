#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        cd /sysroot
        cd etc/sysconfig/network-scripts
        echo DEVICE=$DEVICE >> ifcfg-$DEVICE
        echo NAME=$DEVICE >> ifcfg-$DEVICE
        echo IPADDR=$IPADDR >> ifcfg-$DEVICE
        echo PREFIX=$PREFIX >> ifcfg-$DEVICE
        echo NETMASK=$NETMASK >> ifcfg-$DEVICE
    """

    hostname = """
        cd /sysroot
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        echo "HOSTNAME=$HOSTNAME" >> etc/sysconfig/network
        echo "$HOSTNAME" > etc/hostname
    """

    gateway = """
        cd /sysroot
        echo "GATEWAY=$GATEWAY" >> etc/sysconfig/network
    """