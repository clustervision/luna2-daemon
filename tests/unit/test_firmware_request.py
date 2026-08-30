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
TRIX-1996a unit tests: asking for a firmware update, and reading what became of it.

The push records rather than flashes, so what these assert is what got written down
and what the operator was told. The two things worth pinning are that a group is
answered per node - one group holds more than one platform, so the members disagree
about what they need - and that a member which cannot be pushed to does not take the
rest of the group with it.

Status is read from those rows and not from inventory, which is a different question
answered elsewhere: inventory says what a node runs, these say what somebody asked
for and how it ended.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables these paths touch."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    files = tmp_path / 'files'
    files.mkdir()
    for name in ('fw.bin',):
        (files / name).write_bytes(b'firmware')
    original_files = constant.CONSTANT['FILES']['IMAGE_FILES']
    constant.CONSTANT['FILES']['IMAGE_FILES'] = str(files)
    database.local_thread.connection = None
    for table in ['node', 'group', 'firmwarecatalog', 'firmwarerequest',
                  'nodeinventory', 'nodeinventoryfirmware', 'status']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    constant.CONSTANT['FILES']['IMAGE_FILES'] = original_files
    database.local_thread.connection = None


def add_group(db, name):
    from utils.helper import Helper
    return db.insert('group', Helper().make_rows({'name': name}))


def add_node(db, name, manufacturer=None, model=None, groupid=None):
    from utils.helper import Helper
    nodeid = db.insert('node', Helper().make_rows({'name': name, 'groupid': groupid}))
    if manufacturer:
        db.insert('nodeinventory', Helper().make_rows(
            {'nodeid': nodeid, 'source': 'redfish',
             'manufacturer': manufacturer, 'product': model}))
    return nodeid


def add_running(db, nodeid, component, version):
    from utils.helper import Helper
    db.insert('nodeinventoryfirmware', Helper().make_rows(
        {'nodeid': nodeid, 'source': 'redfish', 'name': component,
         'component': component, 'version': version, 'updateable': 1}))


def add_entry(db, name, manufacturer, model, component, version):
    from utils.helper import Helper
    db.insert('firmwarecatalog', Helper().make_rows(
        {'name': name, 'manufacturer': manufacturer, 'model': model,
         'component': component, 'version': version, 'imagefile': 'fw.bin'}))


def push(object_type, name, **payload):
    from base.firmware import Firmware
    return Firmware().push_firmware(
        object_type=object_type, name=name,
        request_data={'config': {object_type: {name: dict(payload)}}})


def requests(db):
    return db.get_record(table='firmwarerequest') or []


def test_a_node_behind_the_catalogue_is_recorded(db):
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    returned = push('node', 'node001')
    assert returned[0] is True
    rows = requests(db)
    assert len(rows) == 1
    assert rows[0]['nodeid'] == nodeid
    assert rows[0]['status'] == 'queued'
    assert rows[0]['request_id'] == returned[2]


def test_a_node_already_at_the_catalogue_version_records_nothing(db):
    """Recording work that is not work would make a push of nothing look like one."""
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.10')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    status, response = push('node', 'node001')
    assert status is False
    assert 'Nothing to update' in response
    assert requests(db) == []


def test_a_node_the_catalogue_does_not_cover_is_refused_with_the_reason(db):
    from utils.firmware import NO_ENTRY

    add_node(db, 'node001', 'Supermicro', 'X13DEG')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    status, response = push('node', 'node001')
    assert status is False and NO_ENTRY in response


def test_a_node_whose_image_is_not_staged_is_refused_and_nothing_is_recorded(db):
    """
    Recording the request would put a node in the sweeper's hands with nothing to
    give the BMC; the failure would then arrive minutes later, per node, in the
    board's words. Refused here, in ours, with the file named.
    """
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    import os
    import common.constant as constant
    os.remove(os.path.join(constant.CONSTANT['FILES']['IMAGE_FILES'], 'fw.bin'))

    status, response = push('node', 'node001')
    assert status is False
    assert 'fw.bin' in response and 'not staged' in response
    assert requests(db) == []


def test_a_group_is_answered_per_node_and_one_bad_member_does_not_stop_it(db):
    """
    A group routinely holds more than one platform, and a node that never booted
    has no BMC either. Refusing the whole instruction for its sake is the wrong
    way round - the two that can be done are done, and the third is reported.
    """
    from utils.firmware import NO_INVENTORY

    groupid = add_group(db, 'compute')
    behind = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, behind, 'BMC', '7.00')
    current = add_node(db, 'node002', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, current, 'BMC', '7.10')
    other = add_node(db, 'node003', 'Supermicro', 'X13DEG', groupid)
    add_running(db, other, 'BMC', '1.00')
    add_node(db, 'node004', groupid=groupid)
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    add_entry(db, 'smcbmc', 'Supermicro', 'X13DEG', 'BMC', '1.05')

    returned = push('group', 'compute')
    assert returned[0] is True
    recorded = sorted(row['nodeid'] for row in requests(db))
    assert recorded == sorted([behind, other])
    assert '2 node(s)' in returned[1]
    assert '1 already as the catalogue asks' in returned[1]
    assert NO_INVENTORY in returned[1]


def test_a_named_component_only_records_the_nodes_that_need_that_one(db):
    groupid = add_group(db, 'compute')
    bios = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, bios, 'BMC', '7.10')
    add_running(db, bios, 'BIOS', '1.00')
    bmc = add_node(db, 'node002', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, bmc, 'BMC', '7.00')
    add_running(db, bmc, 'BIOS', '1.05')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    add_entry(db, 'dellbios', 'Dell Inc.', 'PowerEdge R650', 'BIOS', '1.05')

    returned = push('group', 'compute', component='BIOS')
    assert returned[0] is True
    rows = requests(db)
    assert [row['nodeid'] for row in rows] == [bios]
    assert rows[0]['component'] == 'BIOS'


def test_a_group_nobody_made_is_told_apart_from_one_nobody_filled(db):
    """Empty and non-existent want different answers; they read the same otherwise."""
    add_group(db, 'empty')
    status, response = push('group', 'empty')
    assert status is False and 'has no nodes' in response
    status, response = push('group', 'nosuchgroup')
    assert status is False and 'does not exist' in response


def test_status_says_nothing_was_asked_for_before_anything_is(db):
    from base.firmware import Firmware

    add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    status, response = Firmware().status()
    assert status is False and 'No firmware update' in response


def test_status_reports_the_newest_request_per_node(db):
    """
    Asking twice is deliberately not collapsed, so a node carries several rows.
    The one worth showing is the last one - an older 'failed' presented as the
    answer would report a machine as broken after somebody fixed it.
    """
    from base.firmware import Firmware
    from utils.firmware import FirmwareRequest

    groupid = add_group(db, 'compute')
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    push('node', 'node001')
    first = requests(db)[0]['id']
    FirmwareRequest().finish(requestid=first, status=False, message='board refused')
    push('node', 'node001')

    status, response = Firmware().status()
    assert status is True
    rows = response['config']['firmwarecatalog']['status']
    assert list(rows) == ['node001']
    assert rows['node001']['state'] == 'queued'
    assert rows['node001']['group'] == 'compute'
    assert response['config']['firmwarecatalog']['summary'] == {'queued': 1}


def test_status_keeps_a_restore_an_older_request_still_owes_in_view(db):
    """
    The newest request is the one shown, but a restore is owed by the node, not
    by the request whose flash left it owed. Shown per request it disappears the
    moment somebody asks again, and the admin then learns of the reset from the
    board. It stays until it settles.
    """
    from base.firmware import Firmware
    from utils.firmware import FirmwareRequest, RESTORE_PENDING

    groupid = add_group(db, 'compute')
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    push('node', 'node001')
    first = requests(db)[0]['id']
    FirmwareRequest().finish(requestid=first, status=True, message='flashed')
    FirmwareRequest().mark_restore(requestid=first)
    push('node', 'node001')
    second = requests(db)[1]['id']
    FirmwareRequest().finish(requestid=second, status=True, message='already there')

    _, response = Firmware().status()
    rows = response['config']['firmwarecatalog']['status']
    assert rows['node001']['request_id'] == requests(db)[1]['request_id']
    assert rows['node001']['restore'] == RESTORE_PENDING
    FirmwareRequest().finish_restore(requestid=first, status=True, message='BMC answers')
    _, response = Firmware().status()
    assert response['config']['firmwarecatalog']['status']['node001']['restore'] == ''


def test_status_carries_what_the_board_said_when_it_failed(db):
    from base.firmware import Firmware
    from utils.firmware import FirmwareRequest

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    push('node', 'node001')
    FirmwareRequest().finish(requestid=requests(db)[0]['id'], status=False,
                             message='the file name does not match')

    status, response = Firmware().status(name='node001')
    assert status is True
    row = response['config']['firmwarecatalog']['status']['node001']
    assert row['state'] == 'failed'
    assert 'file name' in row['message']


def test_status_scoped_to_a_group_leaves_the_rest_of_the_cluster_out(db):
    from base.firmware import Firmware

    groupid = add_group(db, 'compute')
    add_group(db, 'storage')
    inside = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650', groupid)
    add_running(db, inside, 'BMC', '7.00')
    outside = add_node(db, 'node002', 'Dell Inc.', 'PowerEdge R650',
                       add_group(db, 'login'))
    add_running(db, outside, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    push('node', 'node001')
    push('node', 'node002')

    status, response = Firmware().status(group='compute')
    assert status is True
    assert list(response['config']['firmwarecatalog']['status']) == ['node001']


def test_status_for_a_group_nobody_made_says_so(db):
    from base.firmware import Firmware

    status, response = Firmware().status(group='nosuchgroup')
    assert status is False and 'not available' in response


# ---------------------------------------------------------------------------
# Every write to the request table travels through the journal (HA)
# ---------------------------------------------------------------------------

def journaled(monkeypatch, answer=(True, 'Not in H/A mode')):
    """Records what would go to the peer, and answers as the journal would."""
    from utils.journal import Journal
    sent = []
    monkeypatch.setattr(Journal, 'add_request',
                        lambda self, function=None, object=None, param=None, payload=None, **k:
                        sent.append({'function': function, 'object': object, 'payload': payload}) or answer)
    return sent


def test_every_request_write_is_journaled_to_the_peer_and_applied_locally(db, monkeypatch):
    """
    The table is replicated, so its writes go through the journal - the hourly hash
    sweep is a last resort for a controller that was away, not the way a row travels.
    A node netbooting from the other controller inside that hour would otherwise be
    told nothing is owed.
    """
    from utils.firmware import FirmwareRequest, RESTORE_PENDING
    sent = journaled(monkeypatch)
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    requests_ = FirmwareRequest()
    assert requests_.record(nodeids=[nodeid], component='BMC', request_id='r1') == 1
    row = requests(db)[0]
    requests_.claim(row['id']); requests_.mark_restore(row['id'])
    requests_.finish(row['id'], True, 'flashed'); requests_.finish_restore(row['id'], False, 'no settings object')
    assert [s['function'] for s in sent] == ['Firmware.replay_request'] * 5
    assert [s['object'] for s in sent] == ['record', 'update', 'update', 'update', 'update']
    # addressed by what both controllers share, never by the local autoincrement
    for s in sent[1:]:
        assert s['payload']['request_id'] == 'r1' and s['payload']['nodeid'] == nodeid and 'id' not in s['payload']
    row = requests(db)[0]
    assert (row['status'], row['message'], row['restore']) == ('done', 'flashed', 'failed: no settings object')


def test_a_write_the_peer_did_not_take_is_not_written_locally_either(db, monkeypatch):
    """A controller that is not in sync must not write what it cannot replicate."""
    from utils.firmware import FirmwareRequest
    journaled(monkeypatch, answer=(False, 'not in sync'))
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    assert FirmwareRequest().record(nodeids=[nodeid], component='BMC', request_id='r1') == 0
    assert requests(db) == []


def test_the_peer_replays_the_write_onto_its_own_row(db, monkeypatch):
    """What the journal hands the peer reproduces the row there - keyed on
    (request_id, nodeid), since the peer's id is its own."""
    from base.firmware import Firmware
    from utils.firmware import RESTORE_PENDING
    journaled(monkeypatch)
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    Firmware().replay_request('record', {'nodeid': nodeid, 'component': 'BMC', 'request_id': 'r9'})
    Firmware().replay_request('update', {'request_id': 'r9', 'nodeid': nodeid, 'restore': RESTORE_PENDING})
    row = requests(db)[0]
    assert (row['request_id'], row['status'], row['restore']) == ('r9', 'queued', RESTORE_PENDING)


def test_a_request_whose_claim_was_refused_is_not_flashed_and_stays_queued(db, monkeypatch):
    """
    The claim travels through the journal, and a controller out of sync is refused.
    Flashing anyway would leave the row queued while the node was flashed, and the
    next sweep would take it up and flash it again - for as long as the pair stayed
    out of sync, and against the stored inventory, which still says the old version.
    So a request that cannot be claimed is left alone, and said so.
    """
    from threading import Event
    from utils.firmware import FirmwareRequest, QUEUED
    from utils.firmware_push import FirmwarePush
    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    journaled(monkeypatch)
    assert FirmwareRequest().record(nodeids=[nodeid], component='BMC', request_id='r1') == 1
    journaled(monkeypatch, answer=(False, 'not in sync'))
    flashed = []
    monkeypatch.setattr(FirmwarePush, 'sweep_batches',
                        lambda self, pipeline, requests=None: flashed.append(pipeline.get_nodes()))
    stop = Event()
    stop.set()
    FirmwarePush().sweep_mother(stop)
    assert flashed == []
    row = requests(db)[0]
    assert (row['request_id'], row['status']) == ('r1', QUEUED)
