#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2188 unit tests: the provisioning plugin named by a node or a group is checked the
same way on both, for the method and for the fallback, each on its own.

A node checked the method when it was handed the fallback, so a change of the fallback
alone raised, and a fallback naming no plugin passed whenever the method was a good one.
"""

import os

import pytest

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh, isolated SQLite database with a group and a node in it."""
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
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    groupid = Database().insert('group', Helper().make_rows({'name': 'compute'}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _update(table, name, fields):
    from base.group import Group
    from base.node import Node
    update = Node().update_node if table == 'node' else Group().update_group
    return update(name, {'config': {table: {name: dict(fields)}}})


@pytest.mark.parametrize('table, name', [('node', 'node001'), ('group', 'compute')])
@pytest.mark.parametrize('key', ['provision_method', 'provision_fallback'])
def test_each_key_is_accepted_on_its_own(db, table, name, key):
    status, message = _update(table, name, {key: 'http'})
    assert status, message
    assert db.get_record(table=table, where=f"name = '{name}'")[0][key] == 'http'


@pytest.mark.parametrize('table, name', [('node', 'node001'), ('group', 'compute')])
@pytest.mark.parametrize('fields', [{'provision_method': 'nosuch'}, {'provision_fallback': 'nosuch'},
                                    {'provision_method': 'torrent', 'provision_fallback': 'nosuch'}])
def test_a_key_naming_no_plugin_is_refused(db, table, name, fields):
    status, message = _update(table, name, fields)
    assert status is False and message == 'Invalid request: provisioning plugin nosuch does not exist'
    row = db.get_record(table=table, where=f"name = '{name}'")[0]
    assert row['provision_method'] is None and row['provision_fallback'] is None
