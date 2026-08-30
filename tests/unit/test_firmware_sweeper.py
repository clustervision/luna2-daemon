
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
    files = tmp_path / 'files'
    files.mkdir()
    for name in ('bmc.bin', 'bmc-7.10.bin', 'bios.bin',):
        (files / name).write_bytes(b'firmware')
    original_files = constant.CONSTANT['FILES']['IMAGE_FILES']
    constant.CONSTANT['FILES']['IMAGE_FILES'] = str(files)
    database.local_thread.connection = None
    for table in ['node', 'group', 'firmwarecatalog', 'firmwarerequest',
                  'nodeinventory', 'nodeinventoryfirmware', 'queue',
                  'network', 'nodeinterface', 'ipaddress', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    constant.CONSTANT['FILES']['IMAGE_FILES'] = original_files
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


def bmc_on_network(db, nodeid, network='ipmi', address='10.148.0.1'):
    """Give a node a BMC address on a Luna network, the way an install would."""
    from utils.helper import Helper

    netid = db.insert('network', Helper().make_rows(
        {'name': network, 'network': '10.148.0.0', 'subnet': '16'}))
    interface = db.insert('nodeinterface', Helper().make_rows(
        {'nodeid': nodeid, 'interface': 'BMC'}))
    db.insert('ipaddress', Helper().make_rows(
        {'tableref': 'nodeinterface', 'tablerefid': interface,
         'ipaddress': address, 'networkid': netid}))
    return netid


def controller_addresses(monkeypatch, mapping):
    """Stand in for the walk of this machine's own interfaces."""
    from utils.helper import Helper

    monkeypatch.setattr(Helper, 'get_controller_addresses_for_networks',
                        lambda self: mapping)


def test_the_image_url_uses_the_controller_address_on_the_bmc_network(db, nodes, monkeypatch):
    """
    The BMC is on the management network, so it can only reach the controller on the
    controller's address there - not the cluster one, which is a different interface
    and unroutable from a BMC.
    """
    from utils.firmware_push import FirmwarePush

    bmc_on_network(db, nodes['node001'])
    controller_addresses(monkeypatch, {'ipv4': {'ipmi': '10.148.255.254',
                                                'cluster': '10.141.255.254'},
                                       'ipv6': {}})
    status, url = FirmwarePush().image_url(nodename='node001', imagefile='bmc-7.10.bin')
    assert status is True
    assert url == 'http://10.148.255.254:7051/files/bmc-7.10.bin'
    assert '10.141.255.254' not in url, 'the BMC was handed an address it cannot reach'


def test_a_network_this_controller_has_no_address_on_is_refused(db, nodes, monkeypatch):
    from utils.firmware_push import FirmwarePush

    bmc_on_network(db, nodes['node001'])
    controller_addresses(monkeypatch, {'ipv4': {'cluster': '10.141.255.254'}, 'ipv6': {}})
    status, reason = FirmwarePush().image_url(nodename='node001', imagefile='bmc.bin')
    assert status is False and 'nowhere to fetch from' in reason


def test_an_ipv6_address_is_bracketed_for_a_url(db, nodes, monkeypatch):
    from utils.firmware_push import FirmwarePush

    bmc_on_network(db, nodes['node001'])
    controller_addresses(monkeypatch, {'ipv4': {}, 'ipv6': {'ipmi': 'fd00::254'}})
    status, url = FirmwarePush().image_url(nodename='node001', imagefile='bmc.bin')
    assert status is True and url.startswith('http://[fd00::254]:7051/')


def test_a_node_with_no_bmc_on_a_known_network_is_refused(db, nodes):
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().image_url(nodename='node001', imagefile='bmc.bin')
    assert status is False and 'no BMC address on a network Luna knows' in reason


def test_the_webserver_settings_are_honoured(db, nodes, monkeypatch):
    import common.constant as constant
    from utils.firmware_push import FirmwarePush

    bmc_on_network(db, nodes['node001'])
    controller_addresses(monkeypatch, {'ipv4': {'ipmi': '10.148.255.254'}, 'ipv6': {}})
    constant.CONSTANT['WEBSERVER'] = {'PROTOCOL': 'https', 'PORT': '8443'}
    try:
        _, url = FirmwarePush().image_url(nodename='node001', imagefile='bmc.bin')
        assert url == 'https://10.148.255.254:8443/files/bmc.bin'
    finally:
        del constant.CONSTANT['WEBSERVER']


def test_an_entry_with_no_image_file_is_refused_before_anything_is_contacted(db, nodes):
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().image_url(nodename='node001', imagefile=None)
    assert status is False and 'no image file' in reason


def test_an_image_that_is_gone_by_flash_time_is_refused_before_the_bmc_is_asked(db, nodes, monkeypatch):
    """
    The dry run checked; the sweep runs later, and the file can have gone in
    between. The BMC would report 'file is missing' after fetching nothing - this
    says so first, in the same words the preview uses.
    """
    from utils.firmware_push import FirmwarePush

    bmc_on_network(db, nodes['node001'])
    controller_addresses(monkeypatch, {'ipv4': {'ipmi': '10.148.255.254'}, 'ipv6': {}})
    status, reason = FirmwarePush().image_url(nodename='node001', imagefile='gone.bin')
    assert status is False
    assert 'gone.bin' in reason and 'not staged' in reason


def test_the_walk_pairs_every_local_address_with_its_luna_network(db, monkeypatch):
    """
    The primitive both this and the per-network DNS zone need: which of this
    machine's own addresses is on which Luna network. A controller has one ipaddress
    row and it is the cluster one, so the rest are known only to the kernel.

    The interfaces below are the shape TRIX-1946 reports: one NIC carrying two
    addresses on two networks, and a separate InfiniBand NIC. Picking the wrong one
    is what makes controller.ib resolve to an ethernet address.
    """
    import utils.helper as helper_module
    from utils.helper import Helper

    for name, network, subnet in (('cluster', '10.131.0.0', '16'),
                                  ('ipmi', '10.138.0.0', '16'),
                                  ('ib', '10.139.0.0', '16')):
        db.insert('network', Helper().make_rows(
            {'name': name, 'network': network, 'subnet': subnet}))

    fake = {
        'lo': {2: [{'addr': '127.0.0.1'}]},
        'enp2s0f0np0': {2: [{'addr': '10.131.255.254'}, {'addr': '10.138.255.254'}]},
        'ibp129s0': {2: [{'addr': '10.139.1.102'}]},
    }
    monkeypatch.setattr(helper_module.ni, 'interfaces', lambda: list(fake))
    monkeypatch.setattr(helper_module.ni, 'ifaddresses', lambda name: fake[name])

    found = Helper().get_controller_addresses_for_networks()['ipv4']
    assert found['cluster'] == '10.131.255.254'
    assert found['ipmi'] == '10.138.255.254'
    assert found['ib'] == '10.139.1.102', 'the InfiniBand network took an ethernet address'


def test_an_address_on_no_luna_network_is_ignored(db, monkeypatch):
    """A controller carries addresses Luna knows nothing about; they are not answers."""
    import utils.helper as helper_module
    from utils.helper import Helper

    db.insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.131.0.0', 'subnet': '16'}))
    fake = {'enp2s0f1np1': {2: [{'addr': '172.25.3.10'}]},
            'enp2s0f0np0': {2: [{'addr': '10.131.255.254'}]}}
    monkeypatch.setattr(helper_module.ni, 'interfaces', lambda: list(fake))
    monkeypatch.setattr(helper_module.ni, 'ifaddresses', lambda name: fake[name])

    found = Helper().get_controller_addresses_for_networks()['ipv4']
    assert found == {'cluster': '10.131.255.254'}


# --- TRIX-2035: a flash that resets the BMC tells the operator, and reboots nothing ---

def test_the_reconfigure_note_fires_only_for_a_config_resetting_component():
    """
    A BMC flash resets the board to defaults; a BIOS flash does not. The note is the
    difference, and it must not appear where nothing was reset.
    """
    from utils.firmware_push import FirmwarePush

    note = FirmwarePush().reconfigure_note(['BMC'])
    assert 'setupbmc' in note and 'reset to defaults' in note
    assert FirmwarePush().reconfigure_note(['BIOS']) == ''
    assert FirmwarePush().reconfigure_note([]) == ''
    # one resetting component among several is enough to warrant the note
    assert 'setupbmc' in FirmwarePush().reconfigure_note(['BIOS', 'BMC'])


def test_every_bmc_named_component_a_board_offers_earns_the_note():
    """
    The published UpdateComponent list of a real AMI board, which is the vocabulary
    the catalogue has to use - payload() refuses anything the board does not offer.
    Every entry naming the BMC resets its configuration, so every one of them has to
    produce the note; an exact-match list caught 'BMC' and missed 'HPM_BMC', which
    flashes the same chip and locked the operator out silently.
    """
    from utils.firmware_push import FirmwarePush

    offered = ['BMC', 'BIOS', 'MB_CPLD', 'BPB_CPLD', 'HPM_BMC', 'HPM_BIOS', 'HPM_SCP']
    resets = [name for name in offered if 'BMC' in name]
    assert len(resets) > 1, 'the list this pins has stopped covering more than one spelling'
    for name in resets:
        assert 'setupbmc' in FirmwarePush().reconfigure_note([name]), name
    for name in [name for name in offered if name not in resets]:
        assert FirmwarePush().reconfigure_note([name]) == '', name


def test_a_board_holding_two_bmc_images_earns_the_note_for_either():
    """
    A dual-image BMC publishes its firmware as BMCImage1 and BMCImage2. Flashing
    either resets the same configuration, and neither is the bare string 'BMC'.
    """
    from utils.firmware_push import FirmwarePush

    assert 'setupbmc' in FirmwarePush().reconfigure_note(['BMCImage1'])
    assert 'setupbmc' in FirmwarePush().reconfigure_note(['BMCImage2'])


def test_the_note_reports_and_does_not_promise_a_reboot():
    """
    Luna does not reboot a node for a firmware push, so the note must not say it will
    - it tells the operator to boot the node, it does not claim to do it.
    """
    from utils.firmware_push import FirmwarePush

    note = FirmwarePush().reconfigure_note(['BMC']).lower()
    # it asks the operator to act; it never states Luna is rebooting anything
    assert 'boot the node' in note
    assert 'rebooting' not in note and 'will reboot' not in note


def test_a_finished_bmc_flash_carries_the_note_into_its_result(db, nodes, monkeypatch):
    """
    The note has to reach the request row the operator reads, which means it has to be
    on update_node's success message - not merely computable somewhere.
    """
    from utils.database import Database
    from utils.helper import Helper
    from utils.firmware_push import FirmwarePush

    # node001 is behind on BMC (7.00 vs catalogue 7.10); make the flash itself a no-op
    fp = FirmwarePush()
    monkeypatch.setattr(fp, 'update_component',
                        lambda redfish, nodename, item: (True, f'{nodename} {item["component"]} ok'))
    status, message = fp.update_node({'nodename': 'node001'}, redfish=object())
    assert status is True
    assert 'now at the catalogue version' in message
    assert 'setupbmc' in message


def test_a_bios_only_flash_carries_no_note(db, nodes, monkeypatch):
    from utils.database import Database
    from utils.helper import Helper
    from utils.firmware_push import FirmwarePush

    ids = nodes
    # give node001 a BIOS component that is behind, and no BMC difference
    Database().update('nodeinventoryfirmware', Helper().make_rows({'version': '7.10'}),
                      [{"column": "nodeid", "value": ids['node001']}])  # BMC now matches
    db.insert('nodeinventoryfirmware', Helper().make_rows(
        {'nodeid': ids['node001'], 'source': 'redfish', 'name': 'BIOS',
         'component': 'BIOS', 'version': '1.00', 'updateable': 1}))
    db.insert('firmwarecatalog', Helper().make_rows(
        {'name': 'dellbios', 'manufacturer': 'Dell Inc.', 'model': 'PowerEdge R650',
         'component': 'BIOS', 'version': '1.05', 'imagefile': 'bios.bin'}))

    fp = FirmwarePush()
    monkeypatch.setattr(fp, 'update_component',
                        lambda redfish, nodename, item: (True, f'{nodename} {item["component"]} ok'))
    status, message = fp.update_node({'nodename': 'node001'}, redfish=object())
    assert status is True
    assert 'setupbmc' not in message
