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
import re
import sys
from ipaddress import ip_network

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


def _iface(routes=None, routes_ipv6=None, gateway='192.168.1.1', gateway_ipv6=''):
    return {'eth1': {
        'type': 'ethernet', 'networktype': 'ethernet', 'zone': 'trusted', 'mtu': '',
        'ipaddress': '10.141.0.5', 'prefix': '16', 'vlanid': '', 'vlan_parent': '',
        'ipaddress_ipv6': 'fd00::5', 'prefix_ipv6': '64',
        'nameserver_ip': ['10.141.0.1'], 'nameserver_ip_ipv6': ['fd00::1'],
        'gateway': gateway, 'gateway_ipv6': gateway_ipv6, 'gateway_metric': '101',
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
def test_nm_routes_render_on_dhcp_interface(name):
    """Static routes must also render on a DHCP (method=auto) interface (TRIX-1481:
    the internal/provision network is often DHCP, and NM applies routeN on top)."""
    iface = _iface(routes=[{'destination': '172.16.0.0/12', 'gateway': '10.141.255.254', 'metric': 200}])
    iface['eth1']['dhcp'] = True
    out = _env().get_template(f'{name}.templ').render(LUNA_INTERFACES=iface, **_CTX)
    assert 'method=auto' in out
    assert 'route1=172.16.0.0/12,10.141.255.254,200' in out


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_ipv6_route_without_gateway_is_route1(name):
    """Without an IPv6 gateway the first IPv6 route is route1."""
    out = _env().get_template(f'{name}.templ').render(
        LUNA_INTERFACES=_iface(routes_ipv6=[{'destination': 'fd10::/32', 'gateway': 'fd00::9', 'metric': None}]),
        **_CTX)
    assert 'route1=fd10::/32,fd00::9' in out


def _keyfile_routes(rendered):
    """Yield (section, destination) for every routeN= in the rendered NM keyfile."""
    section = None
    for line in rendered.splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line
        elif section in ('[ipv4]', '[ipv6]') and re.match(r'^route\d+=', line):
            yield section, line.split('=', 1)[1].split(',')[0]


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_route_destinations_match_the_family_of_their_section(name):
    """TRIX-1937: an [ipv6] route destination must be an IPv6 prefix, and vice versa.

    The IPv6 default route was written as 0.0.0.0/0 -- the IPv4 line, copied. It is not a
    parse error: NetworkManager reads the profile, verifies it, and silently drops the route,
    so the node comes up with an IPv6 address and no IPv6 default route. Nothing complains.

    This asserts the family of every route destination against the section it lands in rather
    than matching the one known-bad string, so a later IPv4 destination reaching [ipv6] by any
    other route -- the routes_ipv6 loop included -- fails here too.
    """
    out = _env().get_template(f'{name}.templ').render(
        LUNA_INTERFACES=_iface(gateway_ipv6='fd00::1',
                               routes_ipv6=[{'destination': 'fd10::/32', 'gateway': 'fd00::9', 'metric': 200}],
                               routes=[{'destination': '10.0.0.0/8', 'gateway': '10.141.255.254', 'metric': 200}]),
        **_CTX)
    found = list(_keyfile_routes(out))
    assert found, "no routes rendered at all -- the fixture no longer reaches the route lines"
    for section, destination in found:
        expected = 4 if section == '[ipv4]' else 6
        assert ip_network(destination, strict=False).version == expected, (
            f"{name}.templ rendered {destination} as a route destination inside {section}. "
            f"NetworkManager drops it silently -- the profile loads and the route is simply absent."
        )


@pytest.mark.parametrize('name', NM_TEMPLATES)
def test_nm_ipv6_gateway_renders_the_ipv6_default_route(name):
    """The IPv6 default route is ::/0, and the IPv4 one is still 0.0.0.0/0."""
    out = _env().get_template(f'{name}.templ').render(
        LUNA_INTERFACES=_iface(gateway_ipv6='fd00::1'), **_CTX)
    assert 'route1=::/0,fd00::1,101' in out
    assert 'route1=0.0.0.0/0,192.168.1.1,101' in out, "the IPv4 default route was collateral damage"


def _ub_iface(routes=None, routes_ipv6=None, dhcp=False, gateway='10.145.255.254'):
    return {'eth0': {
        'type': 'ethernet', 'networktype': 'ethernet', 'zone': 'trusted', 'mtu': '',
        'ipaddress': '10.145.0.5', 'prefix': '16', 'vlanid': '', 'vlan_parent': '',
        'ipaddress_ipv6': '', 'prefix_ipv6': '', 'nameserver_ip': ['10.145.0.1'],
        'nameserver_ip_ipv6': [], 'gateway': '' if dhcp else gateway, 'gateway_ipv6': '',
        'gateway_metric': '101', 'dhcp': dhcp, 'options': '', 'master': '',
        'routes': routes or [], 'routes_ipv6': routes_ipv6 or []}}
    # no bond keys: the daemon only puts them on a bond, and the netplan template
    # branches on their presence


def test_netplan_static_route():
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(routes=[{'destination': '10.30.0.0/16', 'gateway': '172.16.0.33', 'metric': 300}]),
        interface='eth0', PROVISION_INTERFACE='eth0', NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert '- to: 10.30.0.0/16' in out and 'via: 172.16.0.33' in out and 'metric: 300' in out


def test_netplan_onlink_route_uses_scope_link():
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(routes=[{'destination': '10.88.0.0/16', 'gateway': '', 'metric': 66}]),
        interface='eth0', PROVISION_INTERFACE='eth0', NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert '- to: 10.88.0.0/16' in out and 'scope: link' in out


def test_netplan_offlink_route_emits_on_link():
    """An off-link next-hop (binder set on_link) renders via + on-link: true so
    systemd-networkd installs the route instead of stalling the interface."""
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(routes=[{'destination': '10.30.0.0/16', 'gateway': '10.9.9.1', 'metric': 300, 'on_link': True}]),
        interface='eth0', PROVISION_INTERFACE='eth0', NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert 'via: 10.9.9.1' in out and 'on-link: true' in out


def test_netplan_on_link_line_absent_for_on_link_nexthop():
    """A directly-reachable next-hop carries no on_link flag, so on-link is not emitted."""
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(routes=[{'destination': '10.30.0.0/16', 'gateway': '172.16.0.33', 'metric': 300}]),
        interface='eth0', PROVISION_INTERFACE='eth0', NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert 'on-link: true' not in out


def test_netplan_routes_render_on_dhcp_interface():
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(routes=[{'destination': '172.16.0.0/12', 'gateway': '172.16.0.33', 'metric': 200}], dhcp=True),
        interface='eth0', PROVISION_INTERFACE='eth0', NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert 'dhcp4: True' in out and '- to: 172.16.0.0/12' in out


def _ub_bond(slaves, mode='active-backup'):
    iface = _ub_iface()['eth0']
    iface.update({'type': 'bond', 'bond_mode': mode, 'bond_slaves': slaves})
    return {'bond0': iface}


def _netplan_bond(slaves, mode='active-backup', provision='BOOTIF'):
    return _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_bond(slaves, mode), interface='bond0', PROVISION_INTERFACE=provision,
        NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])


BOND_MODES = ['balance-rr', 'active-backup', 'balance-xor', 'broadcast', '802.3ad', 'balance-tlb', 'balance-alb']


@pytest.mark.parametrize('mode', BOND_MODES + [str(n) for n in range(7)])
def test_netplan_bond_renders_its_mode_by_name(mode):
    """A bond without parameters runs netplan's default balance-rr whatever was configured;
    the daemon also accepts the numeric modes, which netplan does not."""
    out = _netplan_bond(['eth1', 'eth2'], mode)
    expected = BOND_MODES[int(mode)] if mode.isdigit() else mode
    assert f'mode: {expected}' in out
    assert 'mii-monitor-interval: 100' in out


def test_netplan_bond_parameters_sit_under_the_bond():
    out = _netplan_bond(['eth1', 'eth2'], '802.3ad')
    bond = out[out.index('bonds:'):]
    assert bond.index('parameters:') < bond.index('addresses:')
    assert 'parameters:' not in out[:out.index('bonds:')]


def test_netplan_ethernet_has_no_bond_parameters():
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(), interface='eth0', PROVISION_INTERFACE='eth0',
        NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert 'bonds:' not in out and 'parameters:' not in out


def test_netplan_bond_carries_its_first_slaves_mac():
    """Without a macaddress networkd derives the bond's from the machine-id, and every
    node booted from one image shares that - so all bonds ended up with one MAC."""
    out = _netplan_bond(['eth1', 'eth2'])
    assert 'macaddress: $(cat /sys/class/net/eth1/address)' in out
    assert out.count('macaddress:') == 1


def test_netplan_bond_on_the_provisioning_interface_reads_the_bootif_mac():
    """The provisioning slave is only a placeholder name in the config; its MAC is read
    from the interface the boot actually came in on."""
    out = _netplan_bond(['BOOTIF', 'eth2'])
    assert 'macaddress: $(cat /sys/class/net/${interface_bootif}/address)' in out
    assert 'BOOTIF/address' not in out


def test_netplan_ethernet_sets_no_macaddress():
    out = _env().get_template('ubuntu.templ').render(
        LUNA_INTERFACES=_ub_iface(), interface='eth0', PROVISION_INTERFACE='eth0',
        NODE_NAME='node002', DOMAIN_SEARCH=['cluster'])
    assert 'macaddress' not in out


def test_database_layout_shape():
    sys.path.insert(0, os.path.join(DAEMON, 'common'))
    import database_layout as dl
    route_cols = [c['column'] for c in dl.DATABASE_LAYOUT_route]
    assert route_cols == ['id', 'name', 'destination', 'gateway', 'metric', 'device', 'comment',
                          'owners', 'usergroups', 'access']
    name_meta = [c for c in dl.DATABASE_LAYOUT_route if c['column'] == 'name'][0]
    assert name_meta.get('key') == 'UNIQUE'
    map_cols = [c['column'] for c in dl.DATABASE_LAYOUT_routemap]
    assert map_cols == ['id', 'tableref', 'tablerefid', 'routeid']
    # routemap must not impose a composite unique that would cap one route per target
    assert not any(c.get('with') for c in dl.DATABASE_LAYOUT_routemap)


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
