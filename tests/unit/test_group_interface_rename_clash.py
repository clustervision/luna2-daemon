#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a group interface is not renamed to a name one of its nodes already uses.

The group's nodes are renamed in the background, where the clash with the node's own
interface can only be logged, so the request itself has to refuse it.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with a group of two nodes."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'groupinterface', 'node', 'nodeinterface']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    groupid = Database().insert('group', Helper().make_rows({'name': 'groupxyz'}))
    Database().insert('groupinterface', Helper().make_rows({'groupid': groupid, 'interface': 'bond0'}))
    for name in ['node001', 'node002']:
        nodeid = Database().insert('node', Helper().make_rows({'name': name, 'groupid': groupid}))
        Database().insert('nodeinterface', Helper().make_rows({'nodeid': nodeid, 'interface': 'bond0'}))
    yield groupid
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def interfaces(table):
    from utils.database import Database
    return sorted(row['interface'] for row in Database().get_record(table=table))


def test_rename_to_a_name_a_node_already_has_is_refused(db):
    from utils.config import Config
    from utils.database import Database
    from utils.helper import Helper
    node = Database().get_record(table='node', where="name = 'node002'")
    Database().insert('nodeinterface', Helper().make_rows({'nodeid': node[0]['id'], 'interface': 'BOOTIF'}))

    status, message = Config().group_interface_rename(groupid=db, interface_name='bond0',
                                                      new_interface_name='BOOTIF')

    assert interfaces('groupinterface') == ['bond0']
    assert status is False
    assert 'node002' in message and 'node001' not in message, message


def test_rename_to_a_name_no_node_has_goes_ahead(db):
    from utils.config import Config
    status, message = Config().group_interface_rename(groupid=db, interface_name='bond0',
                                                      new_interface_name='BOOTIF')

    assert status is True, message
    assert interfaces('groupinterface') == ['BOOTIF']
