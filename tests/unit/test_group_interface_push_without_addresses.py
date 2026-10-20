#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a new group interface on a network with no addresses in use reaches the nodes.

The group's interface settings are read with a query joined through ipaddress, and with a
fallback query when that finds nothing; both have to carry every setting the push applies.
"""

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh, isolated SQLite database with a one-node group and an unused network."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'groupinterface', 'node', 'nodeinterface', 'network', 'ipaddress', 'queue']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    networkid = Database().insert('network', Helper().make_rows(
        {'name': 'netxyz', 'network': '192.0.2.0', 'subnet': '24'}))
    groupid = Database().insert('group', Helper().make_rows({'name': 'groupxyz'}))
    Database().insert('groupinterface', Helper().make_rows(
        {'groupid': groupid, 'interface': 'eth9', 'networkid': networkid, 'mtu': '9000'}))
    Database().insert('node', Helper().make_rows({'name': 'nodexyz', 'groupid': groupid}))
    # the push pings for a free address; the address chosen is not what is under test
    monkeypatch.setattr(Helper, 'get_available_ip', lambda *args, **kwargs: '192.0.2.10')
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_new_interface_on_a_network_without_addresses_reaches_the_node(db):
    from utils.config import Config
    from utils.queue import Queue
    Queue().add_task_to_queue(task='add_interface_to_group_nodes', param='groupxyz:eth9',
                              subsystem='group_interface')

    Config().update_interface_on_group_nodes('groupxyz')

    interfaces = db.get_record(table='nodeinterface')
    assert [row['interface'] for row in interfaces] == ['eth9']
    assert str(interfaces[0]['mtu']) == '9000'
    assert not db.get_record(table='queue', where="subsystem = 'group_interface'")
