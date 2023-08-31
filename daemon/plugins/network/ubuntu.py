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

#network:
#  version: 2
#  renderer: networkd
#  ethernets:
#    eth0:
#      addresses:
#        - 10.10.10.2/24
#      routes:
#        - to: default
#          via: 10.10.10.1
#      nameservers:
#          search: [mydomain, otherdomain]
#          addresses: [10.10.10.1, 1.1.1.1]
#
#
#/etc/netplan/99_config.yaml

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
        - $IPADDRESS/$PREFIX
EOF


#        chroot $rootmnt "nmcli connection add con-name Connection_$DEVICE ifname $DEVICE type ethernet"
#        #chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.addresses $IPADDRESS/$PREFIX"
#        chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.addresses $IPADDRESS/$NETMASK"
#        chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.method manual"
        #$ZONE
        #$OPTIONS
    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        chroot $rootmnt "hostnamectl --static set-hostname $HOSTNAME"
    """

    gateway = """
#        chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.gateway $GATEWAY"
#        chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.route-metric $METRIC"
    """

    dns = """
#        chroot $rootmnt "nmcli connection modify Connection_$DEVICE ipv4.dns $NAMESERVER ipv4.dns-search $SEARCH"
        cd $rootmnt
        echo "search $SEARCH" > /etc/resolv.conf
        echo "nameserver $NAMESERVER" >> /etc/resolv.conf
        cd -
    """

    ntp = """
        cd $rootmnt
        echo "server  $NTPSERVER" > etc/ntp.conf
        echo "fudge   $NTPSERVER stratum 10" >> etc/ntp.conf
        echo "driftfile /etc/ntp/drift" >> etc/ntp.conf
        cd -
    """

