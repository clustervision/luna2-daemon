#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a change made while a dns/dhcp run is under way gets a run of its own.

The run renders from the database it read at the start; a request that is folded into it
instead of queued after it never reaches the service.
"""

import threading

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh, isolated SQLite database with the tables a housekeeper pass touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['queue', 'ha', 'monitor', 'reference', 'ipaddress']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['SERVICES'], 'DHCP', 'dhcpd')
    monkeypatch.setitem(constant.CONSTANT['SERVICES'], 'DNS', 'named')
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_a_change_during_a_dns_reload_queues_a_second_reload(db, monkeypatch):
    from utils.housekeeper import Housekeeper
    from utils.queue import Queue
    from utils.service import Service
    runs = []

    def luna_service(self, service, action):
        runs.append((service, action))
        if len(runs) == 1:
            Queue().add_task_to_queue(task='reload', param='dns', subsystem='housekeeper',
                                      request_id='__node_update__')
        return True, 'ok'

    monkeypatch.setattr(Service, 'luna_service', luna_service)
    Queue().add_task_to_queue(task='reload', param='dns', subsystem='housekeeper',
                              request_id='__node_update__')
    stop = threading.Event()
    stop.set()

    Housekeeper().tasks_mother(stop)

    assert runs == [('dns', 'reload'), ('dns', 'reload')]
    assert not db.get_record(table='queue', where="subsystem = 'housekeeper'")
