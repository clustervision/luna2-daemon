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


    def authenticate(self, username=None, password=None):
        """
        This method verifies a password against the user's stored digest.
        Output - the user's id and a message, or None and the reason.
        """
        users = Database().get_record(table='user', where=f"username = '{username}'")
        if not users:
            return None, f'User {username} does not exist'
        user = users[0]
        if not user['password']:
            return None, f'User {username} has no password in Luna'
        if not self.verify(password, user['password']):
            return None, f'Incorrect password for user {username}'
        if not Helper().make_bool(user['enabled']):
            return None, f'User {username} is disabled'
        stamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        Database().update('user', Helper().make_rows({'lastlogin': stamp}),
                          [{'column': 'id', 'value': user['id']}])
        return user['id'], f'User {username} authenticated'


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
