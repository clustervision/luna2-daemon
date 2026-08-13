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
    'ownercache': 'per-controller NSS owner resolutions, rebuilt from the directory on demand',
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


def _rack_db(tmp_path):
    """A throwaway database with a populated rack -- the table whose column is named 'order'."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'backup.db')
    database.local_thread.connection = None
    Database().create('rack', DBStructure().get_database_table_structure('rack'))
    Database().insert('rack', Helper().make_rows(
        {'name': 'demo01', 'room': 'DC1', 'site': 'AMS', 'order': 'ascending', 'size': 12}))
    return Database()


def test_reserved_word_column_does_not_export_as_empty(tmp_path):
    """
    A populated table must never export as empty. rack's 'order' column is a reserved
    word: unquoted it makes the select a syntax error, the error is logged and swallowed,
    and the export quietly returns structure with no rows.

    An empty table is legitimate -- tables are empty on purpose all the time. That is
    exactly why this is dangerous: a broken read is indistinguishable from an empty table,
    so nothing downstream can tell the difference.
    """
    from utils.tables import Tables

    db = _rack_db(tmp_path)
    try:
        exported = Tables().export_table('rack', sequence=True, structure=True)
        rows = [r for r in exported if 'STRUCTURE' not in r and 'SQLITE_SEQUENCE' not in r]
        assert len(rows) == 1, "populated rack exported as empty -- the select died on 'order'"
        assert rows[0]['name'] == 'demo01'
        assert rows[0]['order'] == 'ascending'
    finally:
        db.close() if hasattr(db, 'close') else None


def test_backup_roundtrip_preserves_a_reserved_word_table(tmp_path):
    """Export then import must return the rack unchanged, not wipe it.

    import_table clears the table before writing, which is correct for a genuinely
    empty one. Paired with an export that wrongly reads empty, it destroys the data.
    """
    from utils.database import Database
    from utils.tables import Tables

    _rack_db(tmp_path)
    before = Database().get_record(table='rack')
    exported = Tables().export_table('rack', sequence=True, structure=True)
    Tables().import_table('rack', exported, emptyok=True, fixtable=False)
    after = Database().get_record(table='rack')

    assert len(after) == len(before) == 1, "restore destroyed rack data"
    assert after[0]['name'] == 'demo01' and after[0]['order'] == 'ascending'


def test_every_backed_up_table_is_readable(tmp_path):
    """
    No table in the backup set may carry a column the export cannot read. This is the
    general form of the rack bug: quoting is what makes it hold, so it stays true for
    any column name anyone adds later.
    """
    import re
    from utils.database import Database
    from utils.dbstructure import DBStructure

    _, backed_up = _lists()
    unreadable = []
    for table in sorted(backed_up):
        layout = DBStructure().get_database_table_structure(table)
        if not layout:
            continue
        columns = [c['column'] for c in layout]
        quoted = Database().quote_columns(columns)
        for original, q in zip(columns, quoted):
            if not re.fullmatch(r'"%s"' % re.escape(original), q):
                unreadable.append((table, original))
    assert not unreadable, f"columns not safely quoted for select: {unreadable}"
