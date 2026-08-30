
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
TRIX-1996a unit tests: what the firmware catalogue says about a node.

Every answer here comes from stored inventory, so all of it is testable with no BMC
and no hardware - which is the point of putting the decision here rather than in the
push. A machine that is switched off gets the same answer as one that is running.

The cases that matter are the ones where a node is NOT a candidate, because those
are what a group instruction meets most of: a node that has never booted has no
inventory and almost certainly no BMC either, so it is not a failure to report but
work not worth attempting.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the catalogue and inventory tables."""
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
    for table in ['node', 'group', 'firmwarecatalog', 'nodeinventory',
                  'nodeinventoryfirmware']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    constant.CONSTANT['FILES']['IMAGE_FILES'] = original_files
    database.local_thread.connection = None


def add_node(db, name, manufacturer=None, model=None, source='redfish'):
    """A node, with an inventory snapshot only where a hardware pair is given."""
    from utils.helper import Helper
    nodeid = db.insert('node', Helper().make_rows({'name': name}))
    if manufacturer:
        db.insert('nodeinventory', Helper().make_rows(
            {'nodeid': nodeid, 'source': source,
             'manufacturer': manufacturer, 'product': model}))
    return nodeid


def add_running(db, nodeid, component, version, source='redfish', updateable=1):
    from utils.helper import Helper
    db.insert('nodeinventoryfirmware', Helper().make_rows(
        {'nodeid': nodeid, 'source': source, 'name': component,
         'component': component, 'version': version, 'updateable': updateable}))


def add_entry(db, name, manufacturer, model, component, version, imagefile='fw.bin'):
    from utils.helper import Helper
    db.insert('firmwarecatalog', Helper().make_rows(
        {'name': name, 'manufacturer': manufacturer, 'model': model,
         'component': component, 'version': version, 'imagefile': imagefile}))


def test_a_node_that_has_never_booted_is_not_a_candidate(db):
    """No inventory means no BMC was ever configured, so there is nothing to reach."""
    from utils.firmware import FirmwareCatalog, NO_INVENTORY

    add_node(db, 'never')
    assert FirmwareCatalog().plan(nodename='never') == (False, NO_INVENTORY)


def test_hardware_with_no_catalogue_entry_is_reported_not_guessed(db):
    from utils.firmware import FirmwareCatalog, NO_ENTRY

    add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    assert FirmwareCatalog().plan(nodename='node001') == (False, NO_ENTRY)


def test_an_entry_with_no_version_refuses_rather_than_pushing_blind(db):
    """A flash we cannot verify afterwards is one we can say nothing true about."""
    from utils.firmware import FirmwareCatalog, NO_VERSION

    add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_entry(db, 'bmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '')
    assert FirmwareCatalog().plan(nodename='node001') == (False, NO_VERSION)


def test_the_vendor_need_not_be_spelled_the_way_the_board_spells_it(db):
    """'Dell' in the catalogue has to match a board saying 'Dell Inc.'."""
    from utils.firmware import FirmwareCatalog

    add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_entry(db, 'bmc', 'Dell', 'PowerEdge R650', 'BMC', '7.10')
    status, answer = FirmwareCatalog().plan(nodename='node001')
    assert status is True and len(answer['components']) == 1


def test_a_node_already_on_the_catalogue_version_is_not_work(db):
    from utils.firmware import FirmwareCatalog

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.10')
    add_entry(db, 'bmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    status, answer = FirmwareCatalog().plan(nodename='node001')
    assert status is True
    assert answer['differs'] == []


def test_a_node_behind_the_catalogue_is_work(db):
    from utils.firmware import FirmwareCatalog

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'bmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    status, answer = FirmwareCatalog().plan(nodename='node001')
    assert status is True
    assert [item['component'] for item in answer['differs']] == ['BMC']
    assert answer['differs'][0]['running'] == '7.00'


def test_a_component_the_node_has_never_reported_counts_as_work(db):
    """An absent version is not a match. Nothing is known, so it cannot be right."""
    from utils.firmware import FirmwareCatalog

    add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_entry(db, 'bmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    status, answer = FirmwareCatalog().plan(nodename='node001')
    assert answer['differs'][0]['running'] is None


def test_redfish_wins_over_an_in_band_answer_for_the_same_component(db):
    from utils.firmware import FirmwareCatalog

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '6.00', source='dmidecode')
    add_running(db, nodeid, 'BMC', '7.10', source='redfish')
    assert FirmwareCatalog().running(nodename='node001')['BMC']['version'] == '7.10'


def test_a_mixed_group_is_answered_per_node(db):
    """
    The case the whole design turns on: one group, three platforms, one instruction.
    Each node is resolved from its own hardware, and the ones that are not candidates
    do not stop the one that is.
    """
    from utils.firmware import FirmwareCatalog, NO_INVENTORY, NO_ENTRY

    dell = add_node(db, 'dell01', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, dell, 'BMC', '7.00')
    add_node(db, 'super01', 'Supermicro', 'X13DEG')
    add_node(db, 'never01')
    add_node(db, 'never02')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    answer = FirmwareCatalog().preview(
        nodenames=['dell01', 'super01', 'never01', 'never02'])
    assert [item['node'] for item in answer['ready']] == ['dell01']
    assert answer['skipped'] == {NO_ENTRY: ['super01'],
                                 NO_INVENTORY: ['never01', 'never02']}


def test_the_summary_groups_by_cause_rather_than_listing_nodes(db):
    """At four thousand nodes a line each is a wall. The causes are few."""
    from utils.firmware import FirmwareCatalog

    for index in range(50):
        add_node(db, f'never{index:03d}')
    dell = add_node(db, 'dell01', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, dell, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')

    names = [f'never{index:03d}' for index in range(50)] + ['dell01']
    summary = FirmwareCatalog().preview(nodenames=names)['summary']
    assert len(summary) == 2
    assert summary[0] == '1 node(s) would change, 0 already as the catalogue asks'
    assert summary[1].startswith('50 skipped: no inventory')


def test_an_entry_whose_image_is_not_staged_is_skipped_and_the_file_is_named(db):
    """
    The row is a pointer and nothing checks it points anywhere. Without this a
    dry run says 'would change' and the BMC discovers the truth ('file is
    missing') minutes later, one node at a time.
    """
    from utils.firmware import FirmwareCatalog, NO_IMAGE

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10',
              imagefile='not-scped-yet.bin')

    status, reason = FirmwareCatalog().plan(nodename='node001')
    assert status is False
    assert reason == NO_IMAGE.format(imagefile='not-scped-yet.bin')
    assert 'not-scped-yet.bin' in reason, 'the operator has to know which file to stage'


def test_an_entry_naming_no_image_at_all_is_skipped_before_a_push(db):
    from utils.firmware import FirmwareCatalog, NO_IMAGEFILE

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10', imagefile='')

    assert FirmwareCatalog().plan(nodename='node001') == (False, NO_IMAGEFILE)


def test_a_node_already_on_the_catalogue_version_does_not_need_the_image(db):
    """
    An image is needed to flash, not to compare. Once a fleet is on the catalogue
    version the file may go; the nodes are still 'as the catalogue asks'.
    """
    from utils.firmware import FirmwareCatalog

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.10')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10',
              imagefile='long-gone.bin')

    status, answer = FirmwareCatalog().plan(nodename='node001')
    assert status is True and answer['differs'] == []


def test_a_preview_lists_the_image_directory_once_not_once_per_node(db, monkeypatch):
    """
    Four thousand nodes times a few components is twelve thousand stats a dry run
    if each plan looks for itself. One listing answers for all of them.
    """
    import os
    from utils.firmware import FirmwareCatalog

    for name in ('node001', 'node002', 'node003'):
        nodeid = add_node(db, name, 'Dell Inc.', 'PowerEdge R650')
        add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    listings = []
    real = os.listdir
    monkeypatch.setattr(os, 'listdir', lambda path: listings.append(path) or real(path))

    answer = FirmwareCatalog().preview(nodenames=['node001', 'node002', 'node003'])
    assert len(answer['ready']) == 3
    assert len(listings) == 1


def test_an_unreadable_image_directory_stages_nothing_and_does_not_crash(db):
    import common.constant as constant
    from utils.firmware import FirmwareCatalog, NO_IMAGE

    nodeid = add_node(db, 'node001', 'Dell Inc.', 'PowerEdge R650')
    add_running(db, nodeid, 'BMC', '7.00')
    add_entry(db, 'dellbmc', 'Dell Inc.', 'PowerEdge R650', 'BMC', '7.10')
    constant.CONSTANT['FILES']['IMAGE_FILES'] += '/does-not-exist'

    assert FirmwareCatalog().plan(nodename='node001') == (
        False, NO_IMAGE.format(imagefile='fw.bin'))
