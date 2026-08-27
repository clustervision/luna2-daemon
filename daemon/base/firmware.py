
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


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is what an operator does with the firmware catalogue.

The catalogue is desired state per kind of hardware, so its entries are written by
hand rather than grabbed from a machine - which is the opposite of a BIOS
configuration and the reason this carries an add where biosconfig deliberately does
not. Nothing is derived from a node here; a node only ever selects an entry.

The preview is the point of the read side. 'What would this do to my group' has an
answer that costs nothing and contacts nothing, because every input is stored
inventory - so an operator can ask it about four thousand nodes before deciding, and
get it for a rack that is powered off.
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
from utils.firmware import FirmwareCatalog


class Firmware():
    """
    This class is responsible for all operations on the firmware catalogue.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'firmwarecatalog'
        self.table_cap = 'Firmware catalogue entry'


    def get_all_firmware(self):
        """
        This method will return every entry in the catalogue.
        """
        records = Database().get_record(table=self.table, where=None)
        if not records:
            return False, 'No firmware catalogue entry is available'
        response = {'config': {self.table: {}}}
        for record in records:
            response['config'][self.table][record['name']] = self.detail(record)
        return True, response


    def get_firmware(self, name=None):
        """
        This method will return one catalogue entry.
        """
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not record:
            return False, f'{self.table_cap} {name} is not available'
        return True, {'config': {self.table: {name: self.detail(record[0])}}}


    def detail(self, record=None):
        """
        This method renders one entry for a caller, without its row id.
        """
        detail = {key: value for key, value in (record or {}).items() if key != 'id'}
        detail['name'] = (record or {}).get('name')
        return detail


    def update_firmware(self, name=None, request_data=None):
        """
        This method will create or change one catalogue entry.

        An entry says which version a kind of hardware should run, so the three
        things that make it addressable - the hardware it is for, the component it
        updates, and the version - are required at creation. An entry missing any
        of them cannot select a node, and an entry that cannot select a node is a
        row nobody will ever notice is wrong.
        """
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        try:
            data = request_data['config'][self.table][name]
        except (KeyError, TypeError):
            return False, 'Invalid request: Did not receive data'
        data['name'] = name
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not record:
            missing = [field for field in ('manufacturer', 'model', 'component', 'version')
                       if not data.get(field)]
            if missing:
                return False, (f'Invalid request: a new {self.table} entry needs '
                               f'{", ".join(missing)}')
            row = Helper().make_rows(data)
            if not Database().insert(self.table, row):
                return False, f'Internal error: {self.table_cap} {name} create failed'
            return True, f'{self.table_cap} {name} created'
        del data['name']
        if not data:
            return False, 'Nothing to update'
        Database().update(self.table, Helper().make_rows(data),
                          [{"column": "id", "value": record[0]['id']}])
        return True, f'{self.table_cap} {name} updated'


    def delete_firmware(self, name=None):
        """
        This method will delete one catalogue entry.
        """
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not record:
            return False, f'{self.table_cap} {name} is not available'
        Database().delete_row(self.table, [{"column": "id", "value": record[0]['id']}])
        return True, f'{self.table_cap} {name} removed'


    def preview(self, object_type=None, name=None):
        """
        This method answers what a firmware push would do, without doing any of it.

        Contacts nothing. Every input is stored inventory, so this is answerable for
        a node that is switched off and affordable for a whole cluster - which is
        what makes it worth asking before a push rather than after.
        """
        status, targets = self.targets(object_type=object_type, name=name)
        if not status:
            return False, targets
        answer = FirmwareCatalog().preview(nodenames=targets)
        return True, {'config': {'firmware': {'preview': answer}}}


    def targets(self, object_type=None, name=None):
        """
        This method resolves what a request was aimed at into a list of node names.

        A group is expanded here, at the edge, rather than carried into the queue as
        a group: the members are read now, so a node added to the group after the
        operator looked is not silently included in something they did not see.
        """
        if object_type == 'group':
            # 'group' is a reserved SQL word, so a where clause naming it is a
            # syntax error that the daemon logs and swallows - leaving the caller
            # an empty result, and a group that exists reported as having no nodes
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if not group:
                return False, f'group {name} does not exist'
            nodes = Database().get_record(table='node',
                                          where=f"groupid = \"{group[0]['id']}\"")
            if not nodes:
                return False, f'group {name} has no nodes'
            return True, [node['name'] for node in nodes]
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return False, f'node {name} does not exist'
        return True, [name]
