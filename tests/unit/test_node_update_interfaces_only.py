#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
A node update that carries only interfaces (as a node's own boot sends) has no node
column to write: it must not issue an UPDATE with an empty row, which fails and logs
an ERROR on every boot, and the interface must still be stored.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in DBStructure().tables:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('osimage', Helper().make_rows({'name': 'theosimage'}))
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Database().insert('group', Helper().make_rows({'name': 'compute', 'osimageid': 1}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': 1}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_an_interfaces_only_update_writes_no_empty_node_row(db, monkeypatch):
    from base.node import Node
    from utils.database import Database

    node_updates = []
    real_update = Database.update

    def spy(self, table=None, row=[], where=[]):
        if table == 'node':
            node_updates.append(list(row))
        return real_update(self, table, row, where)

    monkeypatch.setattr(Database, 'update', spy)
    status, message = Node().update_node(name='node001', request_data={'config': {'node': {'node001': {
        'interfaces': [{'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:01', 'network': 'cluster'}]}}}})

    assert status is True, message
    assert [] not in node_updates, f'UPDATE node with an empty row: {node_updates}'
    stored = db.get_record_join(['nodeinterface.macaddress'], ['nodeinterface.nodeid=node.id'],
                                ["node.name='node001'", "nodeinterface.interface='BOOTIF'"])
    assert stored and stored[0]['macaddress'] == 'aa:bb:cc:dd:ee:01', stored
