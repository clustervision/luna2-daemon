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
    database.local_thread.connection = None
    for table in ['node', 'group', 'firmwarecatalog', 'firmwarerequest',
                  'nodeinventory', 'nodeinventoryfirmware', 'status']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
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
