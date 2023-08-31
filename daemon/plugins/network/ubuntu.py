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
if [ ! -f $rootmnt/etc/netplan/99_config.yaml ]; then
cat << EOF > $rootmnt/etc/netplan/99_config.yaml
network:
  version: 2
  renderer: networkd
  ethernets:
EOF
fi

cat << EOF >> $rootmnt/etc/netplan/99_config.yaml
    $DEVICE
      addresses:
        - $IPADDR/$PREFIX
      routes:
        - to: default
          via: __${DEVICE}_GATEWAY__
      nameservers:
          search: [__${DEVICE}__SEARCH__]
          addresses: [__${DEVICE}__NAMESERVER__]
EOF
        #$NETMASK
        #$ZONE
        #$OPTIONS
    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        chroot $rootmnt "hostnamectl --static set-hostname $HOSTNAME"
    """

    gateway = """
        sed -i 's/__'${DEVICE}'_GATEWAY__/'$GATEWAY'/' $rootmnt/etc/netplan/99_config.yaml
        # $METRIC

    """

    dns = """
        sed -i 's/__'${DEVICE}'__SEARCH__/'$SEARCH'/' $rootmnt/etc/netplan/99_config.yaml
        sed -i 's/__'${DEVICE}'__NAMESERVER__/'$NAMESERVER'/' $rootmnt/etc/netplan/99_config.yaml
        cd $rootmnt
        echo "search $SEARCH" > /etc/resolv.conf
        echo "nameserver $NAMESERVER" >> /etc/resolv.conf
        cd -
        chroot $rootmnt netplan apply
    """

    ntp = """
        cd $rootmnt
        echo "server  $NTPSERVER" > etc/ntp.conf
        echo "fudge   $NTPSERVER stratum 10" >> etc/ntp.conf
        echo "driftfile /etc/ntp/drift" >> etc/ntp.conf
        cd -
    """

