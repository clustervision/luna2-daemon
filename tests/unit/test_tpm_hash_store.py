#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The /tpm endpoint stores the hash a node reports. A node without a TPM reports an
empty string on every boot, and storing that - or re-storing an unchanged hash - is a
raw write on whichever controller answered, which is what keeps the node table
differing between the controllers of a pair.
"""

import pytest

pytest.importorskip('base.authentication')


@pytest.fixture
def node_and_cluster(db, seed):
    from utils.dbstructure import DBStructure
    db.create('cluster', DBStructure().get_database_table_structure('cluster'))
    db.insert('cluster', [{'column': 'name', 'value': 'trinity'}, {'column': 'security', 'value': 0}])
    return seed['nodeid']


@pytest.fixture
def updates(monkeypatch):
    """Count node-table writes made by node_token, without stopping them."""
    from utils.database import Database
    real = Database.update
    calls = []

    def counting(self, table, row, where=None):
        calls.append(table)
        return real(self, table, row, where)
    monkeypatch.setattr(Database, 'update', counting)
    return calls


@pytest.fixture
def auth(monkeypatch):
    import common.constant as constant
    from base.authentication import Authentication
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    monkeypatch.setattr(Authentication, 'get_token', lambda self, data: (True, {'token': 'x'}))
    return Authentication()


def stored(db):
    return db.get_record(table='node', where="name = 'node001'")[0]['tpm_sha256']


def test_an_empty_hash_is_not_stored(db, node_and_cluster, updates, auth):
    status, _ = auth.node_token({'tpm_sha256': '', 'username': 'u', 'password': 'p'}, 'node001')
    assert status is True
    assert updates == []
    assert not stored(db)


def test_a_real_hash_is_stored_once_and_not_rewritten_unchanged(db, node_and_cluster, updates, auth):
    payload = {'tpm_sha256': 'a' * 64, 'username': 'u', 'password': 'p'}
    auth.node_token(payload, 'node001')
    assert stored(db) == 'a' * 64
    assert updates == ['node']
    auth.node_token(payload, 'node001')
    assert updates == ['node'], "an unchanged hash must not be written again"


def test_a_changed_hash_replaces_the_stored_one(db, node_and_cluster, updates, auth):
    auth.node_token({'tpm_sha256': 'a' * 64, 'username': 'u', 'password': 'p'}, 'node001')
    auth.node_token({'tpm_sha256': 'b' * 64, 'username': 'u', 'password': 'p'}, 'node001')
    assert stored(db) == 'b' * 64
    assert updates == ['node', 'node']
