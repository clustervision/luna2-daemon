#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
Redfish Setup Class will handle all redfish setup operations.

A redfishsetup says how Luna reaches a BMC over Redfish - the scheme, the port,
whether the certificate is verified - and carries the accounts it logs in with.
It is deliberately not a statement about what the node should look like: a BIOS
profile or a firmware level is a different lifecycle and gets its own table.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from utils.log import Log
from utils.database import Database
from utils.helper import Helper


class RedfishSetup():
    """
    This class is responsible for all operations for redfish setup.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'redfishsetup'
        self.table_cap = 'Redfish Setup'


    def _setup_with_accounts(self, setup=None):
        """
        One redfishsetup row plus its accounts, in response shape.
        """
        detail = {
            # the name is the key of the dict this lands in, and it is also a field
            # of the record. Both, deliberately: the generic CLI list renderer looks
            # the columns up inside the record and prints --NA-- for anything it
            # cannot find there, so a response carrying the name only as a key
            # renders a table with no names in it.
            'name': setup['name'],
            'scheme': setup['scheme'] or 'https',
            'port': setup['port'],
            'verify': Helper().make_bool(setup['verify']),
            'comment': setup['comment'],
            'accounts': []
        }
        where = f'redfishsetupid = "{setup["id"]}"'
        for record in Database().get_record(table='redfishaccount', where=where) or []:
            del record['id']
            del record['redfishsetupid']
            detail['accounts'].append(record)
        return detail


    def get_all_redfishsetup(self):
        """
        This method will return all the redfishsetup in detailed format.
        """
        status = False
        setups = Database().get_record(table=self.table)
        if setups:
            response = {'config': {self.table: {}}}
            for setup in setups:
                response['config'][self.table][setup['name']] = self._setup_with_accounts(setup)
            status = True
        else:
            self.logger.warning(f'No {self.table_cap} is available.')
            response = f'No {self.table_cap} is available'
        return status, response


    def get_redfishsetup(self, name=None):
        """
        This method will return requested redfishsetup in detailed format.
        """
        status = False
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if setup:
            response = {'config': {self.table: {name: self._setup_with_accounts(setup[0])}}}
            status = True
        else:
            response = f'{self.table_cap} {name} is not available'
        return status, response


    def get_redfishsetup_member(self, name=None):
        """
        This method will return the nodes and groups pointing at a redfishsetup.
        """
        status = False
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not setup:
            return status, f'{self.table_cap} {name} is not available'
        members = self.assigned_to(name)
        if members:
            response = {'config': {self.table: {name: {'members': members}}}}
            status = True
        else:
            response = f'{self.table_cap} {name} does not have any member'
        return status, response


    def assigned_to(self, name=None):
        """
        This method will list every node and group pointing at a redfishsetup.
        """
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not setup:
            return []
        setupid = setup[0]['id']
        assigned = []
        for table in ['node', 'group']:
            records = Database().get_record(table=table, where=f'redfishsetupid = "{setupid}"')
            for record in records or []:
                assigned.append(f"{table} {record['name']}")
        return assigned


    def _validate(self, data=None):
        """
        This method will check the fields the shared input validator deliberately
        does not.

        port is not in MATCH because that map is keyed on the bare field name and
        applies daemon-wide - tracker already has a port, fed by torrent clients,
        and registering it would tighten an existing endpoint as a side effect.
        verify is a boolean, and booleans are coerced here in this daemon rather
        than pattern-matched.
        """
        if 'port' in data and str(data['port']) not in ('', 'None'):
            port = str(data['port'])
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                return False, 'Invalid request: port must be a number between 1 and 65535'
        if 'verify' in data:
            data['verify'] = str(Helper().bool_to_string(data['verify']))
        return True, data


    def update_redfishsetup(self, name=None, request_data=None):
        """
        This method will create or update a redfishsetup and its accounts.

        Accounts present in the request are created or updated by name; accounts
        not named are left as they are - removal goes through
        delete_redfishsetup_account.
        """
        status = False
        response = 'Internal error'
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        data = request_data['config'][self.table][name]
        accounts = data.pop('accounts', None)
        # popped before the column check: it is a request about the name, not a
        # column of its own, exactly as the other entities take theirs
        newname = data.pop('newredfishsetupname', None)
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        setup_columns = Database().get_columns(self.table)
        if not Helper().compare_list(data, setup_columns):
            return False, 'Invalid request: Supplied columns do not match the requirements'
        valid, data = self._validate(data)
        if not valid:
            return False, data
        if newname:
            if not setup:
                return False, f'{self.table_cap} {name} is not available'
            if Database().get_record(table=self.table, where=f'name = "{newname}"'):
                return False, f'Invalid request: {newname} already present in database'
            data['name'] = newname
        if setup:
            setupid = setup[0]['id']
            if data:
                Database().update(self.table, Helper().make_rows(data),
                                  [{"column": "id", "value": setupid}])
            response = f'{self.table_cap} {name} updated'
            if newname:
                # nothing else to do: node and group hold the id, so everything
                # pointing at this setup keeps pointing at it
                name = newname
                response = f'{self.table_cap} renamed to {newname}'
        else:
            data['name'] = name
            if 'scheme' not in data or not data['scheme']:
                data['scheme'] = 'https'
            setupid = Database().insert(self.table, Helper().make_rows(data))
            if not setupid:
                response = f'Internal error: {self.table_cap} {name} create failed'
                self.logger.error(response)
                return False, response
            response = f'{self.table_cap} {name} created'
        status = True
        if accounts:
            valid, message = self._write_accounts(setupid=setupid, accounts=accounts)
            if not valid:
                return False, message
        return status, response


    def _write_accounts(self, setupid=None, accounts=None):
        """
        This method will create or update the accounts under a redfishsetup.
        """
        account_columns = Database().get_columns('redfishaccount')
        for entry in accounts:
            if 'name' not in entry.keys():
                return False, 'Invalid request: account information not complete, name is required'
            if not Helper().compare_list(entry, account_columns):
                return False, 'Invalid request: Supplied account columns do not match the requirements'
            account_name = entry['name']
            where = f'redfishsetupid = "{setupid}" AND name = "{account_name}"'
            existing = Database().get_record(table='redfishaccount', where=where)
            # a change carries only what is changing: 'give this account the Operator
            # role' says nothing about its password, and demanding one would make the
            # caller send the password back to leave it alone
            if not existing:
                for item in ['username', 'password']:
                    if not entry.get(item):
                        return False, (f'Invalid request: account information not complete, '
                                       f'{item} is required')
            if existing:
                where = [
                    {"column": "redfishsetupid", "value": setupid},
                    {"column": "name", "value": account_name}
                ]
                Database().update('redfishaccount', Helper().make_rows(entry), where)
            else:
                entry['redfishsetupid'] = setupid
                Database().insert('redfishaccount', Helper().make_rows(entry))
        return True, 'accounts written'


    def clone_redfishsetup(self, name=None, request_data=None):
        """
        This method will clone a redfishsetup including its accounts.
        """
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        data = request_data['config'][self.table][name]
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not setup:
            return False, f'{self.table_cap} {name} is not available'
        if 'newredfishsetupname' not in data:
            return False, 'Invalid request: New redfishsetup name not provided'
        newname = data['newredfishsetupname']
        if Database().get_record(table=self.table, where=f'name = "{newname}"'):
            return False, f'Invalid request: {self.table_cap} {newname} already present'
        setupid = setup[0]['id']
        newsetup = dict(setup[0])
        del newsetup['id']
        newsetup['name'] = newname
        new_setupid = Database().insert(self.table, Helper().make_rows(newsetup))
        where = f'redfishsetupid = "{setupid}"'
        for record in Database().get_record(table='redfishaccount', where=where) or []:
            del record['id']
            record['redfishsetupid'] = new_setupid
            Database().insert('redfishaccount', Helper().make_rows(record))
        return True, f'{self.table_cap} {name} cloned to {newname}'


    def delete_redfishsetup(self, name=None):
        """
        This method will delete a redfishsetup and its accounts.
        """
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not setup:
            return False, f'{self.table_cap} {name} is not available'
        inuse = self.assigned_to(name)
        if inuse:
            listed = ', '.join(inuse[:10])
            more = ' ...' if len(inuse) > 10 else ''
            return False, (f'Invalid request: {self.table_cap} {name} is currently in use by '
                           f'{listed}{more}')
        setupid = setup[0]['id']
        Database().delete_row('redfishaccount', [{"column": "redfishsetupid", "value": setupid}])
        Database().delete_row(self.table, [{"column": "id", "value": setupid}])
        return True, f'{self.table_cap} {name} removed'


    def delete_redfishsetup_account(self, name=None, account=None):
        """
        This method will delete one account of a redfishsetup.
        """
        setup = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not setup:
            return False, f'{self.table_cap} {name} is not available'
        setupid = setup[0]['id']
        where = f'redfishsetupid = "{setupid}" AND name = "{account}"'
        if not Database().get_record(table='redfishaccount', where=where):
            return False, f'Account {account} is unavailable for {self.table_cap} {name}'
        Database().delete_row('redfishaccount', [
            {"column": "redfishsetupid", "value": setupid},
            {"column": "name", "value": account}
        ])
        return True, f'Account {account} deleted from {self.table_cap} {name}'
