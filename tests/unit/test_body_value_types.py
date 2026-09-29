#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2188 unit tests: a body that carries the wrong kind of value does not make a write raise.

A write is journaled before it runs, so a body that makes the base class raise answers
500 here and halts the journal of the other controller. The base classes read a text
field as text: nothing clears it, and a number, a list or an object is refused by the
checks the field already has. Every column of every object with a write route is tried,
read from the layout, through the real routes.
"""

import json
import os

import pytest
from flask import Flask
from jwt import encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))

OBJECTS = {
    'osimage': ('osimage', 'img', {'path': '/tmp/__none__'}),
    'bmcsetup': ('bmcsetup', 'bmc', {'userid': 3, 'username': 'u', 'password': 'p', 'netchannel': 1, 'mgmtchannel': 1}),
    'group': ('group', 'grp', {'osimage': 'img', 'interfaces': [{'interface': 'BOOTIF', 'network': 'cluster'}]}),
    'node': ('node', 'n001', {'group': 'grp'}),
    'switch': ('switch', 'sw', {'network': 'cluster', 'ipaddress': '10.141.250.250'}),
    'network': ('network', 'net2', {'network': '10.150.0.0/16'}),
    'rack': ('rack', 'rack1', {'size': 42}),
    'otherdevices': ('otherdev', 'pdu', {'network': 'cluster', 'ipaddress': '10.141.250.251'}),
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real routes over a fresh database holding one object of every kind."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper
    from cases.route_requirements_cases import app as routes_app

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in DBStructure().tables:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setitem(constant.CONSTANT, 'SERVICES', {'DHCP': 'dhcpd', 'DNS': 'named', 'COOLDOWN': '2', 'COMMAND': '/bin/true'})
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Database().insert('controller', Helper().make_rows({'hostname': 'controller', 'serverport': '7050', 'beacon': '1'}))
    app = routes_app()
    app.testing = True
    token = encode({'id': 0}, constant.CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(segment, name, fields):
        # a write that raises is what halts the journal; an answer, whatever its code, does not
        response = app.test_client().post(f'/config/{segment}/{name}', headers={'x-access-tokens': token},
                                          data=json.dumps({'config': {segment: {name: fields}}}), content_type='application/json')
        return response.status_code, response.get_data(as_text=True)
    for segment, name, fields in OBJECTS.values():
        code, text = post(segment, name, fields)
        assert code in (201, 204), (segment, text)
    yield post
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _columns(table):
    from utils.dbstructure import DBStructure
    return [column['column'] for column in DBStructure().get_database_table_structure(table)
            if column['column'] not in ('id', 'name')]


VALUES = (None, 5, 1.5, True, ['a'], {'a': 1})


@pytest.mark.parametrize('table', sorted(OBJECTS))
def test_no_value_in_a_column_makes_the_write_raise(client, table):
    segment, name, _ = OBJECTS[table]
    raised = []
    for column in _columns(table) + ['routes']:
        for value in VALUES:
            try:
                client(segment, name, {column: value})
            except Exception as exp:
                raised.append((column, value, type(exp).__name__))
    assert not raised


@pytest.mark.parametrize('table', ['group', 'node'])
@pytest.mark.parametrize('field', ['roles', 'scripts', 'profiles'])
def test_nothing_clears_a_text_field_and_a_number_is_refused(client, table, field):
    from utils.database import Database
    segment, name, _ = OBJECTS[table]
    known = {'roles': 'bond', 'scripts': 'raid1', 'profiles': None}[field]
    if known:
        assert client(segment, name, {field: known})[0] == 204
        assert Database().get_record(table=table, where=f"name = '{name}'")[0][field] == known
    assert client(segment, name, {field: None})[0] == 204
    assert not Database().get_record(table=table, where=f"name = '{name}'")[0][field]
    code, text = client(segment, name, {field: 5})
    assert code == 400 and '5 does not exist' in text
    assert not Database().get_record(table=table, where=f"name = '{name}'")[0][field]


@pytest.mark.parametrize('table', ['group', 'node', 'network'])
def test_routes_alone_are_coupled_and_nothing_clears_them(client, table):
    """A change that carries the routes and no column still couples them; nothing, like
    empty text, uncouples them all."""
    from utils.database import Database
    segment, name, _ = OBJECTS[table]
    assert client('route', 'r1', {'destination': '10.9.0.0/16', 'gateway': '10.141.0.1'})[0] == 201

    def coupled():
        return len(Database().get_record(table='routemap', where=f"tableref = '{table}'") or [])
    for clear in (None, ''):
        assert client(segment, name, {'routes': 'r1'})[0] == 204
        assert coupled() == 1
        assert client(segment, name, {'routes': clear})[0] == 204
        assert coupled() == 0
