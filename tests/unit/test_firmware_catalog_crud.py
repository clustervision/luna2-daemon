
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
TRIX-1996a unit tests: the catalogue as an operator handles it.

A catalogue entry is written rather than grabbed, which is the opposite of a BIOS
configuration, so the interesting cases are about refusing an entry that cannot do
its job - one that names no hardware, no component or no version can never select a
node, and a row that can never select a node is one nobody will notice is wrong.
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
    (files / 'bmc-7.10.bin').write_bytes(b'firmware')
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


def entry(name, **fields):
    """Create or change an entry through the real path."""
    from base.firmware import Firmware
    record = dict(fields)
    return Firmware().update_firmware(
        name, {'config': {'firmwarecatalog': {name: record}}})


COMPLETE = {'manufacturer': 'Dell Inc.', 'model': 'PowerEdge R650',
            'component': 'BMC', 'version': '7.10', 'imagefile': 'bmc-7.10.bin'}


def test_a_complete_entry_is_created(db):
    status, response = entry('dellbmc', **COMPLETE)
    assert status is True and 'created' in response
    assert db.get_record(table='firmwarecatalog', where='name = "dellbmc"')


def test_an_entry_that_could_never_select_a_node_is_refused(db):
    """
    Each of these is what makes an entry addressable. Without them the row sits in
    the catalogue matching nothing, which is worse than not existing because it
    looks like coverage.
    """
    for field in ('manufacturer', 'model', 'component', 'version'):
        fields = dict(COMPLETE)
        del fields[field]
        status, response = entry(f'missing-{field}', **fields)
        assert status is False, f'an entry with no {field} was accepted'
        assert field in response
        assert not db.get_record(table='firmwarecatalog', where=f'name = "missing-{field}"')


def test_the_refusal_names_everything_that_is_missing_at_once(db):
    """One round trip should be enough to learn what an entry needs."""
    status, response = entry('bare', imagefile='x.bin')
    assert status is False
    for field in ('manufacturer', 'model', 'component', 'version'):
        assert field in response


def test_an_image_file_is_a_bare_name_because_it_becomes_a_url_path(db):
    """
    The value is handed to a BMC as '/files/<imagefile>'. A path in it either
    walks out of the served directory or names a file nothing will find; neither
    is a catalogue entry.
    """
    for bad in ('../etc/passwd', 'sub/bmc.bin', '/bmc.bin'):
        fields = dict(COMPLETE, imagefile=bad)
        status, response = entry('dellbmc', **fields)
        assert status is False, f'{bad!r} was accepted as an image file'
        assert 'bare file name' in response
    assert not db.get_record(table='firmwarecatalog', where='name = "dellbmc"')


def test_an_image_named_like_an_os_image_is_refused_because_a_bmc_has_no_token(db):
    """
    The file server asks for a token only for the extensions an OS image wears.
    A BMC cannot present one, so a firmware image with such a name would be
    refused at fetch time with the board's 'file is missing' - say it here.
    """
    from base.authentication import TOKEN_GATED_EXTENSIONS

    assert TOKEN_GATED_EXTENSIONS, 'the gated set the check reads is empty'
    for ext in TOKEN_GATED_EXTENSIONS:
        fields = dict(COMPLETE, imagefile=f'bmc-7.10{ext}')
        status, response = entry('dellbmc', **fields)
        assert status is False, f'*{ext} was accepted as an image file'
        assert ext in response and 'token' in response
    assert not db.get_record(table='firmwarecatalog', where='name = "dellbmc"')


def test_a_change_that_names_a_bad_image_file_is_refused_too(db):
    entry('dellbmc', **COMPLETE)
    status, response = entry('dellbmc', imagefile='../bmc.bin')
    assert status is False
    row = db.get_record(table='firmwarecatalog', where='name = "dellbmc"')[0]
    assert row['imagefile'] == 'bmc-7.10.bin'


def test_naming_an_image_file_reminds_where_to_stage_it_and_that_the_bmc_must_reach_it(db):
    """
    The admin is told at the moment they set the entry up - not by the board, forty
    minutes into a push, in the words 'file is missing'. The reminder is Luna's own
    facts: the directory, the port. Whether the firewall allows it is the
    installer's business, so the note says what must be true, not whether it is.
    """
    import common.constant as constant
    status, response = entry('dellbmc', **COMPLETE)
    assert status is True
    assert 'bmc-7.10.bin' in response
    assert constant.CONSTANT['FILES']['IMAGE_FILES'] in response
    assert 'port 7051' in response and 'trusted zone' in response


def test_a_change_that_sets_the_image_file_carries_the_reminder_and_one_that_does_not_does_not(db):
    entry('dellbmc', **COMPLETE)
    status, response = entry('dellbmc', imagefile='bmc-7.20.bin')
    assert status is True and 'stage bmc-7.20.bin' in response
    status, response = entry('dellbmc', version='7.20')
    assert status is True and 'stage' not in response


def test_an_existing_entry_can_be_changed_without_resupplying_everything(db):
    """A change is a change, not a re-creation: the required fields are already set."""
    entry('dellbmc', **COMPLETE)
    status, response = entry('dellbmc', version='7.20')
    assert status is True and 'updated' in response
    row = db.get_record(table='firmwarecatalog', where='name = "dellbmc"')[0]
    assert row['version'] == '7.20'
    assert row['model'] == 'PowerEdge R650'


def test_reading_back_what_was_written(db):
    from base.firmware import Firmware

    entry('dellbmc', **COMPLETE)
    status, response = Firmware().get_firmware('dellbmc')
    assert status is True
    detail = response['config']['firmwarecatalog']['dellbmc']
    assert detail['version'] == '7.10' and detail['name'] == 'dellbmc'
    assert 'id' not in detail


def test_an_entry_that_is_not_there(db):
    from base.firmware import Firmware

    assert Firmware().get_firmware('nosuch')[0] is False
    assert Firmware().get_all_firmware()[0] is False
    assert Firmware().delete_firmware('nosuch')[0] is False


def test_an_entry_can_be_removed(db):
    from base.firmware import Firmware

    entry('dellbmc', **COMPLETE)
    status, response = Firmware().delete_firmware('dellbmc')
    assert status is True and 'removed' in response
    assert not db.get_record(table='firmwarecatalog', where='name = "dellbmc"')


def test_a_group_is_expanded_now_rather_than_carried_as_a_group(db):
    """
    Read at the edge, so a node added to the group after the operator looked is not
    silently included in something they did not see.
    """
    from base.firmware import Firmware
    from utils.helper import Helper

    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    for name in ('node001', 'node002'):
        db.insert('node', Helper().make_rows({'name': name, 'groupid': groupid}))
    status, targets = Firmware().targets(object_type='group', name='compute')
    assert status is True and sorted(targets) == ['node001', 'node002']


def test_a_group_that_does_not_exist_is_not_an_empty_group(db):
    """
    'group' is a reserved SQL word, and a where clause naming it fails in a way the
    daemon logs and swallows - so a broken query and a genuinely empty group look
    identical to the caller unless the lookup is done the long way.
    """
    from base.firmware import Firmware
    from utils.helper import Helper

    status, response = Firmware().targets(object_type='group', name='nosuch')
    assert status is False and 'does not exist' in response

    db.insert('group', Helper().make_rows({'name': 'empty'}))
    status, response = Firmware().targets(object_type='group', name='empty')
    assert status is False and 'has no nodes' in response


def test_the_preview_answers_for_a_whole_group_without_contacting_anything(db):
    from base.firmware import Firmware
    from utils.helper import Helper

    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    dell = db.insert('node', Helper().make_rows({'name': 'dell01', 'groupid': groupid}))
    db.insert('node', Helper().make_rows({'name': 'never01', 'groupid': groupid}))
    db.insert('nodeinventory', Helper().make_rows(
        {'nodeid': dell, 'source': 'redfish',
         'manufacturer': 'Dell Inc.', 'product': 'PowerEdge R650'}))
    db.insert('nodeinventoryfirmware', Helper().make_rows(
        {'nodeid': dell, 'source': 'redfish', 'name': 'BMC',
         'component': 'BMC', 'version': '7.00', 'updateable': 1}))
    entry('dellbmc', **COMPLETE)

    status, response = Firmware().preview(object_type='group', name='compute')
    assert status is True
    answer = response['config']['firmware']['preview']
    assert [item['node'] for item in answer['ready']] == ['dell01']
    assert any('no inventory' in reason for reason in answer['skipped'])
    assert answer['summary'][0].startswith('1 node(s) would change')
