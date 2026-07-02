#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for the data layer against a real SQLite database.

The daemon's Database supports a SQLite3 driver, so these run the genuine
insert/get/update/delete code against a temp database whose schema is built
from the daemon's own database_layout definitions (see the sqlite_db fixture).
No MSSQL/pyodbc, no mocking of the data layer.
"""

import pytest


@pytest.fixture
def database(sqlite_db):
    from utils.database import Database
    return Database()


@pytest.mark.regression
def test_create_database_tables_builds_full_schema(sqlite_db_path):
    """
    Regression for the DBStructure.create_database_tables NameError.

    The method called a bare get_database_table_structure() (only defined as an
    instance method), so it raised NameError and created nothing whenever
    invoked. On an empty database it must build every declared table. Runs on
    sqlite_db_path (no pre-built schema) so the method itself does the work.
    """
    from utils.database import Database
    from utils.dbstructure import DBStructure

    structure = DBStructure()
    # The database starts empty: no table exists yet.
    assert not Database().get_columns(structure.tables[0])

    structure.create_database_tables()

    for table in structure.tables:
        assert Database().get_columns(table), f"table {table} was not created"


@pytest.mark.regression
def test_schema_has_expected_tables(database):
    """Every declared table exists with columns after the schema build."""
    from utils.dbstructure import DBStructure
    for table in DBStructure().tables:
        assert database.get_columns(table), f"table {table} missing columns"


@pytest.mark.regression
def test_node_insert_get_update_delete(database):
    database.insert("node", [
        {"column": "name", "value": "node001"},
        {"column": "status", "value": "active"},
    ])

    rows = database.get_record(table="node", where='name="node001"')
    assert len(rows) == 1
    assert rows[0]["name"] == "node001"
    assert rows[0]["status"] == "active"

    database.update("node",
                    [{"column": "status", "value": "booted"}],
                    [{"column": "name", "value": "node001"}])
    rows = database.get_record(table="node", where='name="node001"')
    assert rows[0]["status"] == "booted"

    database.delete_row("node", [{"column": "name", "value": "node001"}])
    assert database.get_record(table="node", where='name="node001"') == []


@pytest.mark.regression
def test_id_by_name_roundtrip(database):
    database.insert("group", [{"column": "name", "value": "compute"}])
    group_id = database.id_by_name("group", "compute")
    assert group_id is not None
    assert database.name_by_id("group", group_id) == "compute"
