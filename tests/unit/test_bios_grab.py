#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: grabbing a BIOS configuration off a golden node.

The question this has to answer correctly is which attributes may be carried to
another machine, and the answer is the target's own attribute registry rather
than a list we maintain per vendor and per model. The DMTF AttributeRegistry
schema carries the flags that decide it, and each says something different:

  IsSystemUniqueProperty  "unique for this system and should not be replicated"
  ReadOnly                "a read-only attribute cannot be modified"
  Immutable               "cannot be modified and typically reflect a hardware state"
  WriteOnly               "reverts to its initial value after settings are applied"

IsSystemUniqueProperty is the one that answers the question outright, and it is
also OPTIONAL in the schema - no vendor is obliged to set it, and none has been
confirmed to. That is exactly why the exclude list exists beside it, and why
these tests hold both paths rather than only the tidy one.

Nothing here talks to a BMC. The Redfish client is replaced with one that serves
documents, which is what lets the awkward cases - a registry that will not load,
a machine that publishes none at all - be tested rather than argued about.
"""

import json
from base64 import b64decode

import pytest

from base.bios import Bios
from utils.bios import Bios as BiosPlanner, DEFAULT_EXCLUDE
from utils.database import Database
from utils.helper import Helper


def entry(name, **flags):
    """One attribute registry entry."""
    return dict({'AttributeName': name, 'Type': 'String'}, **flags)


REGISTRY = {'RegistryEntries': {'Attributes': [
    entry('BootMode'),
    entry('SriovGlobalEnable'),
    entry('ProcVirtualization'),
    entry('SystemServiceTag', IsSystemUniqueProperty=True),
    entry('SystemModelName', ReadOnly=True),
    entry('MemoryPresent', Immutable=True),
    entry('SetupPassword', WriteOnly=True),
    entry('AssetTag'),
    entry('MemTest'),
]}}

ATTRIBUTES = {
    'BootMode': 'Uefi',
    'SriovGlobalEnable': 'Enabled',
    'ProcVirtualization': 'Enabled',
    'SystemServiceTag': 'ABC1234',
    'SystemModelName': 'PowerThing R750',
    'MemoryPresent': '256 GB',
    'SetupPassword': '',
    'AssetTag': 'rack12-u04',
    'MemTest': None,
    'UndocumentedKnob': 'Enabled',
}


# --- what may be carried, and why not ---------------------------------------

def test_a_registry_flag_keeps_an_attribute_off_another_machine():
    """
    The four flags are not interchangeable, so each is asserted on its own. A
    filter that only knew ReadOnly would happily copy a service tag.
    """
    kept, dropped = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES)
    assert dropped['SystemServiceTag'] == 'unique to this system and not to be replicated'
    assert dropped['SystemModelName'] == 'read-only'
    assert dropped['MemoryPresent'] == 'immutable, reflects a hardware state'
    assert dropped['SetupPassword'] == 'write-only, reverts after settings are applied'
    assert 'SystemServiceTag' not in kept


def test_an_attribute_the_registry_does_not_describe_is_not_carried():
    """
    A machine that will not talk about an attribute is not one we should be
    copying it from. Silently passing it through is how a vendor's private knob
    reaches a machine that means something else by it.
    """
    _, dropped = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES)
    assert dropped['UndocumentedKnob'] == 'not described by the attribute registry'


def test_a_null_value_is_not_carried():
    _, dropped = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES)
    assert dropped['MemTest'] == 'no value'


def test_the_exclude_list_catches_what_the_vendor_did_not_mark():
    """
    The reason this exists at all. AssetTag is per-machine identity and the
    registry above does not mark it - which is the realistic case, since
    IsSystemUniqueProperty is optional and no vendor is confirmed to set it.
    Without the exclude list a golden node's asset tag lands on every node in
    the group.
    """
    plain, _ = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES)
    assert 'AssetTag' in plain, 'the registry alone was expected not to catch this'

    kept, dropped = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES,
                                           exclude=DEFAULT_EXCLUDE)
    assert 'AssetTag' not in kept
    assert dropped['AssetTag'].startswith('excluded by ')


def test_the_exclude_match_is_case_insensitive():
    """Vendors do not agree on case for the same concept."""
    registry = {'RegistryEntries': {'Attributes': [entry('ASSETTAG'), entry('Assettag')]}}
    kept, _ = BiosPlanner().portable(registry=registry,
                                     attributes={'ASSETTAG': 'a', 'Assettag': 'b'},
                                     exclude=['*AssetTag*'])
    assert kept == {}


def test_what_survives_is_the_settings_and_only_the_settings():
    """
    Assert what was kept, not merely that filtering ran. A filter that dropped
    everything would pass every test above.
    """
    kept, _ = BiosPlanner().portable(registry=REGISTRY, attributes=ATTRIBUTES,
                                     exclude=DEFAULT_EXCLUDE)
    assert kept == {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled',
                    'ProcVirtualization': 'Enabled'}


# --- a fake BMC, so the awkward cases are testable ---------------------------

class FakeRedfish():
    """Serves documents. Anything it was not given is a 404, as a BMC would."""

    def __init__(self, documents=None, system=None, **kwargs):
        self.documents = documents or {}
        self.systemdata = system

    def get(self, path=None, cache=False):
        if path in self.documents:
            return True, self.documents[path]
        return False, f'{path} not found'

    def system(self):
        if self.systemdata is None:
            return False, 'no ComputerSystem', None
        return True, '/redfish/v1/Systems/1', self.systemdata


SYSTEM = {
    'Manufacturer': 'Contoso', 'Model': 'PowerThing R750', 'BiosVersion': '2.15.1',
    'Bios': {'@odata.id': '/redfish/v1/Systems/1/Bios'},
}

DOCUMENTS = {
    '/redfish/v1/Systems/1/Bios': {'Attributes': ATTRIBUTES,
                                   'AttributeRegistry': 'BiosAttributeRegistry.v1_0_0'},
    '/redfish/v1/Registries': {'Members': [
        {'@odata.id': '/redfish/v1/Registries/Base'},
        {'@odata.id': '/redfish/v1/Registries/Bios'},
    ]},
    '/redfish/v1/Registries/Base': {'Registry': 'Base.1.0.0',
                                    'Location': [{'Uri': '/registries/base.json'}]},
    '/redfish/v1/Registries/Bios': {'Registry': 'BiosAttributeRegistry.v1_0_0',
                                    'Location': [{'Uri': '/registries/bios.json'}]},
    '/registries/bios.json': REGISTRY,
}


@pytest.fixture
def bmc(monkeypatch):
    """Point base.bios at a served BMC rather than a real one."""
    def install(documents=DOCUMENTS, system=SYSTEM, reachable=True):
        monkeypatch.setattr('base.bios.NodeInventory.bmc_for',
                            lambda self, name=None: (True, {
                                'device': '10.0.0.1', 'username': 'ro', 'password': 'x',
                                'scheme': 'https', 'port': None, 'verify': False})
                            if reachable else (False, f'{name} has no BMC address configured'))
        monkeypatch.setattr('base.bios.Redfish',
                            lambda **kwargs: FakeRedfish(documents=documents, system=system))
    return install


def test_a_grab_resolves_the_registry_by_id_not_by_guessing_a_path(bmc):
    """
    The Bios resource names a registry by id and the id has to be looked up in
    the registry collection to get a URI. Guessing the path works on one machine
    and not the next - and note the collection here carries a decoy first.
    """
    bmc()
    status, payload = Bios().collect_bios(node='node001', name='golden')
    assert status is True, payload
    data = payload['config']['biosconfig']['golden']
    assert data['attributes'] == {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled',
                                  'ProcVirtualization': 'Enabled'}
    assert data['manufacturer'] == 'Contoso'
    assert data['model'] == 'PowerThing R750'
    assert data['biosversion'] == '2.15.1'


def test_a_machine_that_publishes_no_registry_is_refused(bmc):
    """
    Refusing is right. A configuration we cannot filter is one we would push
    identity values out of, and the node it came from is the only machine that
    can say which those are.
    """
    documents = dict(DOCUMENTS)
    documents['/redfish/v1/Systems/1/Bios'] = {'Attributes': ATTRIBUTES}
    bmc(documents=documents)
    status, response = Bios().collect_bios(node='node001', name='golden')
    assert status is False
    assert 'names no BIOS attribute registry' in response


def test_a_registry_that_is_not_published_is_said_out_loud(bmc):
    documents = dict(DOCUMENTS)
    documents['/redfish/v1/Registries'] = {'Members': [{'@odata.id': '/redfish/v1/Registries/Base'}]}
    bmc(documents=documents)
    status, response = Bios().collect_bios(node='node001', name='golden')
    assert status is False
    assert 'is not published by this machine' in response


def test_the_failure_reason_is_carried_not_the_wrong_tuple_slot(bmc):
    """
    The Redfish client answers (status, path, data) and on a FAILURE the reason
    is in the second slot. Returning the third gives the operator None, which
    has happened once already in this feature set.
    """
    bmc(system=None)
    status, response = Bios().collect_bios(node='node001', name='golden')
    assert status is False
    assert 'no ComputerSystem' in response


def test_a_node_with_no_bmc_is_reported_as_that(bmc):
    bmc(reachable=False)
    status, response = Bios().collect_bios(node='node001', name='golden')
    assert status is False
    assert 'no BMC address configured' in response


# --- storage -----------------------------------------------------------------

def stored(sqlite_db, bmc, name='golden', node='node001'):
    Database().insert('node', Helper().make_rows({'name': node}))
    bmc()
    status, payload = Bios().collect_bios(node=node, name=name)
    assert status is True, payload
    status, message = Bios().store_grabbed(name, payload)
    assert status is True, message
    return Database().get_record(table='biosconfig', where=f'name = "{name}"')[0], message


def test_the_attributes_are_always_base64_and_survive_a_restore(sqlite_db, bmc):
    """
    Same property as the inventory archive: /config/cluster/import strips every
    quote from a text value, so stored JSON restores unparseable. Always encoded
    rather than sometimes, so no reader has to guess which it got.
    """
    row, _ = stored(sqlite_db, bmc)
    assert not row['attributes'].startswith('{')
    restored = row['attributes'].replace("'", "").replace('"', "")
    assert restored == row['attributes']
    assert json.loads(b64decode(restored)) == {'BootMode': 'Uefi',
                                               'SriovGlobalEnable': 'Enabled',
                                               'ProcVirtualization': 'Enabled'}


def test_a_new_configuration_is_seeded_with_the_shipped_exclude_list(sqlite_db, bmc):
    """
    Seeded rather than implied, so an administrator can see what was excluded and
    judge it. An exclude list nobody can read is one nobody can correct.
    """
    row, _ = stored(sqlite_db, bmc)
    assert Bios().exclude_list(row) == list(DEFAULT_EXCLUDE)


def test_the_grab_says_how_much_it_did_not_carry(sqlite_db, bmc):
    """
    A grab that quietly drops half a configuration is indistinguishable from one
    that found half a configuration.
    """
    _, message = stored(sqlite_db, bmc)
    assert '3 setting(s) stored' in message
    assert '7 not carried' in message


def test_the_hardware_the_configuration_came_from_is_recorded(sqlite_db, bmc):
    """A push checks these three before it writes anything."""
    row, _ = stored(sqlite_db, bmc)
    assert (row['manufacturer'], row['model'], row['biosversion']) == \
           ('Contoso', 'PowerThing R750', '2.15.1')


def test_the_golden_node_is_stored_as_an_id_and_resolved_to_a_name(sqlite_db, bmc):
    """
    Provenance, and it follows the repo's rule: the reference is an id and the
    name is resolved when it is read, so a rename does not orphan it.
    """
    row, _ = stored(sqlite_db, bmc)
    assert row['nodeid'] == 1
    status, response = Bios().get_bios('golden')
    assert status is True
    assert response['config']['biosconfig']['golden']['grabbedfrom'] == 'node001'


def test_a_deleted_golden_node_does_not_make_the_configuration_unusable(sqlite_db, bmc):
    """It is provenance and nothing acts on it, so it degrades to unknown."""
    stored(sqlite_db, bmc)
    Database().delete_row('node', [{"column": "name", "value": 'node001'}])
    status, response = Bios().get_bios('golden')
    assert status is True
    detail = response['config']['biosconfig']['golden']
    assert detail['grabbedfrom'] == ''
    assert detail['settings'] == 3


def test_the_list_renderer_finds_the_name_inside_the_record(sqlite_db, bmc):
    """
    The generic CLI list renderer looks its columns up inside the record and
    prints --NA-- for anything it cannot find there. This has already caught a
    whole command printing nothing useful.
    """
    stored(sqlite_db, bmc)
    status, response = Bios().get_all_bios()
    assert status is True
    assert response['config']['biosconfig']['golden']['name'] == 'golden'


def test_a_regrab_updates_in_place_and_keeps_the_edited_exclude_list(sqlite_db, bmc):
    """
    An administrator's exclude list is theirs. A second grab must not quietly
    put the shipped one back over it.
    """
    stored(sqlite_db, bmc)
    status, message = Bios().update_bios('golden', {'config': {'biosconfig': {
        'golden': {'grab_exclude': '*AssetTag*'}}}})
    assert status is True, message
    bmc()
    status, payload = Bios().collect_bios(node='node001', name='golden')
    assert status is True
    Bios().store_grabbed('golden', payload)
    row = Database().get_record(table='biosconfig', where='name = "golden"')[0]
    assert Bios().exclude_list(row) == ['*AssetTag*']
    assert len(Database().get_record(table='biosconfig', where='name = "golden"')) == 1


def test_the_edited_exclude_list_is_what_the_next_grab_uses(sqlite_db, bmc):
    """
    Otherwise the field is decorative. Narrowing the list must let a previously
    excluded attribute through.
    """
    stored(sqlite_db, bmc)
    Bios().update_bios('golden', {'config': {'biosconfig': {
        'golden': {'grab_exclude': '*ServiceTag*'}}}})
    bmc()
    status, payload = Bios().collect_bios(node='node001', name='golden')
    assert status is True
    assert 'AssetTag' in payload['config']['biosconfig']['golden']['attributes']


def test_attributes_cannot_be_hand_edited_through_the_api(sqlite_db, bmc):
    """
    They are what a machine said about itself. A configuration edited into
    something no machine ever reported is the thing a golden node avoids.
    """
    stored(sqlite_db, bmc)
    status, response = Bios().update_bios('golden', {'config': {'biosconfig': {
        'golden': {'attributes': {'BootMode': 'Bios'}}}}})
    assert status is False
    assert 'Cannot set attributes' in response
