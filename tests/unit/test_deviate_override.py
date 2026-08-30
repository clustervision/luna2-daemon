#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1854 unit tests: what makes a node or a group report that it deviates.

'luna node list -d' and 'luna group list -d' show what holds something of its own
rather than inheriting it, and both reads carry an _override flag saying so. Two
things were wrong with that flag.

A node or group holding its own static route did not raise it. The routes are
resolved through their own lookup rather than the inheritance chain the rest of the
fields go through, so the bulk read computed the route's source and never used it,
and the single read set the flag and then met an initialiser that cleared it.

The other way round, every freshly created group raised it: group creation wrote the
literal 'default' into its own ipxe_kernel column, and a column holding something is
what the flag means. The read supplies 'default' as the displayed fallback anyway, so
the column can stay empty and nothing downstream notices -- the only consumer of a
group's ipxe_kernel treats empty and 'default' identically.

Both directions are tested: the flag has to rise for a real deviation and stay down
for an inherited value, or it means nothing.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables these reads touch."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'node', 'cluster', 'osimage', 'osimagetag', 'bmcsetup',
                  'redfishsetup', 'network', 'groupinterface', 'nodeinterface',
                  'ipaddress', 'monitor', 'queue', 'route', 'routemap',
                  'groupsecrets', 'nodesecrets', 'switch', 'cloud']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    from utils.helper import Helper
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def seed(db):
    """A group, a node in it, and a route that is not yet coupled to anything."""
    from utils.helper import Helper

    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    nodeid = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    routeid = db.insert('route', Helper().make_rows(
        {'name': 'r1', 'destination': '10.0.0.0/8', 'gateway': '10.141.0.1'}))
    return {'groupid': groupid, 'nodeid': nodeid, 'routeid': routeid}


def couple(db, routeid, tableref, tablerefid):
    """Attach a route to a node, a group or a network."""
    from utils.helper import Helper
    db.insert('routemap', Helper().make_rows(
        {'routeid': routeid, 'tableref': tableref, 'tablerefid': tablerefid}))


def node_flags(name):
    """Returns _override as the listing reports it and as the single read does."""
    from base.node import Node
    _, listing = Node().get_all_nodes()
    _, single = Node().get_node(name=name)
    return (listing['config']['node'][name].get('_override'),
            single['config']['node'][name].get('_override'))


def group_flags(name):
    """The same pair, for a group."""
    from base.group import Group
    _, listing = Group().get_all_group()
    _, single = Group().get_group(name=name)
    return (listing['config']['group'][name].get('_override'),
            single['config']['group'][name].get('_override'))


def test_a_node_holding_its_own_route_deviates(db, seed):
    couple(db, seed['routeid'], 'node', seed['nodeid'])
    assert node_flags('node001') == (True, True)


def test_a_group_holding_its_own_route_deviates(db, seed):
    couple(db, seed['routeid'], 'group', seed['groupid'])
    assert group_flags('compute') == (True, True)


def test_a_node_inheriting_its_group_s_route_does_not_deviate(db, seed):
    """
    The guard that stops the fix becoming the opposite bug: the node has routes, and
    they are not its own.
    """
    couple(db, seed['routeid'], 'group', seed['groupid'])
    assert node_flags('node001') == (False, False)


def test_nothing_of_its_own_means_no_deviation(db, seed):
    assert node_flags('node001') == (False, False)
    assert group_flags('compute') == (False, False)


def test_a_new_group_does_not_deviate_on_ipxe_kernel(db):
    """A group nobody has configured cannot differ from what it would inherit."""
    from base.group import Group

    status, response = Group().update_group(name='fresh', request_data={'config': {'group': {
        'fresh': {'name': 'fresh',
                  'interfaces': [{'interface': 'BOOTIF', 'network': 'cluster'}]}}}})
    assert status is True, f'could not create the group: {response}'
    assert db.get_record(table='group', where='name = "fresh"')[0]['ipxe_kernel'] is None, \
        'group creation wrote a value into a column the operator never set'
    assert group_flags('fresh') == (False, False)


def test_an_empty_column_still_shows_default_as_the_fallback(db):
    """
    Leaving the column empty must not change the value an operator sees. What does
    change is the source beside it: 'default' rather than 'group', which is the
    honest answer and the reason the flag stops rising.
    """
    from base.group import Group

    Group().update_group(name='fresh', request_data={'config': {'group': {
        'fresh': {'name': 'fresh',
                  'interfaces': [{'interface': 'BOOTIF', 'network': 'cluster'}]}}}})
    _, single = Group().get_group(name='fresh')
    shown = single['config']['group']['fresh']
    assert shown['ipxe_kernel'] == 'default'
    assert shown['_ipxe_kernel_source'] == 'default'


def test_a_group_that_really_sets_ipxe_kernel_still_deviates(db):
    """The other direction: the flag must still rise for a value the operator chose."""
    from base.group import Group

    Group().update_group(name='fresh', request_data={'config': {'group': {
        'fresh': {'name': 'fresh',
                  'interfaces': [{'interface': 'BOOTIF', 'network': 'cluster'}]}}}})
    Group().update_group(name='fresh', request_data={'config': {'group': {
        'fresh': {'ipxe_kernel': 'alternative'}}}})
    assert group_flags('fresh') == (True, True)


def dhcp_rebuilds(db):
    """The DHCP rebuilds queued so far, as (task, parameter, who asked)."""
    rows = db.get_record(table='queue', where='param = "dhcp"') or []
    return [(row['task'], row['param'], row['request_id']) for row in rows]


def test_changing_a_node_s_ipxe_kernel_rebuilds_dhcp(db, seed):
    """
    The iPXE binary is named per host in the DHCP configuration, so the setting
    reaches the node only once that is rendered again. Stored without a rebuild it
    is a value in a column and nothing else - the node keeps booting the old one.
    Clearing it hands the node the group's choice, which is a change just the same.
    """
    from base.node import Node
    status, response = Node().update_node(name='node001', request_data={'config': {'node': {
        'node001': {'comment': 'nothing the DHCP config renders'}}}})
    assert status is True, response
    assert dhcp_rebuilds(db) == []
    status, response = Node().update_node(name='node001', request_data={'config': {'node': {
        'node001': {'ipxe_kernel': 'alternative'}}}})
    assert status is True, response
    assert dhcp_rebuilds(db) == [('restart', 'dhcp', '__node_update__')]
    # the queue keeps one copy of a task still waiting; taken, it must be asked again
    db.delete_row('queue', [{'column': 'param', 'value': 'dhcp'}])
    status, response = Node().update_node(name='node001', request_data={'config': {'node': {
        'node001': {'ipxe_kernel': ''}}}})
    assert status is True, response
    assert dhcp_rebuilds(db) == [('restart', 'dhcp', '__node_update__')]


def test_changing_a_group_s_ipxe_kernel_rebuilds_dhcp(db, seed):
    """Every node in the group is rendered with the binary the group gives it."""
    from base.group import Group
    status, response = Group().update_group(name='compute', request_data={'config': {'group': {
        'compute': {'comment': 'nothing the DHCP config renders'}}}})
    assert status is True, response
    assert dhcp_rebuilds(db) == []
    status, response = Group().update_group(name='compute', request_data={'config': {'group': {
        'compute': {'ipxe_kernel': 'alternative'}}}})
    assert status is True, response
    assert dhcp_rebuilds(db) == [('restart', 'dhcp', '__group_update__')]
