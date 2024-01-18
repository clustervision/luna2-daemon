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
cat << EOF > /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[connection]
id=Connection_${DEVICE}
type=${TYPE}
interface-name=${DEVICE}
autoconnect=true
zone=${ZONE}

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
#route1=

[ipv6]
addr-gen-mode=default
method=auto

[proxy]

$OPTIONS
EOF
chown root:root /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
chmod 600 /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection

    """

    hostname = """
        echo "$HOSTNAME" > /proc/sys/kernel/hostname
        chroot /sysroot hostnamectl --static set-hostname $HOSTNAME 2> /dev/null
    """

    gateway = """
        if [ "$GATEWAY" ]; then
            sed -i 's%^#route1=%route1=0.0.0.0/0,'$GATEWAY','$METRIC'%' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        fi
    """

    dns = """
        SEARCH=$(echo $SEARCH | sed -e 's/,/;/g')
        sed -i 's/^dns=/dns='$NAMESERVER'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        sed -i 's/^dns-search=/dns-search='$SEARCH'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

