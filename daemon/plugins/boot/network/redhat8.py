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

    # ------------ INIT --------------

    init = """
cat << EOF > /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[connection]
id=Connection_${DEVICE}
type=${TYPE}
interface-name=${DEVICE}
autoconnect=true
zone=${ZONE}

EOF

if [ "$TYPE" == "vlan" ]; then
    PARENT=$DEVICE
    if [ "$VLANPARENT" ]; then
        PARENT=$VLANPARENT
    fi
    cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[vlan]
interface-name=${DEVICE}
id=${VLANID}
parent=${PARENT}

EOF
else
    if [ "$NETWORKTYPE" == "infiniband" ]; then
        cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[infiniband]
#mtu=65520
#transport-mode=connected
transport-mode=datagram

EOF
    else
        cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ethernet]

EOF
    fi
fi

cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[proxy]

$OPTIONS

EOF
chown root:root /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
chmod 600 /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

    # ------------ ipv4 --------------

    interface = """
    if [ "$TYPE" != "slave" ]; then
        if [ "$IPADDR" == "dhcp" ]; then
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv4]
method=auto
dns=
dns-search=
#route1=

EOF
    else
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv4]
method=manual
address1=$IPADDR/$PREFIX
dns=
dns-search=
#route1=

EOF
        fi
    fi
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
        sed -i 's/^dns=$/dns='$NAMESERVER'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        sed -i 's/^dns-search=$/dns-search='$SEARCH'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

    # ------------ ipv6 --------------

    interface_ipv6 = """
    if [ "$TYPE" != "slave" ]; then
        if [ "$IPADDR" == "dhcp" ]; then
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv6]
dns=
dns-search=
method=auto
#route1=

EOF
    elif [ "$IPADDR" == "linklocal" ]; then
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv6]
method=ignore

EOF
    else
cat << EOF >> /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
[ipv6]
address1=$IPADDR/$PREFIX
dns=
dns-search=
method=manual
#route1=

EOF
        fi
    fi
    """

    gateway_ipv6 = """
        if [ "$GATEWAY" ]; then
            sed -i 's%^#route1=%route1=0.0.0.0/0,'$GATEWAY','$METRIC'%' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        fi
    """

    dns_ipv6 = """
        sed -i 's/^dns=$/dns='$NAMESERVER'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
        sed -i 's/^dns-search=$/dns-search='$SEARCH'/' /sysroot/etc/NetworkManager/system-connections/Connection_${DEVICE}.nmconnection
    """

