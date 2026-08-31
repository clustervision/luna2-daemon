#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2042: BIOS profiles - clone a grabbed configuration, change entries in it
by concept, assign it to nodes and groups, push what is assigned.

The part that decides whether this is vendor agnostic is the resolver: a concept
is found in a board's own attribute registry through its DisplayName and its
value is matched against what that board publishes, so no vendor's attribute
name lives in core. Those cases run against a real registry - the GIGABYTE
R181-Z91 capture - because a registry we wrote would only ever agree with us.

The rest is plumbing that has to hold under HA and at scale: the resolution
happens before the journal (the peer never dials a BMC), an assignment is an id
like every other reference, a push without a name refuses the whole request
when one target has no assignment, and the status view tells "pending" and
"stale" apart from "matched" without waking a machine.
"""

import hashlib
import json
import os
from base64 import b64decode
from json import dumps

import pytest

from base.bios import Bios
from base.group import Group
from base.node import Node
from utils.bios import Bios as Planner, CONCEPTS
from utils.database import Database
from utils.helper import Helper

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
with open(os.path.join(FIXTURES, 'gigabyte-bios-registry.json')) as handle:
    REGISTRY = json.load(handle)


def digest_of(attributes):
    return hashlib.sha256(dumps(attributes, sort_keys=True).encode()).hexdigest()


# --- the resolver, against a real registry ------------------------------------

def test_every_concept_resolves_to_exactly_one_attribute_or_none_on_a_real_board():
    """
    The R181 registry names most concepts plainly; the ones it does not publish
    (the redirection toggle, the baud rate) resolve to nothing, which is the
    honest answer - never to a near miss.
    """
    found = {concept: Planner().concept_matches(registry=REGISTRY, concept=concept)
             for concept in CONCEPTS}
    assert all(len(names) <= 1 for names in found.values()), found
    assert found['hyperthreading'] == ['Naples0023']
    assert found['secure_boot'] == ['SECB001']          # not SECB002 "Secure Boot Mode"
    assert found['serial_console_port'] == ['TER010']
    assert found['serial_console'] == [] and found['serial_console_baud'] == []


def test_a_concept_is_written_as_the_board_spells_it():
    resolved, refused = Planner().resolve(registry=REGISTRY, entries={
        'hyperthreading': 'off', 'sriov': 'on', 'boot_mode': 'uefi', 'tpm': 'on',
        'power_profile': 'performance', 'secure_boot': 'ENABLED'})
    assert refused == {}
    assert resolved == {'Naples0023': 'Off', 'PCIS007': 'Enabled', 'FBO001': 'UEFI',
                        'TCG003': 'Enable', 'Naples0208': 'Performance', 'SECB001': 'Enabled'}


def test_on_never_becomes_auto():
    """
    SMT Mode on this board is [Off, Auto]. Auto is the vendor's third state with
    its own meaning; mapping a plain 'on' onto it would be us deciding what the
    board meant. Refused, with what the board takes.
    """
    resolved, refused = Planner().resolve(registry=REGISTRY, entries={'hyperthreading': 'on'})
    assert resolved == {}
    assert refused == {'hyperthreading': '(Naples0023) takes one of: Off, Auto'}
    resolved, _ = Planner().resolve(registry=REGISTRY, entries={'hyperthreading': 'auto'})
    assert resolved == {'Naples0023': 'Auto'}


def test_a_raw_attribute_name_is_validated_against_its_entry():
    resolved, refused = Planner().resolve(registry=REGISTRY, entries={
        'PCIS007': 'disabled', 'GBT0141': '500', 'SETUP005': 'no', 'REDF002': '10.0.0.1'})
    assert refused == {}
    assert resolved == {'PCIS007': 'Disabled', 'GBT0141': 500, 'SETUP005': False,
                        'REDF002': '10.0.0.1'}
    _, refused = Planner().resolve(registry=REGISTRY, entries={
        'GBT0141': '5', 'SETUP005': 'maybe', 'REDF002': 'x' * 16, 'SETUP001': 'secret'})
    assert refused == {
        'GBT0141': 'takes a whole number between 10 and 10000',
        'SETUP005': 'takes true or false',
        'REDF002': 'takes at most 15 characters',
        'SETUP001': 'is a password, which a stored configuration never carries'}


def test_what_the_board_cannot_express_is_refused_by_name_never_dropped():
    resolved, refused = Planner().resolve(registry=REGISTRY, entries={
        'serial_console': 'on', 'hyperthreading': 'off', 'nosuchthing': '1'})
    assert resolved == {'Naples0023': 'Off'}
    assert refused == {
        'serial_console': 'is not published by this board type',
        'nosuchthing': 'is neither a known concept nor an attribute this board type publishes'}


def test_an_ambiguous_concept_is_refused_with_the_candidates():
    """Two entries both called 'Secure Boot' on a made-up board: a guess here is
    written to hardware, so it is refused and the operator names the attribute."""
    twins = {'RegistryEntries': {'Attributes': [
        {'AttributeName': 'A1', 'DisplayName': 'Secure Boot', 'Type': 'Enumeration',
         'Value': [{'ValueName': 'Enabled'}, {'ValueName': 'Disabled'}]},
        {'AttributeName': 'A2', 'DisplayName': 'secure boot', 'Type': 'Enumeration',
         'Value': [{'ValueName': 'Enabled'}, {'ValueName': 'Disabled'}]}]}}
    _, refused = Planner().resolve(registry=twins, entries={'secure_boot': 'on'})
    assert refused == {'secure_boot': 'is ambiguous on this board type, matching A1, A2; '
                                      'name the attribute instead'}
    resolved, _ = Planner().resolve(registry=twins, entries={'A2': 'on'})
    assert resolved == {'A2': 'Enabled'}


def test_a_vendor_mapping_is_used_only_when_its_attribute_exists():
    """A plugin may say where a concept lives on a board discovery cannot read;
    a mapping naming an attribute the registry lacks falls back to discovery."""
    resolved, _ = Planner().resolve(registry=REGISTRY, entries={'hyperthreading': 'off'},
                                    mapping={'hyperthreading': 'Naples0046'})
    assert resolved == {'Naples0046': 'Disabled'}
    resolved, _ = Planner().resolve(registry=REGISTRY, entries={'hyperthreading': 'off'},
                                    mapping={'hyperthreading': 'GONE001'})
    assert resolved == {'Naples0023': 'Off'}


def test_the_shipped_plugin_maps_nothing():
    from plugins.redfish.default import Plugin
    assert Plugin().concepts() == {}


def test_profiles_are_an_add_on_the_boot_path_never_reads():
    """
    A node with no configuration assigned - every node on an upgraded cluster -
    must boot, install and be monitored exactly as before. So nothing on the boot
    and install path may consult an assignment: the column is only read by the
    node/group views, the status view and an explicit push. Enumerated from the
    tree so a future reference is a red test, not a boot that behaves differently
    on a cluster that never asked for BIOS profiles.
    """
    import glob
    daemon = os.path.join(os.path.dirname(__file__), '..', '..', 'daemon')
    boot_path = ([os.path.join(daemon, 'base', 'boot.py'),
                  os.path.join(daemon, 'base', 'monitor.py')]
                 + glob.glob(os.path.join(daemon, 'templates', '*'))
                 + glob.glob(os.path.join(daemon, 'plugins', 'boot', '**', '*'), recursive=True))
    offenders = []
    for path in boot_path:
        if os.path.isfile(path):
            with open(path, errors='ignore') as handle:
                if 'biosconfig' in handle.read():
                    offenders.append(os.path.relpath(path, daemon))
    assert offenders == [], f'the boot path consults BIOS profiles: {offenders}'


# --- clone, change, assign, push, status - through the base class -------------

@pytest.fixture(name='cluster')
def cluster_fixture(sqlite_db):
    """Two nodes in one group, one in another, and a golden configuration grabbed
    from node001 - the R181 board."""
    db = Database()
    db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    db.insert('node', Helper().make_rows({'name': 'node002', 'groupid': groupid}))
    other = db.insert('group', Helper().make_rows({'name': 'gpu-nodes'}))
    db.insert('node', Helper().make_rows({'name': 'node003', 'groupid': other}))
    attributes = {'Naples0023': 'Auto', 'PCIS007': 'Disabled', 'FBO001': 'UEFI'}
    Bios().store_grabbed('golden', {'config': {'biosconfig': {'golden': {
        'attributes': attributes, 'dropped': {}, 'manufacturer': 'GIGABYTE',
        'model': 'R181-Z91-00', 'biosversion': 'F25', 'node': 'node001'}}}})
    return {'groupid': groupid, 'attributes': attributes}


def config(name):
    return Database().get_record(table='biosconfig', where=f'name = "{name}"')


def test_a_clone_is_the_grab_under_a_new_name_with_its_provenance(cluster):
    status, message = Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {
        'newbiosname': 'hpc-nosmt'}}}})
    assert status is True and message == 'BIOS configuration golden cloned to hpc-nosmt'
    source, clone = config('golden')[0], config('hpc-nosmt')[0]
    for column in ('manufacturer', 'model', 'biosversion', 'nodeid', 'attributes', 'grab_exclude'):
        assert clone[column] == source[column], column
    assert clone['id'] != source['id']
    assert Bios().detail(clone)['grabbedfrom'] == 'node001'
    status, message = Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {
        'newbiosname': 'hpc-nosmt'}}}})
    assert (status, message) == (False, 'BIOS configuration hpc-nosmt already exists')
    status, _ = Bios().clone_bios('nosuch', {'config': {'biosconfig': {'nosuch': {
        'newbiosname': 'x'}}}})
    assert status is False


def resolving(monkeypatch, registry=REGISTRY, node='node001'):
    """The board type's registry, without a BMC: what registry_for returns."""
    monkeypatch.setattr(Bios, 'registry_for',
                        lambda self, record=None: (True, registry, node))
    monkeypatch.setattr(Bios, 'concept_map', lambda self, record=None: {})


def test_a_change_by_concept_lands_as_the_boards_attribute_and_touches_nothing_else(cluster, monkeypatch):
    resolving(monkeypatch)
    Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {'newbiosname': 'hpc-nosmt'}}}})
    request = {'config': {'biosconfig': {'hpc-nosmt': {'set': {'hyperthreading': 'off', 'sriov': 'on'}}}}}
    status, resolved = Bios().resolve_set('hpc-nosmt', request)
    assert status is True
    # what travels to the peer is the resolved map, never the typed concepts
    assert resolved['config']['biosconfig']['hpc-nosmt']['set'] == {'Naples0023': 'Off', 'PCIS007': 'Enabled'}
    status, message = Bios().update_bios('hpc-nosmt', resolved)
    assert status is True, message
    assert Bios().stored_attributes(config('hpc-nosmt')[0]) == {
        'Naples0023': 'Off', 'PCIS007': 'Enabled', 'FBO001': 'UEFI'}
    assert Bios().stored_attributes(config('golden')[0]) == cluster['attributes']


def test_one_bad_entry_refuses_the_whole_change_by_name(cluster, monkeypatch):
    resolving(monkeypatch)
    request = {'config': {'biosconfig': {'golden': {'set': {'hyperthreading': 'off',
                                                            'serial_console': 'on'}}}}}
    status, message = Bios().resolve_set('golden', request)
    assert status is False
    assert message == ('nothing changed on golden (registry read from node001): '
                       'serial_console is not published by this board type')
    assert Bios().stored_attributes(config('golden')[0]) == cluster['attributes']


def test_no_reachable_board_of_that_type_refuses_the_change(cluster, monkeypatch):
    """The golden node has no BMC configured here, and no other node reports the
    board - so there is no registry to validate against, and nothing is written."""
    monkeypatch.setattr(Bios, 'concept_map', lambda self, record=None: {})
    status, message = Bios().resolve_set(
        'golden', {'config': {'biosconfig': {'golden': {'set': {'sriov': 'on'}}}}})
    assert status is False
    assert 'no registry reachable for board type GIGABYTE R181-Z91-00' in message
    assert 'node001' in message


def test_the_registry_is_read_from_the_golden_node_then_any_node_of_that_board(cluster, monkeypatch):
    asked = []

    def board(self, node=None):
        asked.append(node)
        return False, f'{node}: unreachable'

    monkeypatch.setattr(Bios, 'board_bios', board)
    Database().insert('nodeinventory', Helper().make_rows({
        'nodeid': 3, 'source': 'redfish', 'manufacturer': 'gigabyte', 'product': 'R181-Z91-00'}))
    Database().insert('nodeinventory', Helper().make_rows({
        'nodeid': 2, 'source': 'redfish', 'manufacturer': 'Dell Inc.', 'product': 'R750'}))
    status, _, _ = Bios().registry_for(config('golden')[0])
    assert status is False
    assert asked == ['node001', 'node003']     # golden first, same board next, other boards never


def test_a_change_without_entries_still_takes_the_exclude_list_and_comment(cluster, monkeypatch):
    request = {'config': {'biosconfig': {'golden': {'comment': 'Z29sZGVu'}}}}
    status, same = Bios().resolve_set('golden', request)
    assert status is True and same is request
    status, _ = Bios().update_bios('golden', request)
    assert status is True and config('golden')[0]['comment'] == 'Z29sZGVu'
    status, message = Bios().update_bios('golden', {'config': {'biosconfig': {'golden': {
        'attributes': {'Naples0023': 'Off'}}}}})
    assert status is False and 'Cannot set attributes' in message


def test_an_assignment_is_stored_as_an_id_and_shown_as_a_name_node_over_group(cluster):
    Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {'newbiosname': 'gpu'}}}})
    status, message = Group().update_group('compute', {'config': {'group': {'compute': {
        'biosconfig': 'golden'}}}})
    assert status is True, message
    status, message = Node().update_node('node002', {'config': {'node': {'node002': {
        'biosconfig': 'gpu'}}}})
    assert status is True, message
    group = Database().get_record(table='group', where='name = "compute"')[0]
    assert group['biosconfigid'] == config('golden')[0]['id']
    assert Database().get_record(table='node', where='name = "node002"')[0]['biosconfigid'] \
        == config('gpu')[0]['id']
    _, shown = Node().get_node('node001')
    node = shown['config']['node']['node001']
    assert (node['biosconfig'], node['_biosconfig_source']) == ('golden', 'group')
    _, shown = Node().get_node('node002')
    node = shown['config']['node']['node002']
    assert (node['biosconfig'], node['_biosconfig_source']) == ('gpu', 'node')
    _, shown = Group().get_group('compute')
    assert shown['config']['group']['compute']['biosconfig'] == 'golden'
    _, listed = Node().get_all_nodes()
    assert listed['config']['node']['node001']['biosconfig'] == 'golden'
    assert listed['config']['node']['node003']['biosconfig'] is None
    status, message = Node().update_node('node002', {'config': {'node': {'node002': {
        'biosconfig': 'nosuch'}}}})
    assert status is False and 'nosuch' in message
    status, _ = Node().update_node('node002', {'config': {'node': {'node002': {'biosconfig': ''}}}})
    assert status is True
    assert not Database().get_record(table='node', where='name = "node002"')[0]['biosconfigid']


def test_an_assignment_can_be_cleared_through_the_shared_validator():
    """
    Found through the CLI: 'biosconfig' was registered under the name rule for the
    grab and push routes, and the same key on a node or group is an assignment,
    which is cleared by sending it empty - so 'luna node change --biosconfig ""'
    was refused before it reached the code. A quoted value must still be refused.
    """
    import common.validate_input as validate_input
    # the decorators set these at request time; outside a request they are the
    # non-strict defaults, as the validator's own tests prime them
    validate_input.STRICT_NAME = False
    validate_input.STRICT_MATCH = None
    validate_input.SKIP_LIST = []
    validate_input.ERROR = None
    assert validate_input.filter_data('', 'biosconfig') == ''
    assert validate_input.ERROR is None
    assert validate_input.filter_data('hpc-nosmt', 'biosconfig') == 'hpc-nosmt'
    assert validate_input.ERROR is None
    assert validate_input.filter_data('hpc"nosmt', 'biosconfig') is None
    assert validate_input.ERROR
    validate_input.ERROR = None


def test_an_assigned_configuration_cannot_be_removed(cluster):
    Group().update_group('compute', {'config': {'group': {'compute': {'biosconfig': 'golden'}}}})
    status, message = Bios().delete_bios('golden')
    assert status is False and 'assigned to group compute' in message
    Group().update_group('compute', {'config': {'group': {'compute': {'biosconfig': ''}}}})
    assert Bios().delete_bios('golden')[0] is True


def queued():
    return sorted(row['param'] for row in
                  Database().get_record(table='queue', where='task = "push_bios"') or [])


def test_a_push_without_a_name_pushes_each_nodes_assignment(cluster):
    Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {'newbiosname': 'gpu'}}}})
    Group().update_group('compute', {'config': {'group': {'compute': {'biosconfig': 'golden'}}}})
    Node().update_node('node002', {'config': {'node': {'node002': {'biosconfig': 'gpu'}}}})
    returned = Bios().push_bios(object_type='group', name='compute',
                                request_data={'config': {'group': {'compute': {}}}})
    assert returned[0] is True, returned[1]
    assert queued() == ['node001:golden:warn', 'node002:gpu:warn']
    assert 'golden, gpu' in returned[1]


def test_a_push_without_a_name_refuses_the_whole_group_when_one_member_has_none(cluster):
    Node().update_node('node002', {'config': {'node': {'node002': {'biosconfig': 'golden'}}}})
    returned = Bios().push_bios(object_type='group', name='compute',
                                request_data={'config': {'group': {'compute': {}}}})
    assert returned[0] is False
    assert returned[1] == ('no BIOS configuration is assigned to node001; assign one to the '
                           'node or its group, or name one to push')
    assert queued() == []
    returned = Bios().push_bios(object_type='node', name='node003', request_data=None)
    assert returned[0] is False and 'node003' in returned[1]


def test_a_named_push_still_wins_over_the_assignment(cluster):
    Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {'newbiosname': 'gpu'}}}})
    Node().update_node('node003', {'config': {'node': {'node003': {'biosconfig': 'gpu'}}}})
    returned = Bios().push_bios(object_type='node', name='node003',
                                request_data={'config': {'node': {'node003': {'biosconfig': 'golden'}}}})
    assert returned[0] is True and queued() == ['node003:golden:warn']


def snapshot(nodeid, held, configname=None, content=None):
    row = {'nodeid': nodeid, 'source': 'redfish', 'bios_digest': digest_of(held)}
    if configname:
        row.update({'bios_config': configname, 'bios_config_digest': digest_of(held),
                    'bios_config_content': content or ''})
    Database().insert('nodeinventory', Helper().make_rows(row))


def state_of(node):
    _, response = Bios().status()
    return response['config']['biosconfig']['status'][node]


def test_status_tells_pending_and_stale_apart_from_matched(cluster, monkeypatch):
    golden = config('golden')[0]
    content = Bios().content_digest(golden)
    Bios().clone_bios('golden', {'config': {'biosconfig': {'golden': {'newbiosname': 'gpu'}}}})
    Group().update_group('compute', {'config': {'group': {'compute': {'biosconfig': 'golden'}}}})
    Node().update_node('node003', {'config': {'node': {'node003': {'biosconfig': 'gpu'}}}})
    held = cluster['attributes']
    snapshot(1, held, 'golden', content)      # holds golden, assigned golden -> matched
    snapshot(2, held)                         # read, matches nothing, assigned golden -> pending
    snapshot(3, held, 'golden', content)      # holds golden, assigned gpu -> pending
    assert (state_of('node001')['state'], state_of('node001')['assigned']) == ('matched', 'golden')
    assert state_of('node002')['state'] == 'pending'
    assert state_of('node003')['state'] == 'pending'
    # now golden is edited: node001 still holds what golden said at the push
    resolving(monkeypatch)
    status, resolved = Bios().resolve_set('golden', {'config': {'biosconfig': {'golden': {
        'set': {'hyperthreading': 'off'}}}}})
    assert status is True
    Bios().update_bios('golden', resolved)
    assert state_of('node001')['state'] == 'stale'
    _, response = Bios().status()
    assert response['config']['biosconfig']['summary'] == {'stale': 1, 'pending': 2}


def test_a_match_recorded_before_the_content_was_kept_is_not_called_stale(cluster):
    Group().update_group('compute', {'config': {'group': {'compute': {'biosconfig': 'golden'}}}})
    snapshot(1, cluster['attributes'], 'golden')          # no content recorded
    assert state_of('node001')['state'] == 'matched'


def test_record_match_keeps_what_the_configuration_said(cluster):
    Database().insert('nodeinventory', Helper().make_rows({'nodeid': 1, 'source': 'redfish'}))
    assert Bios().record_match(name='node001', payload={'config': 'golden', 'digest': 'abc'}) is True
    row = Database().get_record(table='nodeinventory', where='nodeid = "1"')[0]
    assert row['bios_config_content'] == Bios().content_digest(config('golden')[0])
    assert row['bios_config_content'] == digest_of(cluster['attributes'])
