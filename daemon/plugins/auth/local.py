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
Authentication source: the daemon's own user table.
A row with a password digest is a Luna login in its own right. A row without one is a
user that authenticates elsewhere, so this source answers not-known and the chain goes on.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from base.user import User


class Plugin():
    """
    This class is the local authentication source. See the README beside it.
    """

    def authenticate(self, name=None, password=None):
        """
        A stored digest decides: verified, or refused and the chain stops. No digest is
        not-known, so another source may claim the name.
        """
        rows = Database().get_record(table='user', where=f"username = '{name}'")
        if not rows or not rows[0]['password']:
            return None, f'{name} has no password in Luna'
        if not User().verify(password, rows[0]['password']):
            return False, f'Incorrect password for user {name}'
        return True, self._identity(rows[0])

    def resolve(self, name=None):
        """
        A local row is known whether or not it holds a digest.
        """
        rows = Database().get_record(table='user', where=f"username = '{name}'")
        if not rows:
            return False, f'User {name} does not exist'
        return True, self._identity(rows[0])

    def _identity(self, row):
        return {'name': row['username'], 'external_id': row['external_id'] or row['username'], 'groups': []}
