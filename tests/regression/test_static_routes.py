#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1481 regression tests for static routes.

These cover the parts that can be exercised without a running daemon:
- the per-OS network .templ files render routes additively (no coupled routes ->
  identical to the legacy gateway-only output) and correctly (NM keyfile routeN,
  netplan routes:, on-link);
- the route/routemap database layouts have the expected shape.
"""

import os
import sys

import pytest
from jinja2 import Environment, FileSystemLoader

HERE = os.path.dirname(__file__)
DAEMON = os.path.abspath(os.path.join(HERE, '..', '..', 'daemon'))
NETDIR = os.path.join(DAEMON, 'plugins', 'boot', 'network')
NM_TEMPLATES = ['redhat8', 'redhat9', 'redhat10', 'opensuse']


def _env():
    env = Environment(loader=FileSystemLoader(NETDIR))
    env.filters['b64decode'] = lambda value: ""
    return env


def _iface(routes=None, routes_ipv6=None, gateway='192.168.1.1'):
    return {'eth1': {
        'type': 'ethernet', 'networktype': 'ethernet', 'zone': 'trusted', 'mtu': '',
        'ipaddress': '10.141.0.5', 'prefix': '16', 'vlanid': '', 'vlan_parent': '',
        'ipaddress_ipv6': 'fd00::5', 'prefix_ipv6': '64',
        'nameserver_ip': ['10.141.0.1'], 'nameserver_ip_ipv6': ['fd00::1'],
        'gateway': gateway, 'gateway_ipv6': '', 'gateway_metric': '101',
        'dhcp': None, 'options': '', 'master': '', 'bond_mode': '', 'bond_slaves': [],
        'routes': routes or [], 'routes_ipv6': routes_ipv6 or []}}


_CTX = dict(interface='eth1', PROVISION_INTERFACE='eth1', NODE_NAME='node002',
            DOMAIN_SEARCH=['cluster'])


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_additive_without_routes(name):
    """With no coupled routes only the gateway route1 is present (no route2+)."""
    out = _env().get_template(f'{name}.templ').render(LUNA_INTERFACES=_iface(), **_CTX)
    assert 'route1=0.0.0.0/0,192.168.1.1,101' in out
    assert 'route2' not in out


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_renders_routes(name):
    """A next-hop route becomes route2, an on-link route uses an empty next-hop."""
    routes = [
        {'destination': '10.0.0.0/8', 'gateway': '10.141.255.254', 'metric': 200},
        {'destination': '192.168.9.0/24', 'gateway': '', 'metric': 50},
    ]
    out = _env().get_template(f'{name}.templ').render(
        LUNA_INTERFACES=_iface(routes=routes), **_CTX)
    assert 'route2=10.0.0.0/8,10.141.255.254,200' in out
    assert 'route3=192.168.9.0/24,,50' in out


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_ipv6_route_without_gateway_is_route1(name):
    """Without an IPv6 gateway the first IPv6 route is route1."""
    out = _env().get_template(f'{name}.templ').render(
        LUNA_INTERFACES=_iface(routes_ipv6=[{'destination': 'fd10::/32', 'gateway': 'fd00::9', 'metric': None}]),
        **_CTX)
    assert 'route1=fd10::/32,fd00::9' in out


def test_database_layout_shape():
    sys.path.insert(0, os.path.join(DAEMON, 'common'))
    import database_layout as dl
    route_cols = [c['column'] for c in dl.DATABASE_LAYOUT_route]
    assert route_cols == ['id', 'name', 'destination', 'gateway', 'metric', 'device', 'comment']
    name_meta = [c for c in dl.DATABASE_LAYOUT_route if c['column'] == 'name'][0]
    assert name_meta.get('key') == 'UNIQUE'
    map_cols = [c['column'] for c in dl.DATABASE_LAYOUT_routemap]
    assert map_cols == ['id', 'tableref', 'tablerefid', 'routeid']
    # routemap must not impose a composite unique that would cap one route per target
    assert not any(c.get('with') for c in dl.DATABASE_LAYOUT_routemap)


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
