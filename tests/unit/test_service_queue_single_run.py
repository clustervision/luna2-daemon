#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: Service().queue and service_mother run a dhcp/dns task once per request burst.

A request folded into an existing task must not start a worker of its own, or every node
of a booting rack restarts dhcpd; a request made while a run renders must get a run after it.
"""

import pytest


class FakeExecutor:
    """Records the workers Service().queue would start, without starting them."""
    submitted = []

    def __init__(self, max_workers=None):
        pass

    def submit(self, *args):
        FakeExecutor.submitted.append(args[1:])

    def shutdown(self, wait=True):
        pass


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh, isolated SQLite database with the queue and status tables."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    import utils.service as service

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['queue', 'status']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['SERVICES'], 'DHCP', 'dhcpd')
    monkeypatch.setitem(constant.CONSTANT['SERVICES'], 'DNS', 'named')
    monkeypatch.setattr(service.concurrent.futures, 'ThreadPoolExecutor', FakeExecutor)
    monkeypatch.setattr(service, 'sleep', lambda seconds: None)
    FakeExecutor.submitted = []
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_a_request_folded_into_a_waiting_task_starts_no_worker(db):
    from utils.service import Service
    Service().queue('dhcp', 'restart')
    FakeExecutor.submitted = []

    Service().queue('dhcp', 'restart')

    assert FakeExecutor.submitted == []
    assert len(db.get_record(table='queue', where="subsystem = 'service'")) == 1


def test_a_request_made_during_a_run_gets_a_run_of_its_own(db, monkeypatch):
    from utils.service import Service
    runs = []

    def luna_service(self, service, action):
        runs.append((service, action))
        if len(runs) == 1:
            Service().queue('dhcp', 'restart')
        return True, 'ok'

    monkeypatch.setattr(Service, 'luna_service', luna_service)
    Service().queue('dhcp', 'restart')

    Service().service_mother('dhcp', 'restart', '__internal__')

    assert runs == [('dhcp', 'restart'), ('dhcp', 'restart')]
    assert not db.get_record(table='queue', where="subsystem = 'service'")
