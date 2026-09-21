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
Authentication source: the controller's operating system through PAM.
On a TrinityX controller that reaches the cluster's own directory through sssd, so
local plus pam covers the cluster's people with no directory settings in Luna.
The identity comes from the name service: the uid is the stable id, the OS group
list the groups. The daemon runs as root, so the PAM conversation works directly.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import pwd
import grp
from common.constant import CONSTANT


class Plugin():
    """
    This class is the PAM authentication source. See the README beside it.
    """

    def __init__(self):
        # python-pam is a pure Python package on top of libpam; imported here so a
        # controller without it fails this source loudly and nothing else.
        import pam
        self.pam = pam
        self.service = CONSTANT.get('AUTH_PAM', {}).get('SERVICE') or 'login'

    def authenticate(self, name=None, password=None):
        """
        A name the name service does not know is not-known. A known name with a wrong
        password is refused and the chain stops: the OS is the authority on its users.
        """
        entry = self._passwd(name)
        if entry is None:
            return None, f'{name} is not a user of this system'
        conversation = self.pam.pam()
        if not conversation.authenticate(name, password, service=self.service):
            return False, f'PAM refused user {name}: {conversation.reason}'
        return True, self._identity(entry)

    def resolve(self, name=None):
        """
        Without a credential only an account that could log in itself is known: a system
        account has no password and never gets past a login, so it must not get past a
        delegation either.
        """
        entry = self._passwd(name)
        if entry is None:
            return False, f'{name} is not a user of this system'
        if not self._can_log_in(entry):
            return False, f'{name} is a system account and cannot be resolved without a credential'
        return True, self._identity(entry)

    def _can_log_in(self, entry):
        """
        A login shell, and a uid at or above the system's first ordinary uid (UID_MIN in
        login.defs, 1000 when absent); root is never resolved this way.
        """
        shell = os.path.basename(getattr(entry, 'pw_shell', '') or '')
        if shell in ('nologin', 'false', ''):
            return False
        uid_min = 1000
        try:
            with open('/etc/login.defs', encoding='utf-8') as handle:
                for line in handle:
                    parts = line.split()
                    if len(parts) == 2 and parts[0] == 'UID_MIN':
                        uid_min = int(parts[1])
        except (OSError, ValueError):
            pass
        return entry.pw_uid >= uid_min

    def _passwd(self, name):
        try:
            return pwd.getpwnam(name)
        except KeyError:
            return None

    def _identity(self, entry):
        gids = os.getgrouplist(entry.pw_name, entry.pw_gid)
        groups = []
        for gid in gids:
            try:
                groups.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                continue
        return {'name': entry.pw_name, 'external_id': str(entry.pw_uid), 'groups': groups}
