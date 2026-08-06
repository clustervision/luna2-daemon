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
Checksums for artefacts this controller holds on disk - osimage files today,
other objects later.

The rows are LOCAL and are never replicated. A checksum is an assertion about a
file on this machine, so it legitimately differs between controllers, and that
difference is the whole point: it is what lets a peer tell 'my copy matches
yours' from 'my copy is broken'. Replicating it would copy the master's claim
about the master's file and staple it to a different file.

The table is therefore deliberately absent from Tables().tables - see the
reason recorded in tests/unit/test_backup_tables.py.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import hashlib
from time import strftime, localtime, time
from utils.log import Log
from utils.database import Database
from utils.helper import Helper


class Hashes():
    """Class for recording and looking up checksums of local artefacts"""

    def __init__(self):
        self.logger = Log.get_logger()
        self.hashtype = 'sha256'


    def compute(self, path):
        # chunked: an imagefile is measured in gigabytes and this runs on a
        # controller that may already be short of memory.
        try:
            digest = hashlib.sha256()
            with open(path, 'rb') as handle:
                for chunk in iter(lambda: handle.read(1048576), b''):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError as exp:
            self.logger.error(f"could not hash {path}: {exp}")
        return None


    def record(self, object_type, name, file, path=None, hash_value=None):
        # Either hand over a hash already computed while the bytes were passing,
        # or a path to read. Returns the hash, or None when it could not be had.
        #
        # This must never raise. One caller is build_osimage, where a database
        # hiccup should not turn a perfectly good image build into a failure; the
        # other is pull_image_files, which runs on the journal path, where raising
        # holds replication for every later record. A checksum is optional metadata
        # either way - not having one only means 'not verifiable'.
        try:
            if not hash_value and path:
                hash_value = self.compute(path)
            if not hash_value:
                return None
            where = [{"column": "object", "value": object_type},
                     {"column": "name", "value": name},
                     {"column": "file", "value": file}]
            row = Helper().make_rows({'object': object_type, 'name': name, 'file': file,
                                      'hashtype': self.hashtype, 'hash': hash_value,
                                      'created': strftime('%Y-%m-%d %H:%M:%S', localtime(time()))})
            current = Database().get_record(table='hash',
                                            where=f"object='{object_type}' AND name='{name}' AND file='{file}'")
            if current:
                Database().update('hash', row, where)
            else:
                Database().insert('hash', row)
            return hash_value
        except Exception as exp:
            # Loud, because a hash that silently stops being recorded is how
            # verification quietly becomes a no-op.
            self.logger.error(f"could not record {self.hashtype} for {object_type}/{name}/{file}: {exp}")
        return None


    def lookup(self, object_type, name, file):
        # Also never raises: a lookup that fails means 'cannot verify', and the
        # caller treats that exactly like an artefact that predates hashing.
        try:
            record = Database().get_record(table='hash',
                                           where=f"object='{object_type}' AND name='{name}' AND file='{file}'")
            if record:
                return record[0]['hash']
        except Exception as exp:
            self.logger.error(f"could not look up {self.hashtype} for {object_type}/{name}/{file}: {exp}")
        return None


    def forget_file(self, file):
        # Keyed on the artefact alone, because the thing that removes a file knows
        # its name and nothing else. Called when a file is actually deleted, so a
        # hash never outlives what it describes - otherwise a later artefact
        # reusing the name would look verifiable against the wrong bytes.
        try:
            Database().delete_row('hash', [{"column": "file", "value": file}])
        except Exception as exp:
            self.logger.error(f"could not forget hash for {file}: {exp}")


    def prune(self, files_path):
        """
        Drop rows whose artefact is no longer on disk.

        forget_file() covers the tidy path - a file removed through cleanup_file
        takes its row with it. This covers the untidy ones: a file removed by
        hand, lost with a filesystem, or deleted by anything that does not route
        through cleanup_file. Without it the table only ever grows, because a row
        is never wrong enough to notice - it just describes something that is not
        there any more.

        A row without its file is stale by definition: the table records what
        THIS controller holds, so nothing else can explain it.
        """
        try:
            rows = Database().get_record(table='hash')
            if not rows:
                return 0
            present = set(os.listdir(files_path))
            gone = [r['file'] for r in rows if r['file'] not in present]
            for file in gone:
                Database().delete_row('hash', [{"column": "file", "value": file}])
            if gone:
                self.logger.info(f"pruned {len(gone)} hash row(s) whose artefact is gone: {', '.join(gone[:3])}"
                                 + (" ..." if len(gone) > 3 else ""))
            return len(gone)
        except Exception as exp:
            self.logger.error(f"could not prune the hash table: {exp}")
        return 0


    def forget(self, object_type, name, file=None):
        # Called when the thing the hash describes is removed. A stale row is not
        # dangerous - it is looked up by name and file - but it is untidy and it
        # would make a later artefact of the same name look verifiable when it is
        # a different file.
        where = [{"column": "object", "value": object_type}, {"column": "name", "value": name}]
        if file:
            where.append({"column": "file", "value": file})
        Database().delete_row('hash', where)
