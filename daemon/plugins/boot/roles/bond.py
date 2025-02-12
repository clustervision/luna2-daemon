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
This the default localdisk/grub plugin. It provides info for local install

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
    Class for a role.
    
    This plugin needs a mandatory variable set for template functionality
    -- script   --> This code will be called through the unit/systemd
                    The content will be written to /usr/local/roles/<role name>
    -- unit     --> This part provides the systemd unit or service file

    Below fetches the IP address from the active/BOOTIF interface and makes a
    bond out of it. This might not work out of the box in your case, so edit
    the below before proceeding.
    """

    script = """
#!/bin/bash
echo "Login node bond role" | logger
IPADDR=$(ip a show dev enp1s0f0np0|grep -oE "inet [0-9\.\/]+"|grep -oE "[0-9\.\/]+")
if [ "$IPADDR" ]; then
  echo "Bond IP [$IPADDR]" | logger
  nmcli con down enp1s0f0np0
  nmcli con down enp1s0f1np1
  nmcli con add type bond con-name nm-bond ifname nm-bond mode balance-rr ip4 $IPADDR
  nmcli con add type bond-slave ifname enp1s0f0np0 master nm-bond
  nmcli con add type bond-slave ifname enp1s0f1np1 master nm-bond
  nmcli con up bond-slave-enp1s0f0np0
  nmcli con up bond-slave-enp1s0f1np1
  nmcli con up nm-bond
else
  echo "No IP for bond found" | logger
fi
    """

    unit = """
[Unit]
Description=Luna Bonding interfaces
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/roles/__LUNA_ROLE__

[Install]
WantedBy=multi-user.target
    """

