#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Shared fixtures for the Route unit tests.

The Route class talks to the real Database layer, which reads its SQLite path from
CONSTANT at connect time. These fixtures repoint CONSTANT at a throwaway database so
the real code is exercised without touching any live data. The whole module is
skipped where the daemon configuration is absent (e.g. a bare CI checkout).
"""

import os
import sys

import pytest

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
sys.path.insert(0, DAEMON)

# Skips the entire unit suite when the daemon config/deps are unavailable.
pytest.importorskip('base.route')


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the route-relevant tables created."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['route', 'routemap', 'node', 'group', 'network']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def seed(db):
    """Insert a node in a group plus two networks; return their ids."""
    from utils.helper import Helper
    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    clusterid = db.insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    extid = db.insert('network', Helper().make_rows(
        {'name': 'ext', 'network': '10.145.0.0', 'subnet': '16'}))
    nodeid = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    return {'groupid': groupid, 'clusterid': clusterid, 'extid': extid, 'nodeid': nodeid}


def make_route(name, destination, gateway='', device='', metric=None):
    """Create a route through the real Route.update_route path; return its id."""
    from base.route import Route
    from utils.database import Database
    payload = {'config': {'route': {name: {
        'destination': destination, 'gateway': gateway, 'device': device, 'metric': metric}}}}
    status, message = Route().update_route(name, payload)
    assert status, message
    return Database().get_record(table='route', where=f"name='{name}'")[0]['id']
