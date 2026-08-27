#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
Plugin Class :: HPE BMC

At boot/install time, prefer hponcfg when it is available, and fall back to the
generic ipmitool flow otherwise - the same shape plugins/boot/bmc/dell.py uses
for racadm and lenovo.py for OneCLI.

The only HPE-specific behaviour asserted here is the reason hponcfg is needed at
all: iLO ships with IPMI/DCMI-over-LAN switched off, so ipmitool cannot reach a
fresh iLO over the network at all. hponcfg talks to iLO in band through the hpilo
driver rather than over the network, which is exactly why it can turn the network
path on. Once it has, the BMC's network parameters and the managed account are
the generic flow, unchanged.

hponcfg is driven by RIBCL rather than by key/value arguments, so this reads the
current configuration back to prove it can talk to iLO, writes the smallest
RIBCL document that turns IPMI-over-LAN on, applies it, and removes the file. The
document is written with restrictive permissions and deleted afterwards because
RIBCL requires a LOGIN element.

Everything is best effort. Any step that fails clears the readiness flag and the
generic flow below runs exactly as it would have on a machine with no hponcfg, so
this plugin can only add behaviour, never remove it.

Deliberately not carried from the working xCAT postscript this was drawn from:
its RIBCL also pinned the network settings, the shared-port selection and the
HTTP/HTTPS ports, and it loaded a per-model conrep BIOS file from a site path.
Network configuration is the generic flow's job once IPMI-over-LAN is on, and the
rest is site policy.

Selected by manufacturer. Which token that is depends on what the board reports:
modern machines say 'HPE', older ones 'HP', and some report the full company
name. hp.py and hewlett.py sit beside this file for those, and say so.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from plugins.boot.bmc.default import Plugin as DefaultPlugin


# Runs before the generic flow, because on an iLO the generic flow cannot reach
# the BMC over the network until IPMI/DCMI-over-LAN has been switched on.
HPONCFG = """
    HPE_HPONCFG_READY=0
    modprobe hpilo >/dev/null 2>&1 || true
    if command -v hponcfg >/dev/null 2>&1
    then
        echo "Luna2: hponcfg found, checking whether it can reach iLO"
        HPE_RIBCL_READ="$(mktemp /tmp/luna-ilo-read.XXXXXX)"
        HPE_RIBCL_SET="$(mktemp /tmp/luna-ilo-set.XXXXXX)"
        chmod 600 "${HPE_RIBCL_READ}" "${HPE_RIBCL_SET}"

        if hponcfg -w "${HPE_RIBCL_READ}" >/dev/null 2>&1
        then
            HPE_HPONCFG_READY=1
        else
            echo "Luna2: hponcfg cannot reach iLO, leaving it to the generic flow"
        fi

        if [[ "${HPE_HPONCFG_READY}" == "1" ]]
        then
            echo "Luna2: enabling IPMI/DCMI over LAN on iLO"
            cat > "${HPE_RIBCL_SET}" <<EOF_LUNA_ILO
<RIBCL VERSION="2.0">
  <LOGIN USER_LOGIN="${USERNAME}" PASSWORD="${PASSWORD}">
    <RIB_INFO MODE="write">
      <MOD_GLOBAL_SETTINGS>
        <IPMI_DCMI_OVER_LAN_ENABLED VALUE="Y"/>
      </MOD_GLOBAL_SETTINGS>
    </RIB_INFO>
  </LOGIN>
</RIBCL>
EOF_LUNA_ILO
            hponcfg -f "${HPE_RIBCL_SET}" >/dev/null 2>&1 || HPE_HPONCFG_READY=0
        fi

        if [[ "${HPE_HPONCFG_READY}" == "1" ]]
        then
            # read it back rather than trusting the exit code: hponcfg reports
            # success for a document iLO accepted and did nothing with
            if hponcfg -w "${HPE_RIBCL_READ}" >/dev/null 2>&1
            then
                if grep -qi 'IPMI_DCMI_OVER_LAN_ENABLED VALUE="Y"' "${HPE_RIBCL_READ}"
                then
                    echo "Luna2: iLO confirms IPMI over LAN is enabled"
                else
                    echo "Luna2: iLO did not report IPMI over LAN as enabled"
                    HPE_HPONCFG_READY=0
                fi
            fi
        fi

        rm -f "${HPE_RIBCL_READ}" "${HPE_RIBCL_SET}"

        if [[ "${HPE_HPONCFG_READY}" == "0" ]]
        then
            echo "Luna2: the hponcfg path did not complete; the generic flow follows"
        fi
    fi
"""


class Plugin(DefaultPlugin):
    """
    HPE-specific boot-time BMC plugin.

    The generic segment is inherited rather than restated, for the same reason
    lenovo.py inherits it: a vendor file that copies it acquires a private fork of
    the BMC bootstrap, and the copies drift.
    """

    config = HPONCFG + DefaultPlugin.config
