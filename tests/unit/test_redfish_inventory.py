#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1981: collecting node inventory from the BMC, out of band.

In-band collection runs only while a node is being provisioned, so a node that has
never been installed - or is simply powered off - has no inventory at all, and
nothing that selects on hardware can work for it. Redfish answers either way.

The rule the whole collector is built around: the component set a machine reports
is implementation-defined. Two boards from one vendor list different things and a
firmware flash can change the list, so nothing here may assume what is there.
"""

import pytest

from base.nodeinventory import NodeInventory
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.helper import Helper


class FakeClient():
    """A Redfish service that answers from a path -> document map."""

    def __init__(self, resources=None, system=None, manager=None):
        self.resources = resources or {}
        self.system_data = system
        self.manager_data = manager
        self.asked = []

    def get(self, path=None, cache=False):
        self.asked.append(path)
        if path in self.resources:
            return True, self.resources[path]
        return False, f'no such resource {path}'

    def service_root(self):
        return self.get('/redfish/v1/')

    def system(self):
        if self.system_data is None:
            return False, 'no system', None
        return True, '/redfish/v1/Systems/1', self.system_data

    def manager(self):
        if self.manager_data is None:
            return False, 'no manager', None
        return True, '/redfish/v1/Managers/1', self.manager_data


SYSTEM = {
    'Manufacturer': 'Dell Inc.',
    'Model': 'PowerEdge R650',
    'SerialNumber': 'ABC1234',
    'BiosVersion': '2.10.2',
    'ProcessorSummary': {'Model': 'Intel(R) Xeon(R) Gold 6338', 'Count': 2},
    'MemorySummary': {'TotalSystemMemoryGiB': 512},
}


def collector():
    return NodeInventory()


# --- the headline facts -----------------------------------------------------

def test_the_system_resource_becomes_the_parent_row():
    status, snapshot = collector().redfish_snapshot(redfish=FakeClient(system=SYSTEM))
    assert status is True
    assert snapshot['source'] == 'redfish'
    assert snapshot['manufacturer'] == 'Dell Inc.'
    assert snapshot['product'] == 'PowerEdge R650'
    assert snapshot['serial'] == 'ABC1234'
    assert snapshot['bios_version'] == '2.10.2'
    assert snapshot['cpu_count'] == 2
    assert 'Xeon' in snapshot['cpu_model']


def test_memory_is_converted_from_gib_to_the_column_the_schema_has():
    """Redfish reports GiB; nodeinventory stores memory_mb, as in-band collection does."""
    status, snapshot = collector().redfish_snapshot(redfish=FakeClient(system=SYSTEM))
    assert snapshot['memory_mb'] == 512 * 1024


def test_a_system_that_cannot_be_read_is_reported_not_guessed():
    status, message = collector().redfish_snapshot(redfish=FakeClient(system=None))
    assert status is False and 'no system' in message


def test_a_sparse_system_yields_only_what_it_published():
    """A board that publishes half of this must not produce empty strings for the rest."""
    status, snapshot = collector().redfish_snapshot(
        redfish=FakeClient(system={'Manufacturer': 'Supermicro'}))
    assert status is True
    assert snapshot['manufacturer'] == 'Supermicro'
    assert 'serial' not in snapshot and 'bios_version' not in snapshot


# --- firmware: the part that must assume nothing -----------------------------

def firmware_service(members=None, manager=None):
    resources = {
        '/redfish/v1/': {'UpdateService': {'@odata.id': '/redfish/v1/UpdateService'}},
        '/redfish/v1/UpdateService': {
            'FirmwareInventory': {'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory'}},
        '/redfish/v1/UpdateService/FirmwareInventory': {
            'Members': [{'@odata.id': f'/fw/{index}'} for index in range(len(members or []))]},
    }
    for index, member in enumerate(members or []):
        resources[f'/fw/{index}'] = member
    return FakeClient(resources=resources, system=SYSTEM, manager=manager)


def test_every_component_the_machine_lists_is_recorded():
    """
    The acceptance criterion, and the reason there is no component list in the
    collector: a machine exposing something nobody anticipated is stored correctly,
    with no schema change, because components are rows and not columns.
    """
    client = firmware_service(members=[
        {'Id': 'BIOS', 'Name': 'BIOS', 'Version': '2.10.2', 'Updateable': True},
        {'Id': 'NIC.1', 'Name': 'Intel X710', 'Version': '21.5.9', 'Updateable': True},
        {'Id': 'CPLD', 'Name': 'System CPLD', 'Version': '1.0.6', 'Updateable': False},
        {'Id': 'QuantumFluxCapacitor', 'Name': 'Nobody Anticipated This',
         'Version': '0.1', 'Updateable': True},
    ])
    components = collector().redfish_firmware(redfish=client)
    names = [entry['name'] for entry in components]
    assert 'QuantumFluxCapacitor' in names
    assert {'BIOS', 'NIC.1', 'CPLD', 'QuantumFluxCapacitor'} <= set(names)


def test_updateable_is_recorded_so_the_question_can_be_answered_without_trying():
    """Support currently answers 'can this be flashed' by attempting it."""
    client = firmware_service(members=[
        {'Id': 'BIOS', 'Version': '2.10.2', 'Updateable': True},
        {'Id': 'CPLD', 'Version': '1.0.6', 'Updateable': False},
    ])
    by_name = {entry['name']: entry for entry in collector().redfish_firmware(redfish=client)}
    assert by_name['BIOS']['updateable'] == 1
    assert by_name['CPLD']['updateable'] == 0


def test_the_bmc_firmware_version_is_recorded_even_without_an_update_service():
    """
    Managers/<id>.FirmwareVersion is one of the two strings that are effectively
    always there, and the one a flash is verified against. A service with no
    UpdateService at all must still yield it.
    """
    client = FakeClient(resources={'/redfish/v1/': {}}, system=SYSTEM,
                        manager={'FirmwareVersion': '7.10.30.00', 'Model': 'iDRAC9',
                                 'Manufacturer': 'Dell Inc.'})
    components = collector().redfish_firmware(redfish=client)
    assert len(components) == 1
    assert components[0]['name'] == 'bmc'
    assert components[0]['version'] == '7.10.30.00'


def test_related_item_ties_a_version_to_the_device_it_belongs_to():
    """'a NIC' is not useful; 'this NIC' is."""
    client = firmware_service(members=[{
        'Id': 'NIC.1', 'Version': '21.5.9',
        'RelatedItem': [{'@odata.id': '/redfish/v1/Chassis/1/NetworkAdapters/NIC.1'}]}])
    assert collector().redfish_firmware(redfish=client)[0]['related_item'].endswith('NIC.1')


def test_a_service_with_no_firmware_inventory_is_not_an_error():
    """Plenty of BMCs do not publish one. That is a gap, not a failure."""
    client = FakeClient(resources={'/redfish/v1/': {}}, system=SYSTEM)
    assert collector().redfish_firmware(redfish=client) == []


# --- drives and interfaces, both shapes --------------------------------------

def test_drives_are_read_from_the_storage_model():
    client = FakeClient(system=dict(SYSTEM, Storage={'@odata.id': '/st'}), resources={
        '/st': {'Members': [{'@odata.id': '/st/c1'}]},
        '/st/c1': {'Drives': [{'@odata.id': '/st/c1/d1'}]},
        '/st/c1/d1': {'Id': 'Disk.0', 'CapacityBytes': 960000000000,
                      'MediaType': 'SSD', 'Model': 'MZ7', 'SerialNumber': 'S1'},
    })
    disks = collector().redfish_disks(redfish=client, system=client.system_data)
    assert disks == [{'name': 'Disk.0', 'size_gb': 960, 'type': 'SSD',
                      'model': 'MZ7', 'serial': 'S1'}]


def test_drives_fall_back_to_simple_storage_where_that_is_all_there_is():
    """SimpleStorage is what older services publish. Both are in the wild."""
    client = FakeClient(system=dict(SYSTEM, SimpleStorage={'@odata.id': '/ss'}), resources={
        '/ss': {'Members': [{'@odata.id': '/ss/c1'}]},
        '/ss/c1': {'Devices': [{'Name': 'Drive 1', 'CapacityBytes': 480000000000,
                                'Model': 'INTEL'}]},
    })
    disks = collector().redfish_disks(redfish=client, system=client.system_data)
    assert disks[0]['name'] == 'Drive 1' and disks[0]['size_gb'] == 480


def test_interfaces_are_read_with_their_mac_and_speed():
    client = FakeClient(system=dict(SYSTEM, EthernetInterfaces={'@odata.id': '/eth'}), resources={
        '/eth': {'Members': [{'@odata.id': '/eth/1'}]},
        '/eth/1': {'Id': 'NIC.1', 'MACAddress': 'aa:bb:cc:dd:ee:ff', 'SpeedMbps': 25000,
                   'Status': {'Health': 'OK'}},
    })
    nics = collector().redfish_nics(redfish=client, system=client.system_data)
    assert nics[0]['mac'] == 'aa:bb:cc:dd:ee:ff' and nics[0]['speed_mbps'] == 25000


# --- storing it beside the in-band snapshot ---------------------------------

@pytest.fixture
def inventory_db(tmp_path):
    import common.constant as constant
    from utils import database

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'inventory.db')
    database.local_thread.connection = None
    for table in ('node', 'nodeinventory', 'nodeinventorydisk', 'nodeinventorygpu',
                  'nodeinventorynic', 'nodeinventoryfirmware'):
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('node', Helper().make_rows({'name': 'node001'}))
    return Database()


def test_firmware_rows_survive_the_round_trip(inventory_db):
    snapshot = {'source': 'redfish', 'manufacturer': 'Dell Inc.', 'firmware': [
        {'name': 'BIOS', 'component': 'BIOS', 'version': '2.10.2', 'updateable': 1,
         'manufacturer': 'Dell Inc.', 'release_date': '2026-01-04',
         'software_id': 'x', 'related_item': '/redfish/v1/Systems/1'}]}
    status, _ = collector().update_inventory('node001',
        {'config': {'node': {'node001': {'inventory': snapshot}}}})
    assert status is True
    status, response = collector().get_inventory('node001')
    stored = response['config']['node']['node001']['inventory'][0]['firmware']
    assert len(stored) == 1
    assert stored[0]['version'] == '2.10.2' and stored[0]['updateable'] == 1


def test_the_two_sources_coexist_and_neither_overwrites_the_other(inventory_db):
    """
    The property TRIX-1750's suite already asserts for inband and redfish, extended
    to the firmware children this ticket adds.
    """
    store = collector()
    store.update_inventory('node001', {'config': {'node': {'node001': {'inventory': {
        'source': 'inband', 'manufacturer': 'Dell Inc.', 'bios_version': '2.10.2'}}}}})
    store.update_inventory('node001', {'config': {'node': {'node001': {'inventory': {
        'source': 'redfish', 'manufacturer': 'Dell Inc.', 'bios_version': '2.10.2',
        'firmware': [{'name': 'BIOS', 'version': '2.10.2', 'updateable': 1}]}}}}})
    status, response = store.get_inventory('node001')
    snapshots = {snap['source']: snap for snap in response['config']['node']['node001']['inventory']}
    assert set(snapshots) == {'inband', 'redfish'}
    assert snapshots['inband']['firmware'] == []
    assert len(snapshots['redfish']['firmware']) == 1


def test_recollecting_replaces_rather_than_accumulates(inventory_db):
    """A second sweep must not double every component."""
    store = collector()
    for version in ('2.10.2', '2.11.0'):
        store.update_inventory('node001', {'config': {'node': {'node001': {'inventory': {
            'source': 'redfish',
            'firmware': [{'name': 'BIOS', 'version': version, 'updateable': 1}]}}}}})
    status, response = store.get_inventory('node001')
    firmware = response['config']['node']['node001']['inventory'][0]['firmware']
    assert len(firmware) == 1 and firmware[0]['version'] == '2.11.0'


def test_deleting_a_node_takes_its_firmware_rows_with_it(inventory_db):
    """Everything put in a table on a node's behalf leaves with the node."""
    store = collector()
    store.update_inventory('node001', {'config': {'node': {'node001': {'inventory': {
        'source': 'redfish', 'firmware': [{'name': 'BIOS', 'version': '1'}]}}}}})
    store.delete_inventory(nodeid=1)
    assert not Database().get_record(table='nodeinventoryfirmware', where='nodeid = "1"')


# --- a sweep must not be taken down by one dark BMC -------------------------

def test_an_unreachable_node_is_reported_and_the_sweep_carries_on(inventory_db, monkeypatch):
    """
    An acceptance criterion, and the difference between a usable sweep and one that
    dies on the first powered-off machine. The failure has to name the node, or the
    operator learns only that something went wrong.
    """
    from utils.status import Status

    recorded = []
    monkeypatch.setattr(Status, 'add_message',
                        lambda self, **kwargs: recorded.append(kwargs))
    store = collector()
    monkeypatch.setattr(store, 'collect_redfish',
                        lambda name=None: (False, f'{name}: connect timed out after 5s'))
    assert store.collect_child(name='node001', request_id='r1') is False
    assert 'node001' in recorded[0]['message'] and recorded[0]['status'] == 500
    # the format Control().get_status parses, since this reuses that channel
    node, command, result, text = recorded[0]['message'].split(':', 3)
    assert (node, command, result) == ('node001', 'inventory redfish', 'False')
    assert 'connect timed out' in text


def test_a_raising_collector_does_not_escape_the_worker(inventory_db, monkeypatch):
    """One node's unexpected failure must not take the executor down with it."""
    from utils.status import Status

    recorded = []
    monkeypatch.setattr(Status, 'add_message', lambda self, **kwargs: recorded.append(kwargs))
    store = collector()

    def explode(name=None):
        raise RuntimeError('the BMC said something unrepeatable')

    monkeypatch.setattr(store, 'collect_redfish', explode)
    assert store.collect_child(name='node001', request_id='r1') is False
    assert 'unrepeatable' in recorded[0]['message']


def test_a_bad_hostlist_is_refused_before_anything_is_scheduled():
    status, message = collector().bulk_collect_redfish({'config': {'node': {'hostlist': ''}}})
    assert status is False and 'hostlist' in message


def test_a_request_without_a_hostlist_says_so():
    status, message = collector().bulk_collect_redfish({'config': {'node': {}}})
    assert status is False and 'hostlist' in message
