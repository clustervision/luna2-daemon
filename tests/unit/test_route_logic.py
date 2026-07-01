#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1481 unit tests for the Route class, run against a throwaway SQLite database
(see conftest.py). These exercise the real catalog CRUD, coupling/reconcile,
rename, clone/delete coupling hooks, the in-use delete guard, and the boot-time
route resolution (scope precedence, dedup, and interface binding).
"""

from conftest import make_route


def _interfaces(clusterid, extid):
    """Two interfaces mirroring what boot.py assembles: BOOTIF on cluster, ext01 on ext."""
    return {
        'BOOTIF': {'network': '10.141.0.5/16', 'network_ipv6': 'fd00:141::5/64',
                   'networkid': clusterid, 'routes': [], 'routes_ipv6': []},
        'ext01':  {'network': '10.145.0.5/16', 'network_ipv6': None,
                   'networkid': extid, 'routes': [], 'routes_ipv6': []},
    }


# --------------------------------------------------------------------------- #
# validation                                                                  #
# --------------------------------------------------------------------------- #

def test_validate_accepts_ipv4_and_ipv6(db):
    from base.route import Route
    assert Route().validate_route('10.0.0.0/8', '10.141.255.254', '', 200)[0]
    assert Route().validate_route('fd00::/8', 'fd00::1', '', None)[0]
    assert Route().validate_route('10.0.0.0/8', '', 'ext01', None)[0]


def test_validate_rejects_bad_cidr_missing_target_and_family_mismatch(db):
    from base.route import Route
    assert not Route().validate_route('not-a-cidr', '10.0.0.1', '', None)[0]
    assert not Route().validate_route('10.0.0.0/8', '', '', None)[0]
    assert not Route().validate_route('10.0.0.0/8', 'not-an-ip', '', None)[0]
    assert not Route().validate_route('fd00::/8', '10.141.255.254', '', None)[0]  # v6 dest, v4 hop
    assert not Route().validate_route('10.0.0.0/8', '10.0.0.1', '', 'abc')[0]     # metric not a number


# --------------------------------------------------------------------------- #
# catalog CRUD, coupling, reconcile                                           #
# --------------------------------------------------------------------------- #

def test_reconcile_add_replace_clear(db, seed):
    from base.route import Route
    make_route('a', '10.1.0.0/16', '10.141.0.1')
    make_route('b', '10.2.0.0/16', '10.141.0.2')
    make_route('c', '10.3.0.0/16', '10.141.0.3')
    Route().reconcile('node', seed['nodeid'], ['a', 'b'])
    assert sorted(Route().assigned_names('node', seed['nodeid'])) == ['a', 'b']
    Route().reconcile('node', seed['nodeid'], 'a,c')          # replace
    assert sorted(Route().assigned_names('node', seed['nodeid'])) == ['a', 'c']
    Route().reconcile('node', seed['nodeid'], '')             # clear
    assert Route().assigned_names('node', seed['nodeid']) == []


def test_reconcile_ignores_unknown_names(db, seed):
    from base.route import Route
    make_route('a', '10.1.0.0/16', '10.141.0.1')
    Route().reconcile('node', seed['nodeid'], ['a', 'ghost'])
    assert Route().assigned_names('node', seed['nodeid']) == ['a']


def test_coupled_targets_and_delete_guard(db, seed):
    from base.route import Route
    make_route('vpn', '172.16.0.0/12', '10.141.255.254')
    Route().reconcile('node', seed['nodeid'], ['vpn'])
    routeid = db.get_record(table='route', where="name='vpn'")[0]['id']
    assert Route().coupled_targets(routeid) == ['node/node001']
    ok, _ = Route().delete_route('vpn')
    assert not ok                                             # refused while coupled
    Route().reconcile('node', seed['nodeid'], '')
    ok, _ = Route().delete_route('vpn')
    assert ok                                                 # allowed once free


def test_rename_keeps_couplings(db, seed):
    from base.route import Route
    make_route('old', '10.9.0.0/16', '10.141.0.9')
    Route().reconcile('node', seed['nodeid'], ['old'])
    routeid = db.get_record(table='route', where="name='old'")[0]['id']
    status, _ = Route().update_route('old', {'config': {'route': {'old': {'newname': 'new'}}}})
    assert status
    assert db.get_record(table='route', where=f"id={routeid}")[0]['name'] == 'new'   # same row
    assert Route().assigned_names('node', seed['nodeid']) == ['new']                  # coupling followed


def test_rename_rejects_clash(db, seed):
    from base.route import Route
    make_route('a', '10.1.0.0/16', '10.141.0.1')
    make_route('b', '10.2.0.0/16', '10.141.0.2')
    status, _ = Route().update_route('a', {'config': {'route': {'a': {'newname': 'b'}}}})
    assert not status


def test_partial_change_preserves_other_fields(db):
    from base.route import Route
    make_route('r', '10.4.0.0/16', '10.141.0.4', metric=100)
    Route().update_route('r', {'config': {'route': {'r': {'metric': 300}}}})
    row = db.get_record(table='route', where="name='r'")[0]
    assert row['destination'] == '10.4.0.0/16' and row['gateway'] == '10.141.0.4' and str(row['metric']) == '300'


def test_copy_and_delete_couplings(db, seed):
    from base.route import Route
    make_route('a', '10.1.0.0/16', '10.141.0.1')
    Route().reconcile('node', seed['nodeid'], ['a'])
    other = db.insert('node', __import__('utils.helper', fromlist=['Helper']).Helper().make_rows(
        {'name': 'node002', 'groupid': seed['groupid']}))
    Route().copy_couplings('node', seed['nodeid'], other)
    assert Route().assigned_names('node', other) == ['a']
    Route().delete_couplings('node', other)
    assert Route().assigned_names('node', other) == []


# --------------------------------------------------------------------------- #
# boot-time resolution: binding, precedence, dedup                            #
# --------------------------------------------------------------------------- #

def test_resolve_subnet_match_binds_to_cluster(db, seed):
    from base.route import Route
    make_route('vpn', '172.16.0.0/12', '10.141.255.254')      # hop in cluster
    Route().reconcile('node', seed['nodeid'], ['vpn'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == '172.16.0.0/12' for r in ifaces['BOOTIF']['routes'])
    assert ifaces['ext01']['routes'] == []


def test_resolve_device_overrides_subnet(db, seed):
    from base.route import Route
    make_route('dev', '10.30.0.0/16', '10.141.0.9', device='ext01')   # hop in cluster, device ext01
    Route().reconcile('node', seed['nodeid'], ['dev'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == '10.30.0.0/16' for r in ifaces['ext01']['routes'])
    assert ifaces['BOOTIF']['routes'] == []


def test_resolve_bootif_device_maps_to_provision(db, seed):
    from base.route import Route
    make_route('b', '10.31.0.0/16', '10.141.0.9', device='BOOTIF')
    Route().reconcile('node', seed['nodeid'], ['b'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'ext01')          # provision is ext01 here
    assert any(r['destination'] == '10.31.0.0/16' for r in ifaces['ext01']['routes'])


def test_resolve_unknown_device_falls_back_to_provision(db, seed):
    from base.route import Route
    make_route('g', '10.32.0.0/16', '', device='ghost0')              # non-existing interface
    Route().reconcile('node', seed['nodeid'], ['g'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == '10.32.0.0/16' for r in ifaces['BOOTIF']['routes'])


def test_resolve_onlink_route_has_empty_nexthop(db, seed):
    from base.route import Route
    make_route('l', '10.33.0.0/16', '', device='ext01')              # device, no gateway
    Route().reconcile('node', seed['nodeid'], ['l'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    entry = [r for r in ifaces['ext01']['routes'] if r['destination'] == '10.33.0.0/16'][0]
    assert entry['gateway'] == ''


def test_resolve_ipv6_route_goes_to_ipv6_bucket(db, seed):
    from base.route import Route
    make_route('6', 'fd10::/32', 'fd00:141::9')
    Route().reconcile('node', seed['nodeid'], ['6'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == 'fd10::/32' for r in ifaces['BOOTIF']['routes_ipv6'])
    assert ifaces['BOOTIF']['routes'] == []


def test_resolve_no_interfaces_is_a_noop(db, seed):
    from base.route import Route
    make_route('vpn', '172.16.0.0/12', '10.141.255.254')
    Route().reconcile('node', seed['nodeid'], ['vpn'])
    empty = {}
    Route().resolve_for_node(empty, seed['nodeid'], 'BOOTIF')          # must not raise
    assert empty == {}


def test_resolve_precedence_node_over_group_over_network(db, seed):
    from base.route import Route
    # same destination + metric at all three scopes, different next-hops
    make_route('net', '10.50.0.0/16', '10.141.0.1', metric=100)
    make_route('grp', '10.50.0.0/16', '10.141.0.2', metric=100)
    make_route('nod', '10.50.0.0/16', '10.141.0.3', metric=100)
    Route().reconcile('network', seed['clusterid'], ['net'])
    Route().reconcile('group', seed['groupid'], ['grp'])
    Route().reconcile('node', seed['nodeid'], ['nod'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    hops = [r['gateway'] for r in ifaces['BOOTIF']['routes'] if r['destination'] == '10.50.0.0/16']
    assert hops == ['10.141.0.3']                                     # node wins, once


def test_resolve_node_overrides_group_entirely(db, seed):
    """Strict override: a node with its own routes ignores group routes completely."""
    from base.route import Route
    make_route('nod', '10.1.0.0/16', '10.141.0.1')
    make_route('grp', '10.2.0.0/16', '10.141.0.2')
    Route().reconcile('node', seed['nodeid'], ['nod'])
    Route().reconcile('group', seed['groupid'], ['grp'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    dests = [r['destination'] for r in ifaces['BOOTIF']['routes']]
    assert '10.1.0.0/16' in dests and '10.2.0.0/16' not in dests


def test_resolve_group_overrides_network_base(db, seed):
    """A group with routes ignores the network base entirely."""
    from base.route import Route
    make_route('grp', '10.4.0.0/16', '10.141.0.1')
    make_route('net', '10.5.0.0/16', '10.141.0.2')
    Route().reconcile('group', seed['groupid'], ['grp'])
    Route().reconcile('network', seed['clusterid'], ['net'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    dests = [r['destination'] for r in ifaces['BOOTIF']['routes']]
    assert '10.4.0.0/16' in dests and '10.5.0.0/16' not in dests


def test_resolve_falls_back_to_network_base(db, seed):
    """With no node or group routes, the network base applies."""
    from base.route import Route
    make_route('net', '10.3.0.0/16', '10.141.0.9')
    Route().reconcile('network', seed['clusterid'], ['net'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == '10.3.0.0/16' for r in ifaces['BOOTIF']['routes'])


def test_resolve_same_dest_different_metric_keeps_both(db, seed):
    from base.route import Route
    make_route('m1', '10.60.0.0/16', '10.141.0.1', metric=100)
    make_route('m2', '10.60.0.0/16', '10.141.0.2', metric=200)
    Route().reconcile('node', seed['nodeid'], ['m1', 'm2'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    metrics = sorted(str(r['metric']) for r in ifaces['BOOTIF']['routes'] if r['destination'] == '10.60.0.0/16')
    assert metrics == ['100', '200']


def test_resolve_network_scope_binds_via_interface_networkid(db, seed):
    from base.route import Route
    make_route('net', '10.70.0.0/16', '10.145.0.9')                  # hop in ext subnet
    Route().reconcile('network', seed['extid'], ['net'])
    ifaces = _interfaces(seed['clusterid'], seed['extid'])
    Route().resolve_for_node(ifaces, seed['nodeid'], 'BOOTIF')
    assert any(r['destination'] == '10.70.0.0/16' for r in ifaces['ext01']['routes'])
