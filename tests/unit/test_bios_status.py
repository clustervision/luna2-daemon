#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: what a node was last seen holding.

A push answers "get this machine to that configuration" and it has to talk to the
machine to do it. This answers a different question - "what is running which
configuration" - weeks later, when the machines may be off, and it answers from
stored inventory without contacting anything.

That is only affordable because of what is stored. The attribute sets themselves
run from about a hundred entries to several hundred, which is tens of megabytes
across a cluster, in the database, in every backup and in the hash the controllers
compare on each pass. Three short strings answer the question instead: the digest
of what the machine held when we last read it, the configuration it was last found
to match, and the digest it had at that moment. Drift is the third disagreeing with
the first.

What that deliberately cannot answer is how many stages a node still needs, because
that needs the board's registry and its live values. The status view says when it
last looked rather than implying it knows now.
"""

import hashlib
from json import dumps

import pytest

from base.bios import Bios
from base.nodeinventory import NodeInventory
from utils.database import Database
from utils.helper import Helper


def digest_of(attributes):
    return hashlib.sha256(dumps(attributes, sort_keys=True).encode()).hexdigest()


@pytest.fixture(name='cluster')
def cluster_fixture(sqlite_db):
    """Three nodes, and no BIOS anything until a test says otherwise."""
    for num in (1, 2, 3):
        Database().insert('node', [{"column": "name", "value": f'node00{num}'},
                                   {"column": "id", "value": num}])
    return ['node001', 'node002', 'node003']


def snapshot(nodeid, digest=None, config=None, config_digest=None,
             version='2.15.1', updated='2026-08-27 10:00:00'):
    row = [{"column": "nodeid", "value": nodeid},
           {"column": "source", "value": "redfish"},
           {"column": "bios_version", "value": version},
           {"column": "updated", "value": updated}]
    for column, value in (('bios_digest', digest), ('bios_config', config),
                          ('bios_config_digest', config_digest)):
        if value is not None:
            row.append({"column": column, "value": value})
    Database().insert('nodeinventory', row)


# --- the four states, each meaning something different ----------------------

def test_a_node_never_read_is_unknown_not_broken(cluster):
    """
    No Redfish inventory has been taken, so we have never looked. That is not a
    problem to report, it is an absence of an answer, and conflating the two is
    how a status view teaches people to ignore it.
    """
    status, response = Bios().status('node001')
    assert status is True
    assert response['config']['biosconfig']['status']['node001']['state'] == 'unknown'


def test_a_node_read_but_matching_nothing_is_collected(cluster):
    snapshot(1, digest=digest_of({'BootMode': 'Uefi'}))
    _, response = Bios().status('node001')
    row = response['config']['biosconfig']['status']['node001']
    assert row['state'] == 'collected'
    assert row['config'] == ''
    assert row['bios_version'] == '2.15.1'


def test_a_node_holding_what_it_was_pushed_is_matched(cluster):
    held = digest_of({'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled'})
    snapshot(1, digest=held, config='hpc-tuned', config_digest=held)
    _, response = Bios().status('node001')
    row = response['config']['biosconfig']['status']['node001']
    assert row['state'] == 'matched'
    assert row['config'] == 'hpc-tuned'
    assert row['since'] == '2026-08-27 10:00:00', 'when we looked, not now'


def test_a_bios_that_moved_since_it_matched_is_drifted(cluster):
    """
    The state that earns the third stored field. Somebody changed something
    outside Luna, or a push half landed - either way the configuration name alone
    would still say 'hpc-tuned' and would be a lie.
    """
    matched = digest_of({'BootMode': 'Uefi'})
    now = digest_of({'BootMode': 'Legacy'})
    snapshot(1, digest=now, config='hpc-tuned', config_digest=matched)
    _, response = Bios().status('node001')
    assert response['config']['biosconfig']['status']['node001']['state'] == 'drifted'


def test_the_digest_is_shortened_for_reading_but_compared_in_full(cluster):
    """A truncated digest in the output must not become a truncated comparison."""
    matched = digest_of({'a': 1})
    now = matched[:12] + 'f' * (len(matched) - 12)
    assert matched[:12] == now[:12], 'the test needs them to share a prefix'
    snapshot(1, digest=now, config='c', config_digest=matched)
    _, response = Bios().status('node001')
    row = response['config']['biosconfig']['status']['node001']
    assert row['state'] == 'drifted', 'compared on the prefix, they would look equal'
    assert len(row['digest']) == 12


# --- the summary, which is what makes it usable at scale --------------------

def test_the_summary_counts_every_node_exactly_once(cluster):
    held = digest_of({'BootMode': 'Uefi'})
    snapshot(1, digest=held, config='hpc-tuned', config_digest=held)
    snapshot(2, digest=digest_of({'BootMode': 'Legacy'}))
    _, response = Bios().status()
    summary = response['config']['biosconfig']['summary']
    assert summary == {'matched': 1, 'collected': 1, 'unknown': 1}
    assert sum(summary.values()) == len(response['config']['biosconfig']['status'])


def test_it_reads_the_database_and_never_the_machine(cluster, monkeypatch):
    """
    The whole point: a cluster of four thousand nodes, most of them off, answered
    without a single connection. If this ever starts contacting BMCs it stops
    being a thing you can run.
    """
    def refuse(*args, **kwargs):
        raise AssertionError('status contacted a BMC')

    monkeypatch.setattr('utils.redfish.Redfish.call', refuse)
    snapshot(1, digest=digest_of({'BootMode': 'Uefi'}))
    status, _ = Bios().status()
    assert status is True


def test_a_node_that_does_not_exist_is_refused_not_invented(cluster):
    status, message = Bios().status('node404')
    assert status is False
    assert 'node404' in message


# --- recording a match ------------------------------------------------------

def test_recording_a_match_writes_all_three_fields(cluster):
    snapshot(1, digest=digest_of({'BootMode': 'Legacy'}))
    held = digest_of({'BootMode': 'Uefi'})
    assert Bios().record_match(name='node001',
                               payload={'config': 'hpc-tuned', 'digest': held})
    _, response = Bios().status('node001')
    row = response['config']['biosconfig']['status']['node001']
    assert row['state'] == 'matched'
    assert row['config'] == 'hpc-tuned'


def test_recording_against_a_node_with_no_redfish_snapshot_does_not_invent_one(cluster):
    """
    A node we have never collected from has no row to annotate, and inventing one
    would put a BIOS record beside no inventory at all.
    """
    assert Bios().record_match(name='node001',
                               payload={'config': 'c', 'digest': 'abc'}) is False
    _, response = Bios().status('node001')
    assert response['config']['biosconfig']['status']['node001']['state'] == 'unknown'


# --- the digest itself ------------------------------------------------------

class BiosBmc():
    def __init__(self, attributes=None, bios=True):
        self.attributes = attributes
        self.bios = bios

    def get(self, path=None, cache=False):
        if path == '/redfish/v1/Systems/1/Bios' and self.attributes is not None:
            return True, {'Attributes': dict(self.attributes)}
        return False, 'no'


def system_with(bios=True):
    return {'Bios': {'@odata.id': '/redfish/v1/Systems/1/Bios'}} if bios else {}


def test_the_digest_ignores_the_order_attributes_arrive_in():
    """Two reads of one unchanged machine must not look like a change."""
    one = BiosBmc({'a': '1', 'b': '2'})
    two = BiosBmc({'b': '2', 'a': '1'})
    assert (NodeInventory().bios_digest(redfish=one, system=system_with())
            == NodeInventory().bios_digest(redfish=two, system=system_with()))


def test_a_changed_value_changes_the_digest():
    one = BiosBmc({'a': '1'})
    two = BiosBmc({'a': '2'})
    assert (NodeInventory().bios_digest(redfish=one, system=system_with())
            != NodeInventory().bios_digest(redfish=two, system=system_with()))


@pytest.mark.parametrize('bmc,system', [
    (BiosBmc(None), system_with()),
    (BiosBmc({}), system_with()),
    (BiosBmc({'a': '1'}), system_with(bios=False)),
])
def test_a_machine_with_no_bios_to_read_gets_no_digest(bmc, system):
    """
    Every one of these is a real board: licence-gated, exposing no Bios resource,
    or serving an empty attribute set. None of them is an error - they simply have
    nothing to fingerprint, and the status reads 'unknown' rather than a wrong
    answer.
    """
    assert NodeInventory().bios_digest(redfish=bmc, system=system) is None


# --- and it has to reach the other controller -------------------------------

def test_the_match_is_replicated_rather_than_written_straight_at_the_table():
    """
    nodeinventory is in Tables().tables, so the peer is expected to hold identical
    content and the controllers hash it. A push that recorded the match locally
    would work perfectly on the controller that ran it and leave the other one
    disagreeing on that table for good - which the secondary answers by clearing
    and re-importing the whole of it, per write.

    So the executor must hand it to the journal, and it must name a function the
    journal can actually dispatch. The collector beside it does the same thing for
    the same reason.
    """
    import ast
    import inspect

    from utils import bios_push

    source = inspect.getsource(bios_push.BiosPush.record_applied)
    tree = ast.parse(source.lstrip())
    functions = [
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == 'function' and isinstance(keyword.value, ast.Constant)
    ]
    assert functions == ['Bios.record_match'], (
        'the applied configuration must be recorded through Journal().add_request'
    )
    assert 'Database().update' not in source, 'that write would not reach the peer'
    # add_request queues for the PEER and applies nothing here, so the local write is
    # a second, separate call - and it is conditional on the queueing having been
    # accepted, because a controller that is not in sync must not write what it
    # cannot replicate. Proven on a live pair: without this the secondary held the
    # record and the controller that ran the push did not
    assert 'Bios().record_match(' in source, (
        'add_request does not apply locally; the caller has to, as every mutating '
        'route does'
    )
    assert source.index('add_request') < source.index('Bios().record_match('), (
        'queue for the peer first, then write locally - the other order writes what '
        'may never replicate'
    )
    assert 'if status is True' in source, (
        'the local write must be conditional on the peer having accepted the change'
    )


def test_the_journal_can_dispatch_what_the_executor_names():
    """
    The journal resolves a class by name out of its own globals, so a base class it
    does not import cannot be dispatched - and the failure lands on the *receiving*
    controller, after the request that caused it already returned success. Checked
    here rather than trusted.
    """
    from utils import journal

    assert hasattr(journal, 'Bios')
    assert callable(getattr(journal.Bios, 'record_match'))


def test_record_match_takes_the_shape_the_journal_dispatches():
    """
    add_request guesses arity from which of object/param/payload it was given, so a
    method reached with (object, payload) must accept exactly that. A signature that
    disagrees raises a TypeError on the peer and wedges replication.
    """
    import inspect

    parameters = list(inspect.signature(Bios.record_match).parameters)
    assert parameters == ['self', 'name', 'payload']


# --- the node's own vendor/assettag now come from the inventory ---------------

def test_the_node_columns_are_derived_from_the_snapshot(cluster):
    """
    They used to be collected separately: the install ran dmidecode a second time
    and POSTed a vendor and an assettag that update_inventory already sends as
    manufacturer and serial. One collection now feeds both.
    """
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'inband', 'manufacturer': 'Contoso',
                      'product': 'R750', 'serial': 'ABC123'}}}}})
    node = Database().get_record(table='node', where='name = "node001"')[0]
    assert node['vendor'] == 'Contoso'
    assert node['assettag'] == 'ABC123', 'assettag has always held the serial'


def test_an_out_of_band_collection_refreshes_them_too(cluster):
    """
    The point of deriving them. A board that was replaced used to keep reporting
    the machine it used to be until somebody reinstalled the node.
    """
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'inband', 'manufacturer': 'Contoso', 'serial': 'OLD'}}}}})
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'redfish', 'manufacturer': 'Fabrikam', 'serial': 'NEW'}}}}})
    node = Database().get_record(table='node', where='name = "node001"')[0]
    assert (node['vendor'], node['assettag']) == ('Fabrikam', 'NEW')


def test_redfish_wins_where_the_two_sources_disagree(cluster):
    """
    dmidecode and Redfish do not always spell a manufacturer the same way. The
    preference is the same one the plugin search path uses, deliberately: two
    rules for one question is how they drift apart.
    """
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'redfish', 'manufacturer': 'Fabrikam', 'serial': 'RF'}}}}})
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'inband', 'manufacturer': 'Contoso', 'serial': 'IB'}}}}})
    node = Database().get_record(table='node', where='name = "node001"')[0]
    assert (node['vendor'], node['assettag']) == ('Fabrikam', 'RF'), (
        'the in-band collection arrived last but must not win'
    )


def test_a_snapshot_that_says_nothing_leaves_the_columns_alone(cluster):
    """A machine that reports no manufacturer must not blank what we already knew."""
    Database().update('node', Helper().make_rows({'vendor': 'Contoso',
                                                  'assettag': 'ABC123'}),
                      [{"column": "name", "value": 'node001'}])
    NodeInventory().update_inventory('node001', {'config': {'node': {'node001': {
        'inventory': {'source': 'inband', 'cpu_count': 64}}}}})
    node = Database().get_record(table='node', where='name = "node001"')[0]
    assert (node['vendor'], node['assettag']) == ('Contoso', 'ABC123')


# --- BIOS is a group-level thing as much as a node-level one -----------------

def grouped(cluster):
    """node001+node002 in 'gpu', node003 in 'compute'."""
    Database().insert('group', [{"column": "name", "value": 'gpu'},
                                {"column": "id", "value": 1}])
    Database().insert('group', [{"column": "name", "value": 'compute'},
                                {"column": "id", "value": 2}])
    for nodeid, groupid in ((1, 1), (2, 1), (3, 2)):
        Database().update('node', Helper().make_rows({'groupid': groupid}),
                          [{"column": "id", "value": nodeid}])


def test_every_row_says_which_group_the_node_is_in(cluster):
    grouped(cluster)
    snapshot(1, digest=digest_of({'a': 1}))
    _, response = Bios().status()
    rows = response['config']['biosconfig']['status']
    assert rows['node001']['group'] == 'gpu'
    assert rows['node003']['group'] == 'compute'


def test_a_group_can_be_asked_about_on_its_own(cluster):
    """
    A GPU group and a plain compute group want different BIOS settings, so an
    operator has to be able to ask about one without reading past the other.
    """
    grouped(cluster)
    status, response = Bios().status(group='gpu')
    assert status is True
    rows = response['config']['biosconfig']['status']
    assert sorted(rows) == ['node001', 'node002'], 'compute must not be in here'
    assert sum(response['config']['biosconfig']['summary'].values()) == 2


def test_a_group_that_does_not_exist_and_one_with_no_nodes_are_different_answers(cluster):
    """
    'group' is a reserved SQL word, so a where clause naming it is a syntax error
    the daemon logs and swallows - and the caller then sees an empty result, which
    reads exactly like a group with no nodes. Empty and broken must not look alike.
    """
    grouped(cluster)
    Database().insert('group', [{"column": "name", "value": 'empty'},
                                {"column": "id", "value": 3}])
    missing = Bios().status(group='nosuchgroup')
    empty = Bios().status(group='empty')
    assert missing[0] is False and 'not available' in missing[1]
    assert empty[0] is False and 'no nodes' in empty[1]
    assert missing[1] != empty[1]


def test_naming_a_node_still_wins_over_a_group(cluster):
    grouped(cluster)
    _, response = Bios().status(name='node003', group='gpu')
    assert sorted(response['config']['biosconfig']['status']) == ['node003']


def test_the_group_lookup_is_one_query_not_one_per_node(cluster, monkeypatch):
    """
    At four thousand nodes the difference between a query and four thousand
    queries is the difference between a usable command and an unusable one.
    """
    grouped(cluster)
    calls = []
    original = Database.get_record

    def counting(self, select=None, table=None, where=None, orderby=None):
        calls.append(table)
        return original(self, select=select, table=table, where=where, orderby=orderby)

    monkeypatch.setattr(Database, 'get_record', counting)
    Bios().status()
    assert calls.count('group') == 1, f'group was read {calls.count("group")} times'
    assert calls.count('nodeinventory') == 1, (
        f'nodeinventory was read {calls.count("nodeinventory")} times - reading it '
        'per node is the cost this whole view exists to avoid'
    )
    assert len(calls) <= 3, f'{len(calls)} queries for a whole-cluster status'


def test_the_collector_records_whether_the_board_can_take_a_bios_write():
    """One read of the Bios resource serves the digest and the writable fact; a
    dummy settings object (no SettingsObject) is recorded as not writable."""
    from base.nodeinventory import NodeInventory
    from utils.bios_push import BiosPush

    class Bmc():
        def __init__(self, doc):
            self.doc = doc
        def get(self, path=None, cache=False):
            return (True, dict(self.doc)) if path == '/redfish/v1/Systems/1/Bios' else (False, 'no')

    writable = Bmc({'Attributes': {'A': 1},
                    '@Redfish.Settings': {'SettingsObject': {'@odata.id': '/redfish/v1/Systems/1/Bios/SD'}}})
    dummy = Bmc({'Attributes': {'A': 1}, '@Redfish.Settings': {'ETag': 'Dummyetag', 'Messages': []}})
    for client, expected in ((writable, '1'), (dummy, '0')):
        bios = NodeInventory().read_bios(redfish=client, system=system_with())
        assert ('1' if BiosPush().settings_path(bios=bios) else '0') == expected
        assert NodeInventory().bios_digest(bios=bios) == NodeInventory().bios_digest(redfish=client, system=system_with())
    assert NodeInventory().read_bios(redfish=dummy, system=system_with(bios=False)) is None
