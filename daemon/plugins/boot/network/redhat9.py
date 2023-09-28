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
cat << EOF > /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[connection]
id=Connection_${DEVICE}
type=${TYPE}
interface-name=${DEVICE}
autoconnect=true

[$TYPE]
EOF

if [ "$TYPE" == "infiniband" ]; then
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
#mtu=65520
#transport-mode=connected
transport-mode=datagram

EOF
fi

cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv4]
address1=$IPADDR/$PREFIX
dns=
dns-search=
method=manual

[ipv6]
addr-gen-mode=default
method=auto

[proxy]
EOF
chown root:root /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
chmod 600 /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection

        #$ZONE
        #$OPTIONS
    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        chroot /sysroot hostnamectl --static set-hostname $HOSTNAME 2> /dev/null
    """

    gateway = """
        GREP=$(grep '^address1' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection)
        sed -i 's%^'$GREP'%'$GREP','$GATEWAY'%' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

    dns = """
        SEARCH=$(echo $SEARCH | sed -e 's/,/;/g')
        sed -i 's/^dns=/dns='$NAMESERVER'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        sed -i 's/^dns-search=/dns-search='$SEARCH'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

    ntp = """
        cd /sysroot
        echo "server  $NTPSERVER" > etc/ntp.conf
        echo "fudge   $NTPSERVER stratum 10" >> etc/ntp.conf
        echo "driftfile /etc/ntp/drift" >> etc/ntp.conf
    """

