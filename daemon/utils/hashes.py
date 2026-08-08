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


    # Deliberately no prune(): there is no sweep over this table.
    #
    # A sweep would decide what to delete from what is on disk right now, and an
    # empty listing is indistinguishable from every artefact having been removed -
    # so a path that is unmounted, misconfigured or briefly unreadable takes the
    # whole table with it. That failure is silent, because a missing row reads as
    # 'not verifiable', which is a legitimate state: downloads would simply stop
    # being verified and nothing would say so.
    #
    # These rows are long-lived - an image can sit unchanged for years - while a
    # stale row is inert: artefact names carry a timestamp, so a name never recurs
    # and the row is never consulted again. delete_hashes below is the whole
    # cleanup story, and it deletes on evidence rather than on absence.

    def delete_hashes(self, object_type=None, name=None, file=None):
        """
        Remove hash rows. Narrow by artefact, by the thing that owns them, or both.

        One method rather than two, because the callers differ only in what they
        happen to know. Cleanup knows a filename and nothing else; deleting an
        osimage knows the osimage and not which artefacts it had. Both are the same
        act - the hashes go when the thing they describe goes.

        A row that outlives its artefact is not merely untidy: a later artefact
        reusing the name would look verifiable against the wrong bytes.

        Never raises. This runs from the journal path and from cleanup, and a
        tidy-up that fails must not take either of those down with it.
        """
        where = []
        if object_type:
            where.append({"column": "object", "value": object_type})
        if name:
            where.append({"column": "name", "value": name})
        if file:
            where.append({"column": "file", "value": file})
        if not where:
            # Not a data-loss guard: delete_row builds its clause by iterating the
            # filter, so an empty one leaves the clause unassigned and raises before
            # any query runs. The guard is here to say plainly what happened instead
            # of leaving a NameError in the log for someone to decode.
            self.logger.error("delete_hashes called with nothing to narrow on; ignoring")
            return
        try:
            Database().delete_row('hash', where)
        except Exception as exp:
            self.logger.error(f"could not delete hash rows for {object_type}/{name}/{file}: {exp}")
