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
Authentication source: a directory, for sites whose directory is not wired into the
controller, or that want groups from directory attributes. FreeIPA and Active Directory
are this source with other attribute names. Settings in the daemon ini:

    [AUTH_LDAP]
    URI = ldaps://ldap.example.com
    BASE = ou=people,dc=example,dc=com
    BIND_DN =                         ; optional, for the search; empty means anonymous
    BIND_PASSWORD =
    USER_ATTRIBUTE = uid              ; sAMAccountName on Active Directory
    ID_ATTRIBUTE = entryUUID          ; objectGUID on Active Directory, or uidNumber
    GROUP_ATTRIBUTE = memberOf

The person's own bind with the found DN is the credential check; the identity is the id
attribute and the group attribute of the entry.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from common.constant import CONSTANT


class Plugin():
    """
    This class is the directory authentication source. See the README beside it.
    """

    def __init__(self):
        # ldap3 is a pure Python package; imported here so a controller without it
        # fails this source loudly and nothing else.
        import ldap3
        self.ldap3 = ldap3
        settings = CONSTANT.get('AUTH_LDAP', {})
        self.uri = settings.get('URI')
        self.base = settings.get('BASE')
        if not self.uri or not self.base:
            raise ValueError('AUTH_LDAP needs URI and BASE')
        self.bind_dn = settings.get('BIND_DN') or None
        self.bind_password = settings.get('BIND_PASSWORD') or None
        self.user_attribute = settings.get('USER_ATTRIBUTE') or 'uid'
        self.id_attribute = settings.get('ID_ATTRIBUTE') or 'entryUUID'
        self.group_attribute = settings.get('GROUP_ATTRIBUTE') or 'memberOf'

    def authenticate(self, name=None, password=None):
        """
        An entry the search does not find is not-known. A found entry whose own bind
        fails is refused and the chain stops.
        """
        entry = self._search(name)
        if entry is None:
            return None, f'{name} is not in the directory'
        if not password or not self._bind(entry['dn'], password):
            return False, f'The directory refused the password of user {name}'
        return True, self._identity(name, entry)

    def resolve(self, name=None):
        entry = self._search(name)
        if entry is None:
            return False, f'{name} is not in the directory'
        return True, self._identity(name, entry)

    def _connection(self, user=None, password=None):
        server = self.ldap3.Server(self.uri, get_info=self.ldap3.NONE)
        return self.ldap3.Connection(server, user=user, password=password, auto_bind=True,
                                     receive_timeout=10)

    def _search(self, name):
        """
        The name is escaped for the filter, so a directory syntax character in a login
        name searches for that character rather than changing the query.
        """
        safe = self.ldap3.utils.conv.escape_filter_chars(name)
        with self._connection(self.bind_dn, self.bind_password) as connection:
            connection.search(self.base, f'({self.user_attribute}={safe})',
                              attributes=[self.id_attribute, self.group_attribute])
            if not connection.entries:
                return None
            found = connection.entries[0]
            return {'dn': found.entry_dn,
                    'id': self._first(found, self.id_attribute),
                    'groups': self._all(found, self.group_attribute)}

    def _bind(self, dn, password):
        try:
            with self._connection(dn, password):
                return True
        except self.ldap3.core.exceptions.LDAPBindError:
            return False

    def _first(self, found, attribute):
        values = self._all(found, attribute)
        return str(values[0]) if values else None

    def _all(self, found, attribute):
        try:
            return [str(value) for value in found[attribute].values]
        except (KeyError, self.ldap3.core.exceptions.LDAPKeyError):
            return []

    def _identity(self, name, entry):
        return {'name': name, 'external_id': entry['id'] or entry['dn'], 'groups': entry['groups']}
