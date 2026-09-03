"""
Two controllers holding the same row must hash it the same, whenever each wrote it.

A journaled write lands on the peer seconds after the origin, and the tables
that carry created or updated stamp them with the local clock. Hashing those
columns made biosconfig, nodeinventory and firmwarerequest differ on every
sweep, and the repair - which clears the live table and reloads it - ran every
hour on the secondary while the content was identical.
"""

import pytest

from utils.dbstructure import DBStructure
from utils.helper import Helper


def _hash(table, rows, tmp_path, name):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.tables import Tables
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / f'{name}.db')
    database.local_thread.connection = None
    Database().create(table, DBStructure().get_database_table_structure(table))
    for row in rows:
        Database().insert(table, Helper().make_rows(row))
    return Tables().get_table_hashes()[table]


@pytest.fixture(autouse=True)
def restore_database():
    import common.constant as constant
    from utils import database
    original = constant.CONSTANT['DATABASE']['DATABASE']
    yield
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _tables_with_timestamps():
    """The tables the sweep replicates that carry a clock stamp - from the sweep's own list."""
    from utils.tables import Tables
    structure = DBStructure()
    return sorted(table for table in Tables().tables
                  if {'created', 'updated'} & {c['column'] for c in structure.get_database_table_structure(table)})


@pytest.mark.parametrize('table', _tables_with_timestamps())
def test_the_same_row_written_at_different_times_hashes_the_same(table, tmp_path):
    columns = {c['column'] for c in DBStructure().get_database_table_structure(table)}
    row = {column: 'x' for column in columns if column not in ('id', 'created', 'updated')}
    origin = dict(row, **{c: 'NOW - 1 minute' for c in ('created', 'updated') if c in columns})
    peer = dict(row, **{c: 'NOW' for c in ('created', 'updated') if c in columns})
    assert _hash(table, [origin], tmp_path, 'origin') == _hash(table, [peer], tmp_path, 'peer'), \
        f'{table}: a row that only differs in when it was written must not trigger a repair'


def test_a_real_difference_still_hashes_differently(tmp_path):
    table = _tables_with_timestamps()[0]
    columns = {c['column'] for c in DBStructure().get_database_table_structure(table)}
    base = {column: 'x' for column in columns if column not in ('id', 'created', 'updated')}
    other = dict(base); other[sorted(base)[0]] = 'y'
    assert _hash(table, [base], tmp_path, 'a') != _hash(table, [other], tmp_path, 'b')
