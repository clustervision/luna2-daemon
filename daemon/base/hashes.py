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
Hashes Class, which serves the checksums this controller holds for its own
artefacts.

Read-only on purpose. A row is written where the artefact is produced or pulled,
never by a caller telling us what our file ought to hash to - that would be
taking another machine's word for our own bytes, which is the opposite of what
the table is for.

Not replicated: see utils/hashes.py for why, and for the reason the table is
absent from Tables().tables.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.database import Database


class Hashes():
    """Class for serving the local artefact checksums"""

    def __init__(self):
        self.logger = Log.get_logger()
        self.table = 'hash'
        self.table_cap = 'Hash'


    def get_hashes(self, object_type=None, name=None):
        """
        Every hash this controller holds, optionally narrowed to one object kind
        or one named object.
        """
        where = None
        if object_type and name:
            where = f"object='{object_type}' AND name='{name}'"
        elif object_type:
            where = f"object='{object_type}'"
        records = Database().get_record(table=self.table, where=where)
        if not records:
            return False, f'No {self.table_cap} is available'
        response = {'config': {self.table: {}}}
        for record in records:
            obj = response['config'][self.table].setdefault(record['object'], {})
            item = obj.setdefault(record['name'], {})
            item[record['file']] = {'hash': record['hash'],
                                    'hashtype': record['hashtype'],
                                    'created': record['created']}
        return True, response


    def get_hash(self, object_type=None, name=None, file=None):
        """
        The hash of one artefact. Absent is a normal answer, not an error
        condition: it means this controller cannot vouch for that file, and every
        caller treats that the same as an artefact that predates hashing.
        """
        records = Database().get_record(
            table=self.table,
            where=f"object='{object_type}' AND name='{name}' AND file='{file}'")
        if not records:
            return False, f'No hash recorded for {object_type} {name} {file}'
        record = records[0]
        response = {'config': {self.table: {object_type: {name: {file: {
            'hash': record['hash'],
            'hashtype': record['hashtype'],
            'created': record['created']}}}}}}
        return True, response
