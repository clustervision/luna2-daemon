"""
Values in where clauses are single-quoted: SQLite reads a double-quoted token
as a column first, so an object named 'name' or 'status' matched every row
of its table, silently, on lookups, updates and deletes alike.
"""

import os
import re

import pytest

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'daemon')


@pytest.fixture
def node_db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'quote.db')
    database.local_thread.connection = None
    Database().create('node', DBStructure().get_database_table_structure('node'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_an_object_named_after_a_column_is_looked_up_alone(node_db):
    from utils.helper import Helper
    for name in ('node001', 'name', 'status'):
        node_db.insert('node', Helper().make_rows({'name': name}))
    assert node_db.id_by_name('node', 'name') == 2
    assert node_db.id_by_name('node', 'status') == 3
    assert node_db.name_by_id('node', 1) == 'node001'


def test_no_where_clause_double_quotes_its_value():
    """Derived over the tree, so the next f-string cannot bring the identifier trap back."""
    offenders = []
    for root, _, files in os.walk(DAEMON):
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            with open(path, encoding='utf-8') as handle:
                for number, line in enumerate(handle, 1):
                    if re.search(r'(where|query|WHERE).*=\s*\\?"\{', line):
                        offenders.append(f'{os.path.relpath(path, DAEMON)}:{number}')
    assert offenders == [], 'double-quoted values in where clauses: ' + ', '.join(offenders)
