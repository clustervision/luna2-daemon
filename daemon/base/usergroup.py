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
UserGroup Class will handle all usergroup operations: the organisations, departments and
teams a Luna user belongs to, the role a user holds in each, and the map that turns a
directory group into a membership. Not to be confused with node groups or OS groups.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.log import Log
from utils.helper import Helper

# The role labels and what each caps the usergroup bits to. Stored as labels;
# fixed here so a row can never carry a role the code does not know.
ROLE_CAPS = {'admin': 'rwx', 'manager': 'rwx', 'operator': 'r-x', 'reader': 'r--'}


class UserGroup():
    """
    This class is responsible for all operations for usergroups, memberships and the map.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.fields = ['newusergroupname', 'comment', 'hardware']


    def get_usergroup(self, name=None):
        """
        This method will return one usergroup with its members, or all of them.
        """
        status = False
        response = f'Usergroup {name} is not available' if name else 'No usergroups available'
        where = f"name = '{name}'" if name else None
        usergroups = Database().get_record(table='usergroup', where=where)
        if usergroups:
            members = self.members()
            config = {}
            for usergroup in usergroups:
                config[usergroup['name']] = {'name': usergroup['name'], 'comment': usergroup['comment'],
                                             'hardware': Helper().make_bool(usergroup['hardware']) is True,
                                             'members': members.get(usergroup['id'], {})}
            response = {'config': {'usergroup': dict(sorted(config.items()))}}
            status = True
        return status, response


    def update_usergroup(self, name=None, request_data=None):
        """
        This method will create or update a usergroup. Members are not part of the body;
        they come one at a time through update_member and remove_member.
        """
        data = {}
        try:
            data = dict(request_data['config']['usergroup'][name])
        except (KeyError, TypeError):
            return False, 'Invalid request: usergroup data is needed'
        unknown = [key for key in data if key not in self.fields]
        if unknown:
            return False, f"Invalid request: unknown field {', '.join(sorted(unknown))}"
        existing = Database().get_record(table='usergroup', where=f"name = '{name}'")
        create = not existing
        if create:
            data['name'] = name
            data.setdefault('hardware', False)
        if 'hardware' in data:
            data['hardware'] = Helper().bool_to_string(data['hardware'])
        if 'newusergroupname' in data:
            if create:
                return False, 'Invalid request: newusergroupname needs an existing usergroup'
            data['name'] = data.pop('newusergroupname')
            clash = Database().get_record(table='usergroup', where=f"name = '{data['name']}'")
            if clash:
                return False, f"Invalid request: usergroup {data['name']} already exists"
        row = Helper().make_rows(data)
        if create:
            if not Database().insert('usergroup', row):
                return False, f'Could not create usergroup {name}'
            return True, f'Usergroup {name} created.'
        Database().update('usergroup', row, [{'column': 'id', 'value': existing[0]['id']}])
        return True, f'Usergroup {name} updated.'


    def delete_usergroup(self, name=None):
        """
        This method will delete a usergroup, its memberships and its map rows.
        """
        existing = Database().get_record(table='usergroup', where=f"name = '{name}'")
        if not existing:
            return False, f'Usergroup {name} is not available'
        where = [{'column': 'usergroupid', 'value': existing[0]['id']}]
        Database().delete_row('usergroupmember', where)
        Database().delete_row('usergroupmap', where)
        Database().delete_row('usergroup', [{'column': 'id', 'value': existing[0]['id']}])
        return True, f'Usergroup {name} removed.'


    def get_members(self, name=None):
        """
        This method will return the members of a usergroup with their roles.
        """
        existing = Database().get_record(table='usergroup', where=f"name = '{name}'")
        if not existing:
            return False, f'Usergroup {name} is not available'
        members = self.members().get(existing[0]['id'], {})
        return True, {'config': {'usergroup': {name: {'members': members}}}}


    def update_member(self, name=None, request_data=None):
        """
        This method adds one user to a usergroup with a role, or changes the role.
        The body names the user and the role.
        """
        data = self._envelope(name, request_data)
        if not data or not data.get('username'):
            return False, 'Invalid request: a username is needed'
        role = data.get('role')
        if role not in ROLE_CAPS:
            return False, f"Invalid request: role must be one of {', '.join(ROLE_CAPS)}"
        usergroup = Database().get_record(table='usergroup', where=f"name = '{name}'")
        if not usergroup:
            return False, f'Usergroup {name} is not available'
        user = Database().get_record(table='user', where=f"username = '{data['username']}'")
        if not user:
            return False, f"User {data['username']} is not available"
        where = f"userid = '{user[0]['id']}' AND usergroupid = '{usergroup[0]['id']}'"
        membership = Database().get_record(table='usergroupmember', where=where)
        row = Helper().make_rows({'userid': user[0]['id'], 'usergroupid': usergroup[0]['id'],
                                  'role': role, 'source': data.get('source', 'local')})
        if membership:
            Database().update('usergroupmember', row, [{'column': 'id', 'value': membership[0]['id']}])
            return True, f"Member {data['username']} of usergroup {name} updated to role {role}."
        Database().insert('usergroupmember', row)
        return True, f"Member {data['username']} added to usergroup {name} as {role}."


    def remove_member(self, name=None, request_data=None):
        """
        This method removes one user from a usergroup. The body names the user.
        """
        data = self._envelope(name, request_data)
        if not data or not data.get('username'):
            return False, 'Invalid request: a username is needed'
        usergroup = Database().get_record(table='usergroup', where=f"name = '{name}'")
        if not usergroup:
            return False, f'Usergroup {name} is not available'
        user = Database().get_record(table='user', where=f"username = '{data['username']}'")
        if not user:
            return False, f"User {data['username']} is not available"
        where = f"userid = '{user[0]['id']}' AND usergroupid = '{usergroup[0]['id']}'"
        membership = Database().get_record(table='usergroupmember', where=where)
        if not membership:
            return False, f"User {data['username']} is not a member of usergroup {name}"
        Database().delete_row('usergroupmember', [{'column': 'id', 'value': membership[0]['id']}])
        return True, f"Member {data['username']} removed from usergroup {name}."


    def get_map(self):
        """
        This method returns every map row: an external group of a source, the usergroup
        it lands in and the role it grants.
        """
        rows = Database().get_record_join(
            ['usergroupmap.source', 'usergroupmap.external_group', 'usergroupmap.role',
             'usergroup.name AS usergroup'],
            ['usergroupmap.usergroupid=usergroup.id'])
        if not rows:
            return False, 'No usergroup map entries available'
        entries = [{'source': row['source'], 'external_group': row['external_group'],
                    'usergroup': row['usergroup'], 'role': row['role']} for row in rows]
        return True, {'config': {'usergroupmap': entries}}


    def update_map(self, request_data=None):
        """
        This method adds one map row or changes the usergroup and role of one.
        The body carries source, external_group, usergroup and role; the first two are the key.
        """
        data, error = self._map_key(request_data)
        if error:
            return False, error
        role = data.get('role')
        if role not in ROLE_CAPS:
            return False, f"Invalid request: role must be one of {', '.join(ROLE_CAPS)}"
        usergroup = Database().get_record(table='usergroup', where=f"name = '{data.get('usergroup')}'")
        if not usergroup:
            return False, f"Usergroup {data.get('usergroup')} is not available"
        where = f"source = '{data['source']}' AND external_group = '{data['external_group']}'"
        entry = Database().get_record(table='usergroupmap', where=where)
        row = Helper().make_rows({'source': data['source'], 'external_group': data['external_group'],
                                  'usergroupid': usergroup[0]['id'], 'role': role})
        if entry:
            Database().update('usergroupmap', row, [{'column': 'id', 'value': entry[0]['id']}])
            return True, f"Map entry {data['source']} {data['external_group']} updated."
        Database().insert('usergroupmap', row)
        return True, f"Map entry {data['source']} {data['external_group']} created."


    def remove_map(self, request_data=None):
        """
        This method removes one map row, named by source and external group.
        """
        data, error = self._map_key(request_data)
        if error:
            return False, error
        where = f"source = '{data['source']}' AND external_group = '{data['external_group']}'"
        entry = Database().get_record(table='usergroupmap', where=where)
        if not entry:
            return False, f"Map entry {data['source']} {data['external_group']} is not available"
        Database().delete_row('usergroupmap', [{'column': 'id', 'value': entry[0]['id']}])
        return True, f"Map entry {data['source']} {data['external_group']} removed."


    def members(self):
        """
        Output - every membership, as {usergroupid: {username: role}}.
        """
        result = {}
        rows = Database().get_record_join(
            ['usergroupmember.usergroupid', 'usergroupmember.role', 'user.username'],
            ['usergroupmember.userid=user.id'])
        for row in rows or []:
            result.setdefault(row['usergroupid'], {})[row['username']] = row['role']
        return result


    def _envelope(self, name=None, request_data=None):
        """
        Output - the body of a request about one usergroup, or None.
        """
        try:
            return request_data['config']['usergroup'][name]
        except (KeyError, TypeError):
            return None


    def _map_key(self, request_data=None):
        """
        Output - the map body and None, or None and the reason it is unusable. The external
        group is a directory name and is not filtered, so a quote in it is refused here.
        """
        try:
            data = request_data['config']['usergroupmap']
        except (KeyError, TypeError):
            return None, 'Invalid request: usergroupmap data is needed'
        if not isinstance(data, dict) or not data.get('source') or not data.get('external_group'):
            return None, 'Invalid request: source and external_group are needed'
        if "'" in data['external_group']:
            return None, 'Invalid request: a quote in external_group is not accepted'
        return data, None
