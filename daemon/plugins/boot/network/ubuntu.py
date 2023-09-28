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
EOF
        # $METRIC
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

    ntp = """
        echo "server  $NTPSERVER" > $rootmnt/etc/ntp.conf
        echo "fudge   $NTPSERVER stratum 10" >> $rootmnt/etc/ntp.conf
        echo "driftfile /etc/ntp/drift" >> $rootmnt/etc/ntp.conf
    """

