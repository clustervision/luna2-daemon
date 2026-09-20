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
User Class will handle all Luna user operations: the identities that hold a token.
Not to be confused with OS users, which are the cluster's accounts managed by obol.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import hashlib
import hmac
from os import urandom
from datetime import datetime
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from common.constant import CONSTANT


class User():
    """
    This class is responsible for all operations for Luna users.
    """

    DIGEST = 'pbkdf2_sha256'
    ITERATIONS = 200000

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.user_items = {
            'source': 'local',
            'enabled': True,
            'admin': False,
            'delegate': False
        }
        self.flags = ['enabled', 'admin', 'delegate']
        self.fields = ['newusername', 'password', 'source', 'external_id', 'createdby'] + self.flags


    def get_user(self, name=None):
        """
        This method will return one user, or all of them. A password is never returned;
        the response says whether one is set.
        """
        status = False
        response = f'User {name} is not available' if name else 'No users available'
        where = f"username = '{name}'" if name else None
        users = Database().get_record(table='user', where=where)
        if users:
            memberships = self.memberships()
            config = {}
            for user in users:
                entry = {'source': user['source'], 'external_id': user['external_id'],
                         'password_set': bool(user['password']), 'lastlogin': user['lastlogin'],
                         'created': user['created'], 'createdby': self.username_by_id(user['createdby'])}
                for flag in self.flags:
                    entry[flag] = Helper().make_bool(user[flag])
                entry['usergroups'] = memberships.get(user['id'], {})
                config[user['username']] = entry
            response = {'config': {'user': dict(sorted(config.items()))}}
            status = True
        return status, response


    def update_user(self, name=None, request_data=None):
        """
        This method will create or update a user. A password in the request is stored
        as a digest; an empty password removes the digest, so the user authenticates
        through another source or not at all.
        """
        data = {}
        try:
            data = dict(request_data['config']['user'][name])
        except (KeyError, TypeError):
            return False, 'Invalid request: user data is needed'
        unknown = [key for key in data if key not in self.fields]
        if unknown:
            return False, f"Invalid request: unknown field {', '.join(sorted(unknown))}"
        existing = Database().get_record(table='user', where=f"username = '{name}'")
        create = not existing
        if create:
            data['username'] = name
            data['created'] = 'NOW'
            for key, value in self.user_items.items():
                data.setdefault(key, value)
            data.setdefault('createdby', 0)
        else:
            data.pop('createdby', None)
            if 'source' in data and data['source'] != existing[0]['source']:
                return False, 'Invalid request: the source of a user cannot change'
        if 'newusername' in data:
            if create:
                return False, 'Invalid request: newusername needs an existing user'
            data['username'] = data.pop('newusername')
            clash = Database().get_record(table='user', where=f"username = '{data['username']}'")
            if clash:
                return False, f"Invalid request: user {data['username']} already exists"
        if 'password' in data:
            data['password'] = self.digest(data['password']) if data['password'] else None
        for flag in self.flags:
            if flag in data:
                data[flag] = Helper().bool_to_string(data[flag])
        row = Helper().make_rows(data)
        if create:
            userid = Database().insert('user', row)
            if not userid:
                return False, f'Could not create user {name}'
            return True, f'User {name} created.'
        Database().update('user', row, [{'column': 'id', 'value': existing[0]['id']}])
        return True, f'User {name} updated.'


    def delete_user(self, name=None):
        """
        This method will delete a user and its memberships.
        """
        existing = Database().get_record(table='user', where=f"username = '{name}'")
        if not existing:
            return False, f'User {name} is not available'
        Database().delete_row('usergroupmember', [{'column': 'userid', 'value': existing[0]['id']}])
        Database().delete_row('user', [{'column': 'id', 'value': existing[0]['id']}])
        return True, f'User {name} removed.'


    def login_identity(self, source=None, identity=None):
        """
        This method turns what an authentication source answered into a Luna user: the row
        is found by the source's stable id, else by a name rootus created ahead for that
        source, else created. The source's group names become memberships through the map
        for that source, replacing what that source wrote before; local memberships stay.
        Output - the user's id and a message, or None and the reason.
        """
        if not identity or not identity.get('name'):
            return None, 'Invalid request: an identity is needed'
        name = identity['name']
        external_id = identity.get('external_id') or name
        rows = Database().get_record(table='user', where=f"username = '{name}'")
        if source == 'local':
            if not rows:
                return None, f'User {name} does not exist'
            user = rows[0]
        else:
            claimed = Database().get_record(table='user', where=f"source = '{source}' AND external_id = '{external_id}'")
            if claimed:
                user = claimed[0]
            elif rows and rows[0]['source'] == source:
                user = rows[0]
                Database().update('user', Helper().make_rows({'external_id': external_id}),
                                  [{'column': 'id', 'value': user['id']}])
            elif rows:
                return None, (f"User {name} exists with source {rows[0]['source']} and cannot log in "
                              f"through {source}; remove it or give it a Luna password")
            else:
                data = dict(self.user_items, username=name, source=source, external_id=external_id,
                            created='NOW', createdby=0)
                for flag in self.flags:
                    data[flag] = Helper().bool_to_string(data[flag])
                userid = Database().insert('user', Helper().make_rows(data))
                if not userid:
                    return None, f'Could not create user {name} from source {source}'
                self.logger.info(f"user {name} created on first login through {source}, id {external_id}")
                user = Database().get_record(table='user', where=f"id = '{userid}'")[0]
        if not Helper().make_bool(user['enabled']):
            return None, f'User {name} is disabled'
        if source != 'local':
            self.write_memberships(user['id'], source, identity.get('groups') or [])
        stamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        Database().update('user', Helper().make_rows({'lastlogin': stamp}),
                          [{'column': 'id', 'value': user['id']}])
        return user['id'], f'User {name} authenticated through {source}'


    def write_memberships(self, userid=None, source=None, groups=None):
        """
        This method replaces the memberships a source gave a user with what it says now,
        through the map rows for that source. Memberships from other sources are untouched.
        """
        mapped = {}
        for row in Database().get_record(table='usergroupmap', where=f"source = '{source}'") or []:
            mapped[row['external_group']] = (row['usergroupid'], row['role'])
        wanted = {}
        for group in groups:
            if group in mapped:
                usergroupid, role = mapped[group]
                wanted[usergroupid] = role
            else:
                self.logger.info(f"group {group} of source {source} is not mapped; it grants nothing")
        Database().delete_row('usergroupmember', [{'column': 'userid', 'value': userid},
                                                  {'column': 'source', 'value': source}])
        for usergroupid, role in wanted.items():
            Database().insert('usergroupmember', Helper().make_rows(
                {'userid': userid, 'usergroupid': usergroupid, 'role': role, 'source': source}))


    def whoami(self, userid=None):
        """
        This method answers who a token belongs to: name, id, source, the admin flag and the
        usergroups with the role held in each. Id 0 is the configuration-file account.
        A row that is gone or disabled is refused, so a stale token learns it here.
        """
        if userid in (0, '0'):
            return True, {'user': CONSTANT['API']['USERNAME'], 'id': 0, 'source': 'ini',
                          'admin': True, 'usergroups': {}, 'hardware': []}
        users = Database().get_record(table='user', where=f"id = '{userid}'")
        if not users:
            return False, f'User {userid} no longer exists'
        user = users[0]
        if not Helper().make_bool(user['enabled']):
            return False, f"User {user['username']} is disabled"
        usergroups = self.memberships().get(user['id'], {})
        hardware = [row['name'] for row in Database().get_record(table='usergroup', where="hardware = '1'") or []
                    if row['name'] in usergroups]
        return True, {'user': user['username'], 'id': user['id'], 'source': user['source'],
                      'admin': Helper().make_bool(user['admin']),
                      'usergroups': usergroups, 'hardware': hardware}


    def digest(self, password=None):
        """
        Input - a password
        Output - a salted digest, self-describing so the parameters can change later.
        """
        salt = urandom(16)
        derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, self.ITERATIONS)
        return f'{self.DIGEST}${self.ITERATIONS}${salt.hex()}${derived.hex()}'


    def verify(self, password=None, stored=None):
        """
        Input - a password and a digest as stored by digest()
        Output - True when they match.
        """
        try:
            algorithm, iterations, salt, expected = stored.split('$')
            if algorithm != self.DIGEST:
                return False
            derived = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
        except (AttributeError, ValueError):
            return False
        return hmac.compare_digest(derived.hex(), expected)


    def memberships(self):
        """
        Output - every membership, as {userid: {usergroup name: role}}.
        """
        result = {}
        rows = Database().get_record_join(
            ['usergroupmember.userid', 'usergroupmember.role', 'usergroup.name AS usergroup'],
            ['usergroupmember.usergroupid=usergroup.id'])
        for row in rows or []:
            result.setdefault(row['userid'], {})[row['usergroup']] = row['role']
        return result


    def username_by_id(self, userid=None):
        """
        Input - a user id; 0 is the account from the configuration file.
        Output - the username, or None.
        """
        if userid in (0, '0'):
            return CONSTANT['API']['USERNAME']
        if userid is None:
            return None
        users = Database().get_record(table='user', where=f"id = '{userid}'")
        return users[0]['username'] if users else None
