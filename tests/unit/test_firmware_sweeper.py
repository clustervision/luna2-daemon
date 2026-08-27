
# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TRIX-1996a unit tests: the firmware sweeper and the request it sweeps.

A request is a stored instruction, not a derived state, and these tests are mostly
about the difference. What the catalogue says a node should run is derivable at any
moment; that somebody ASKED for it is not, and it has to survive a controller
failing over, a daemon restarting, and a sweep claiming it and then dying.

The selection is asserted to be one query rather than one per node, because the whole
argument for a sweeper is that finding the work does not get more expensive as the
cluster does.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables the sweeper touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['node', 'group', 'firmwarecatalog', 'firmwarerequest',
                  'nodeinventory', 'nodeinventoryfirmware', 'queue',
                  'network', 'nodeinterface', 'ipaddress', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def nodes(db):
    """Three nodes; only the first has inventory and a catalogue entry behind it."""
    from utils.helper import Helper

    ids = {}
    for name in ('node001', 'node002', 'node003'):
        ids[name] = db.insert('node', Helper().make_rows({'name': name}))
    db.insert('nodeinventory', Helper().make_rows(
        {'nodeid': ids['node001'], 'source': 'redfish',
         'manufacturer': 'Dell Inc.', 'product': 'PowerEdge R650'}))
    db.insert('nodeinventoryfirmware', Helper().make_rows(
        {'nodeid': ids['node001'], 'source': 'redfish', 'name': 'BMC',
         'component': 'BMC', 'version': '7.00', 'updateable': 1}))
    db.insert('firmwarecatalog', Helper().make_rows(
        {'name': 'dellbmc', 'manufacturer': 'Dell Inc.', 'model': 'PowerEdge R650',
         'component': 'BMC', 'version': '7.10', 'imagefile': 'bmc.bin'}))
    return ids


def test_a_request_is_written_per_node(db, nodes):
    from utils.firmware import FirmwareRequest, QUEUED

    written = FirmwareRequest().record(nodeids=list(nodes.values()), request_id='r1')
    assert written == 3
    rows = db.get_record(table='firmwarerequest', where=f'status="{QUEUED}"')
    assert len(rows) == 3


def test_asking_twice_records_twice(db, nodes):
    """
    Not collapsed on purpose: the operator asked again, and the catalogue or the
    machine may well have moved on since the first time.
    """
    from utils.firmware import FirmwareRequest

    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r1')
    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r2')
    assert len(db.get_record(table='firmwarerequest') or []) == 2


def test_the_whole_sweep_is_one_query(db, nodes):
    """
    The argument for a sweeper is that finding the work does not get more expensive
    as the cluster does. A selection that costs a round trip per node would give that
    away, so the count is asserted rather than assumed.
    """
    from utils.database import Database
    from utils.firmware import FirmwareRequest

    FirmwareRequest().record(nodeids=list(nodes.values()), request_id='r1')

    calls = {'n': 0}
    real_join = Database.get_record_join
    def counting(self, *a, **k):
        calls['n'] += 1
        return real_join(self, *a, **k)
    Database.get_record_join = counting
    try:
        pending = FirmwareRequest().pending()
    finally:
        Database.get_record_join = real_join

    assert len(pending) == 3
    assert calls['n'] == 1, 'the sweep selection should be one query for the whole cluster'
    assert {row['nodename'] for row in pending} == {'node001', 'node002', 'node003'}


def test_a_claim_marks_rather_than_deletes(db, nodes):
    """
    A request removed when claimed is lost if the daemon stops mid-flash, and the
    node is left part-updated with nothing recording that anybody asked.
    """
    from utils.firmware import FirmwareRequest, CLAIMED

    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r1')
    row = FirmwareRequest().pending()[0]
    FirmwareRequest().claim(row['id'])
    assert FirmwareRequest().pending() == []
    still_there = db.get_record(table='firmwarerequest', where=f'id="{row["id"]}"')
    assert still_there and still_there[0]['status'] == CLAIMED


def test_a_claim_a_stopped_daemon_left_behind_is_taken_up_again(db, nodes):
    from utils.database import Database
    from utils.helper import Helper
    from utils.firmware import FirmwareRequest, CLAIMED

    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r1')
    row = FirmwareRequest().pending()[0]
    FirmwareRequest().claim(row['id'])
    # age the claim past the window the way a daemon that stopped would leave it
    Database().update('firmwarerequest',
                      Helper().make_rows({'status': CLAIMED, 'updated': 'NOW -120 minute'}),
                      [{"column": "id", "value": row['id']}])
    assert FirmwareRequest().reclaim_abandoned(minutes=60)
    assert [r['id'] for r in FirmwareRequest().pending()] == [row['id']]


def test_a_fresh_claim_is_not_reclaimed(db, nodes):
    """The reclaim must not steal work from a sweep that is still running it."""
    from utils.firmware import FirmwareRequest

    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r1')
    FirmwareRequest().claim(FirmwareRequest().pending()[0]['id'])
    assert FirmwareRequest().reclaim_abandoned(minutes=60) == []


def test_how_a_request_ended_is_kept_for_the_status_view(db, nodes):
    from utils.firmware import FirmwareRequest

    FirmwareRequest().record(nodeids=[nodes['node001']], request_id='r1')
    row = FirmwareRequest().pending()[0]
    FirmwareRequest().finish(row['id'], False, 'the board refused')
    kept = db.get_record(table='firmwarerequest', where=f'id="{row["id"]}"')[0]
    assert kept['status'] == 'failed' and 'refused' in kept['message']


def test_a_node_the_catalogue_does_not_cover_is_declined_before_any_connection(db, nodes):
    """
    node002 has no inventory, so it has no hardware to match and almost certainly no
    BMC either. Declining here costs nothing; a connection would cost a timeout.
    """
    from utils.firmware_push import FirmwarePush

    status, message = FirmwarePush().update_node({'nodename': 'node002'})
    assert status is False and 'no inventory' in message


def test_a_node_already_on_the_catalogue_version_is_not_work(db, nodes):
    from utils.database import Database
    from utils.helper import Helper
    from utils.firmware_push import FirmwarePush

    Database().update('nodeinventoryfirmware', Helper().make_rows({'version': '7.10'}),
                      [{"column": "nodeid", "value": nodes['node001']}])
    status, message = FirmwarePush().update_node({'nodename': 'node001'})
    assert status is True and 'already running' in message


def test_the_batch_size_has_a_default_and_can_be_configured(db):
    """A flash is the heaviest thing a BMC does, so the batch protects the far end."""
    import common.constant as constant
    from utils.firmware_push import FirmwarePush, DEFAULT_BATCH

    assert FirmwarePush().batch_settings() == (DEFAULT_BATCH, 0)
    constant.CONSTANT['FIRMWARE'] = {'FIRMWARE_BATCH_SIZE': '4', 'FIRMWARE_BATCH_DELAY': '2s'}
    try:
        assert FirmwarePush().batch_settings() == (4, 2)
    finally:
        del constant.CONSTANT['FIRMWARE']


def test_the_image_url_uses_the_address_that_faces_the_bmc(db):
    """
    Derived from the route rather than from configuration or from the database. The
    database cannot answer it: a controller has one ipaddress row and it is the
    cluster one, so on a cluster whose BMCs have their own network there is nothing
    stored that says which address faces them.

    Asked against the loopback, which is the one destination whose answer is knowable
    without a network.
    """
    from utils.firmware_push import FirmwarePush

    status, url = FirmwarePush().image_url(device='127.0.0.1', imagefile='bmc-7.10.bin')
    assert status is True
    assert url == 'http://127.0.0.1:7051/files/bmc-7.10.bin'


def test_the_webserver_settings_are_honoured(db):
    import common.constant as constant
    from utils.firmware_push import FirmwarePush

    constant.CONSTANT['WEBSERVER'] = {'PROTOCOL': 'https', 'PORT': '8443'}
    try:
        _, url = FirmwarePush().image_url(device='127.0.0.1', imagefile='bmc.bin')
        assert url == 'https://127.0.0.1:8443/files/bmc.bin'
    finally:
        del constant.CONSTANT['WEBSERVER']


def test_a_bmc_with_no_route_is_refused_with_the_reason(db):
    """An address the kernel cannot route to has nowhere to fetch from."""
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().image_url(device='2001:db8::1', imagefile='bmc.bin')
    assert status is False
    assert 'no route' in reason or 'no address facing' in reason


def test_an_entry_with_no_image_file_is_refused_before_anything_is_contacted(db):
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().image_url(device='127.0.0.1', imagefile=None)
    assert status is False and 'no image file' in reason
