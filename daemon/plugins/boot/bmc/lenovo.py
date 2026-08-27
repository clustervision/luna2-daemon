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
Plugin Class :: Lenovo BMC

At boot/install time, prefer Lenovo XClarity Essentials OneCLI when it is
available, and fall back to the generic ipmitool flow otherwise - the same shape
plugins/boot/bmc/dell.py uses for racadm.

The only Lenovo-specific behaviour asserted here is the reason OneCLI is needed
at all: an XClarity Controller ships with IPMI-over-LAN switched off, and its
factory account behind a forced password change on first login. Neither is
reachable over IPMI, so ipmitool cannot bootstrap a fresh XCC into being
remotely controllable on its own. Once OneCLI has turned IPMI-over-LAN on and
provisioned the managed account, everything else - the BMC's network parameters,
and the account as a safety net - is the generic flow, unchanged.

Everything is best effort. Any step that fails clears the readiness flag and the
generic flow below runs exactly as it would have on a machine with no OneCLI at
all, so this plugin can only add behaviour, never remove it.

Nothing site-specific is carried. The working xCAT postscript this was drawn
from also set DNS and NTP servers, a timezone, password policy, boot order and
an operating mode; none of that is Luna's to decide, and this plugin covers only
what default.py and dell.py already cover.

Selected by manufacturer: a Lenovo board reports 'Lenovo', which the boot/bmc
search path normalises to 'lenovo'. Before TRIX-1954 that path was node name,
then group name, then default - so a file like this one could only ever load for
a site that happened to call a node "lenovo".
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from plugins.boot.bmc.default import Plugin as DefaultPlugin


# Runs before the generic flow, because on an XCC the generic flow cannot work
# until IPMI-over-LAN has been switched on.
ONECLI = """
    LENOVO_ONECLI_READY=0
    if command -v onecli >/dev/null 2>&1
    then
        echo "Luna2: OneCLI found, checking whether it can reach the XCC"
        if onecli config show IMM.HostName1 >/dev/null 2>&1
        then
            LENOVO_ONECLI_READY=1
        elif onecli misc bmcpassword --newpwd "${PASSWORD}" -q -u USERID -w PASSW0RD >/dev/null 2>&1
        then
            # The factory account is USERID/PASSW0RD behind a forced change on
            # first login, and nothing else is reachable until that is done. It
            # is only attempted when the read above failed, so an XCC that has
            # already been set up is never touched here.
            echo "Luna2: applied the XCC first-login password change"
            LENOVO_ONECLI_READY=1
        else
            echo "Luna2: OneCLI cannot reach the XCC, leaving it to the generic flow"
        fi

        if [[ "${LENOVO_ONECLI_READY}" == "1" ]]
        then
            echo "Luna2: enabling IPMI over LAN on the XCC"
            onecli misc portctrl ipmilan on >/dev/null 2>&1 || LENOVO_ONECLI_READY=0
        fi

        if [[ "${LENOVO_ONECLI_READY}" == "1" ]]
        then
            echo "Luna2: provisioning BMC user ${USERNAME} in XCC slot ${USERID}"
            onecli config set IMM.LoginId.${USERID} "${USERNAME}" >/dev/null 2>&1 || LENOVO_ONECLI_READY=0
            onecli config set IMM.Password.${USERID} "${PASSWORD}" >/dev/null 2>&1 || LENOVO_ONECLI_READY=0
            onecli config set IMM.LoginRole.${USERID} Administrator >/dev/null 2>&1 || LENOVO_ONECLI_READY=0
            onecli config set IMM.Accessible_Interfaces.${USERID} "Web|SSH|Redfish|IPMI" >/dev/null 2>&1 || LENOVO_ONECLI_READY=0
        fi

        if [[ "${LENOVO_ONECLI_READY}" == "0" ]]
        then
            echo "Luna2: the OneCLI path did not complete; the generic flow follows"
        fi
    fi
"""


class Plugin(DefaultPlugin):
    """
    Lenovo-specific boot-time BMC plugin.

    The generic segment is inherited rather than restated. A vendor file that
    copies it acquires a private fork of the BMC bootstrap, and the copies drift:
    a fix lands in one and the node runs the other. Only what is genuinely Lenovo
    lives here.
    """

    config = ONECLI + DefaultPlugin.config
