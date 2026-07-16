#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1481 unit tests guarding the table set used for backups and HA hashing.

Tables' list gates two things its name does not suggest: the cluster export
customers restore from, and the hashes controllers compare to verify each other
in HA. A table absent from it is silently missing from every backup and invisible
to controller comparison -- the restore succeeds and the data is simply gone.

DBStructure's list is the declarative reality: everything the daemon creates.
Nothing keeps the two in step, so these tests do. A new table is backed up unless
it is deliberately named transient below.
"""

# Tables deliberately left out of backups and hashing, with the reason they are
# out. Transient runtime state only: you do not back up a queue, and hashing state
# that legitimately differs per controller would make two healthy controllers look
# permanently out of sync.
#
# Adding a name here is a decision, not a formality -- excluding configuration is
# data loss. The burden is on exclusion.
TRANSIENT = {
    'queue': 'work queue',
    'status': 'in-flight request status',
    'journal': 'replication journal',
    'tracker': 'torrent tracker state',
    'ping': 'liveness probe results',
    'monitor': 'monitoring state, differs per controller',
    'reference': 'lookup sidecar for monitor rows',
    'ha': 'this controller\'s own HA state',
    'reservedipaddress': 'short-lived IP reservations, garbage-collected after 10 minutes',
}


def _lists():
    from utils.dbstructure import DBStructure
    from utils.tables import Tables
    return set(DBStructure().tables), set(Tables().tables)


def test_every_configuration_table_is_backed_up():
    """Anything the daemon creates is backed up unless it is named transient."""
    created, backed_up = _lists()
    unaccounted = created - backed_up - set(TRANSIENT)
    assert not unaccounted, (
        f"tables created but neither backed up nor declared transient: {sorted(unaccounted)}. "
        "Add them to Tables().tables, or to TRANSIENT with the reason they are runtime state."
    )


def test_backup_set_holds_no_unknown_tables():
    """A backed-up table the daemon never creates is a dead name or a typo."""
    created, backed_up = _lists()
    assert not backed_up - created, sorted(backed_up - created)


def test_transient_exclusions_still_exist():
    """A renamed or dropped table must not linger here, silently excusing nothing."""
    created, _ = _lists()
    assert not set(TRANSIENT) - created, sorted(set(TRANSIENT) - created)


def test_transient_tables_are_not_backed_up():
    """The exclusions are real: nothing named transient is in the backup set."""
    _, backed_up = _lists()
    assert not backed_up & set(TRANSIENT), sorted(backed_up & set(TRANSIENT))
