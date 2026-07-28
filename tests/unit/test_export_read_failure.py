#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1937 unit tests separating "this table is empty" from "I could not read this table".

Empty and broken look identical, and that is the trap. Tables are legitimately empty all
the time -- routemap normally is -- so nothing downstream distinguishes "no rows" from
"the read failed" unless the read says so.

It matters because the HA repair path acts on the answer. When two controllers' table
hashes disagree, the secondary fetches the master's copy and calls import_table with
emptyok=True, and import_table clears the table before writing. So a master that cannot
READ a table used to serve it as empty, with status True, and the secondary would clear
its own good copy over the top. import_table has always refused None -- "which i cannot
permit" -- and that guard was unreachable, because export_table returned a list whether
the read worked or not.

The fix is only correct if it keeps both halves: a read failure must be None, and an
empty table must still export, import and restore as empty. These tests pin both, because
breaking the second one to fix the first would be worse than the bug.
"""

import pytest

from base.cluster import Cluster
from base.tables import Tables as BTables
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.helper import Helper
from utils.tables import Tables


@pytest.fixture
def db(tmp_path):
    """A throwaway database with a populated table and a legitimately empty one."""
    import common.constant as constant
    from utils import database

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'export.db')
    database.local_thread.connection = None
    for table in ['group', 'routemap']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('group', Helper().make_rows({'name': 'compute'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


# ---------------------------------------------------------------- an empty table is normal

def test_an_empty_table_exports_without_complaint(db):
    """routemap is normally empty. That is not a failure and must not be reported as one."""
    data = Tables().export_table('routemap')
    assert data is not None, (
        "an empty table exported as None. None means 'could not read', and import_table refuses "
        "it -- so a genuinely empty table would never restore."
    )
    rows = [record for record in data if 'STRUCTURE' not in record and 'SQLITE_SEQUENCE' not in record]
    assert rows == [], f"an empty table exported rows from nowhere: {rows}"


def test_an_empty_table_survives_a_round_trip(db):
    """Export then import an empty table: it must come back, empty, without error."""
    data = Tables().export_table('routemap')
    assert Tables().import_table(table='routemap', data=data, emptyok=True) is True, (
        "importing a legitimately empty table failed. Empty is a normal state, not an error."
    )
    assert (Database().get_record(table='routemap') or []) == []


def test_a_populated_table_survives_a_round_trip(db):
    """The control: real rows must come back."""
    data = Tables().export_table('group')
    assert Tables().import_table(table='group', data=data, emptyok=True) is True
    names = [row['name'] for row in (Database().get_record(table='group') or [])]
    assert names == ['compute'], f"a populated table did not round-trip: {names}"


# ---------------------------------------------------------------- a failed read is not empty

def test_a_failed_read_exports_as_none_not_as_empty(db, monkeypatch):
    """The whole point. A read that failed must not be indistinguishable from an empty table."""
    monkeypatch.setattr(Database, 'get_record', lambda *a, **kw: None)
    assert Tables().export_table('group') is None, (
        "a table whose read FAILED exported as empty. The peer imports that over its own good "
        "copy, because import_table clears before it writes."
    )


def test_a_failed_column_read_exports_as_none_not_as_empty(db, monkeypatch):
    """The same, one layer up: get_columns answers None for a failure too."""
    monkeypatch.setattr(Database, 'get_columns', lambda *a, **kw: None)
    assert Tables().export_table('group') is None


def test_import_refuses_none_before_it_clears_anything(db):
    """The guard that always existed. It must bail out BEFORE Database().clear(table)."""
    assert Tables().import_table(table='group', data=None, emptyok=True) is False
    names = [row['name'] for row in (Database().get_record(table='group') or [])]
    assert names == ['compute'], (
        "import_table cleared the table before refusing the None it was handed. The refusal is "
        "worthless if the data is already gone."
    )


def test_serving_a_table_we_cannot_read_reports_failure(db, monkeypatch):
    """What the peer asks. Saying True here is what makes the secondary destroy its copy."""
    monkeypatch.setattr(Database, 'get_record', lambda *a, **kw: None)
    status, response = BTables().get_table_data('group')
    assert status is False, (
        f"a table that could not be read was served to the peer with status True: {response}"
    )


def test_a_backup_is_not_returned_when_a_table_cannot_be_read(db, monkeypatch):
    """A backup that restores clean and lacks the data is the worst outcome available."""
    monkeypatch.setattr(Database, 'get_record', lambda *a, **kw: None)
    status, response = Cluster().export_config()
    assert status is False, (
        f"export_config reported success while a table could not be read: {response}. A backup "
        f"missing a table is data loss, discovered when the customer needs it most."
    )
