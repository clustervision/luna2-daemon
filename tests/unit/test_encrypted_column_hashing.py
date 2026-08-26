#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2018: a table hash must describe what the data means, not how it is stored.

Fernet puts 16 random bytes of IV in every token, so encrypting the same plaintext
twice under the same key gives two different strings. That is deliberate and
correct - deterministic ciphertext would leak equality - but it means the two
controllers of an HA pair, which each encrypt the plaintext the journal replays to
them, store different bytes for identical data and hash differently forever.

Reproduced on a live pair before this was written: one secret, one plaintext, one
key, and clustersecrets hashing 6a2b9549... on the master against 182b2a10... on
the secondary. hardsync then re-imports the table and bounces dhcp, dhcp6 and dns
over a difference that is not one.
"""

import ast
import os

import pytest

from utils.dbstructure import DBStructure
from utils.helper import Helper

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'daemon')


def _declared_encrypted_at_import():
    """Marked (table, column) pairs, read at collection time so the cases derive
    themselves - a table marked encrypted later is covered without editing this file."""
    structure = DBStructure()
    return {(table, column)
            for table in structure.tables
            for column in structure.get_encrypted_columns(table)}


def _row_for(table, content):
    """A minimal valid row for whichever table the case landed on."""
    columns = {entry['column'] for entry in DBStructure().get_database_table_structure(table)}
    row = {'name': 'shared', 'content': content}
    for column, value in (('path', '/etc/thing'), ('owner', 'root'), ('mode', '0600')):
        if column in columns:
            row[column] = value
    return row


# --- the fix itself ---------------------------------------------------------

def _set_encryption(monkeypatch, value):
    """
    CONSTANT is a process-wide dict, so setting it directly leaks into every test
    that runs afterwards - and this file sorts before test_helper.py, which then
    fails because encryption has silently been turned off underneath it. Set it
    through monkeypatch so it is put back.
    """
    import common.constant as constant

    constant.CONSTANT.setdefault('SECRETS', {})
    monkeypatch.setitem(constant.CONSTANT['SECRETS'], 'ENCRYPT_SECRETS', value)


@pytest.fixture
def encrypting(monkeypatch):
    """A daemon configured the way a trix-installed controller actually is."""
    from cryptography.fernet import Fernet
    import utils.helper as helper

    key = Fernet.generate_key().decode()
    _set_encryption(monkeypatch, 'yes')
    monkeypatch.setattr(helper, 'LUNAKEY', key, raising=False)
    return key


def stored_twice(plaintext='a shared secret'):
    """What each of two controllers independently stores for the same plaintext."""
    return Helper().encrypt_string(plaintext), Helper().encrypt_string(plaintext)


def test_two_controllers_encrypt_the_same_secret_differently(encrypting):
    """The premise. If this ever stops being true the rest of the file is moot."""
    one, two = stored_twice()
    assert one != two
    assert one.startswith('gAAAAA') and two.startswith('gAAAAA')
    assert Helper().decrypt_string(one) == Helper().decrypt_string(two) == 'a shared secret'


def hash_of(table, rows, monkeypatch, tmp_path, name):
    """The daemon's own get_table_hashes over a table containing exactly these rows."""
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


@pytest.mark.parametrize('table', sorted({t for t, _ in _declared_encrypted_at_import()}))
def test_identical_secrets_hash_identically_across_controllers(table, encrypting,
                                                               monkeypatch, tmp_path):
    """
    The bug, and the fix. Two controllers holding the same secret must report the
    same hash for the table, or hardsync tears the table down and rebuilds it every
    cycle for nothing.

    Fails without the change: the two ciphertexts differ, so the hashes do.
    """
    one, two = stored_twice()
    assert one != two, 'the two controllers must have stored different bytes'
    controller_one = hash_of(table, [_row_for(table, one)], monkeypatch, tmp_path, 'one')
    controller_two = hash_of(table, [_row_for(table, two)], monkeypatch, tmp_path, 'two')
    assert controller_one == controller_two


def test_a_genuine_difference_is_still_detected(encrypting, monkeypatch, tmp_path):
    """
    The other half, and the reason not to simply drop the column from the hash: a
    pair that really does hold different secrets has to be reported as different.
    """
    row = {'name': 'shared', 'path': '/etc/thing', 'owner': 'root', 'mode': '0600'}
    one = hash_of('clustersecrets', [dict(row, content=Helper().encrypt_string('alpha'))],
                  monkeypatch, tmp_path, 'a')
    two = hash_of('clustersecrets', [dict(row, content=Helper().encrypt_string('beta'))],
                  monkeypatch, tmp_path, 'b')
    assert one != two


def test_a_cluster_with_encryption_off_is_unaffected(monkeypatch, tmp_path):
    """
    decrypt_string returns anything that is not a Fernet token unchanged, so a
    controller storing plaintext hashes exactly as it always did. Nothing about
    this change is conditional on encryption being enabled.
    """
    _set_encryption(monkeypatch, '')
    row = {'name': 'shared', 'content': 'plain as day', 'path': '/etc/thing'}
    one = hash_of('clustersecrets', [row], monkeypatch, tmp_path, 'p1')
    two = hash_of('clustersecrets', [dict(row)], monkeypatch, tmp_path, 'p2')
    assert one == two


# --- the guard that stops this becoming registration list #8 ----------------

def encrypt_targets():
    """
    Every column name the daemon writes an encrypted value into, read out of the
    source rather than listed here.

    Matches assignments of the shape x['col'] = ...encrypt_string(...). It yields
    column *names* and not (table, column) pairs, deliberately: the encryption
    happens on a dict and the insert happens later with a table name, and linking
    the two statically is fragile enough to be worse than not doing it.

    The table half is supplied from the other direction instead - the caller asks
    every hashed table whether it carries a column of one of these names and has
    marked it. That is what makes the guard hold for a table nobody has thought of
    yet, which a check on names alone would not.
    """
    found = set()
    for root, _, files in os.walk(DAEMON):
        if '__pycache__' in root:
            continue
        for filename in files:
            if not filename.endswith('.py'):
                continue
            with open(os.path.join(root, filename), 'r', encoding='utf-8') as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value.func
                if not (isinstance(call, ast.Attribute) and call.attr == 'encrypt_string'):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)
                            and isinstance(target.slice.value, str)):
                        found.add(target.slice.value)
    return found


def declared_encrypted():
    """Every (table, column) marked encrypted in the layout."""
    structure = DBStructure()
    return {(table, column)
            for table in structure.tables
            for column in structure.get_encrypted_columns(table)}


def test_every_hashed_table_marks_the_columns_the_daemon_encrypts():
    """
    The trap this closes: encrypt_string is called at scattered sites, and the
    hashing needs an independent statement of which columns those are. Two lists
    over one fact drift, and the symptom is a pair that never agrees again - which
    is exactly this bug, arriving a second time.

    Asserting per *table* rather than per column name is what makes it hold: a
    weaker check on names alone passes as long as some table declares the column,
    so a brand new hashed table with an encrypted content column would sail
    through. This asks the question of every table that gets hashed.

    A hashed table carrying a column of that name and genuinely not encrypting it
    would need excusing here with the reason - the same shape as the transient
    list in test_backup_tables.py, and deliberately empty today.
    """
    from utils.tables import Tables

    targets = encrypt_targets()
    assert targets, 'found no encrypt_string call sites at all - the matcher has rotted'
    structure = DBStructure()
    NOT_ENCRYPTED = {}       # (table, column): reason
    missing = []
    for table in sorted(set(Tables().tables)):
        layout = structure.get_database_table_structure(table) or []
        marked = set(structure.get_encrypted_columns(table))
        for entry in layout:
            column = entry['column']
            if column in targets and column not in marked:
                if (table, column) not in NOT_ENCRYPTED:
                    missing.append(f'{table}.{column}')
    assert not missing, (
        f'these are hashed and hold a column the daemon encrypts, but are not marked: '
        f'{sorted(missing)}. Add "encrypted": True to the column in database_layout.py, '
        f'or the two controllers will hash ciphertext and never agree.'
    )


def test_nothing_is_marked_encrypted_that_is_never_encrypted():
    """A dead declaration means the layout is describing something that stopped being true."""
    targets = encrypt_targets()
    stale = sorted({column for _, column in declared_encrypted()} - targets)
    assert not stale, f'marked encrypted but never passed to encrypt_string: {stale}'


def test_every_marked_column_exists_in_its_table():
    """Catches a typo or a column that was renamed out from under the mark."""
    structure = DBStructure()
    for table, column in declared_encrypted():
        columns = [entry['column'] for entry in structure.get_database_table_structure(table)]
        assert column in columns, f'{table} has no column {column}'


def test_every_marked_column_is_in_a_table_that_is_actually_hashed():
    """
    Marking a column that is not in the hashing set would be harmless and
    pointless. Marking one that *is* hashed is the whole point, so the mark and
    the hashing set should agree about which tables matter.
    """
    from utils.tables import Tables
    hashed = set(Tables().tables)
    for table, _ in declared_encrypted():
        assert table in hashed, f'{table} is marked encrypted but is not hashed or backed up'


# --- backwards compatibility, both directions -------------------------------

def test_the_marker_is_inert_to_everything_that_consumes_a_layout():
    """
    The layout travels inside an export, as the STRUCTURE record, so that a daemon
    which does not know the table locally can still build it. That makes the new
    key a cross-version concern in both directions:

      old export -> new daemon: no marker in the STRUCTURE, and it does not matter,
      because the hashing reads the marker from the running code's own layout and
      never from the imported structure.

      new export -> old daemon: the STRUCTURE now carries "encrypted": True, and an
      older Luna must ignore it rather than choke. Every consumer of a layout dict
      reads only the keys it knows, which is what this asserts.
    """
    import inspect

    from utils.database import Database

    for method in (Database.create, Database.add_column):
        source = inspect.getsource(method)
        # the guard shape that makes an unknown key inert
        assert "in cols.keys()" in source or "in column.keys()" in source, (
            f'{method.__name__} no longer reads layout keys defensively; an unknown key '
            f'such as "encrypted" in an exported STRUCTURE could now break an older daemon'
        )


def test_a_layout_carrying_the_marker_still_creates_the_table(monkeypatch, tmp_path):
    """The end-to-end version of the above: the marker must not reach the SQL."""
    import common.constant as constant
    from utils import database
    from utils.database import Database

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'marker.db')
    database.local_thread.connection = None
    layout = DBStructure().get_database_table_structure('clustersecrets')
    assert any(entry.get('encrypted') for entry in layout), 'fixture no longer covers the case'
    Database().create('clustersecrets', layout)
    columns = Database().get_columns('clustersecrets')
    assert 'content' in columns and 'encrypted' not in columns
