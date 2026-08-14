#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1939 unit tests for how the DHCPv6 config names a controller interface.

kea selects a subnet6 by the interface a request arrived on, or by the relay that forwarded
it. The template used to name a hardcoded interface for any subnet the controller has no
address in -- and kea refuses to parse a config naming an interface the host does not have,
failing the WHOLE file rather than that subnet. So one unmatched network took DHCPv6 down
for every network, and a relayed subnet, which correctly has no local interface, could never
be served at all.

The interface line is therefore emitted only when a real interface matched. A relayed subnet
is selected by its relay; a subnet with neither is unservable either way and is reported by
dhcp_overwrite instead of being allowed to discard the configuration.

These tests pin the emission per block type -- plain, shared, and the option-82.5 link-selection
shared-network -- because each looks the interface up differently, and a subnet that renders
without one still has to be a subnet kea accepts.
"""

import json
import os
import re

import pytest

from utils.config import Config

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates')


def _sub6(net, **extra):
    subnet = {'network': net, 'prefix': '64', 'domain': net.replace(':', ''),
              'nameserver_ip_ipv6': '2001:db8:1::1', 'ntp_server': None,
              'range_begin': net + '20', 'range_end': net + '200'}
    subnet.update(extra)
    return subnet


def _render6(interfaces, subnets=None, shared=None, linksel=None, fallback=''):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    names = list((subnets or {})) + [n for share in (shared or {}).values() for n in share] + \
        list((linksel or {}))
    out = env.get_template('templ_kea-dhcp6.cfg').render(
        CLASSES={}, SHARED=shared or {}, SUBNETS=subnets or {}, ZONES={}, EMPTY={}, POOLS={},
        LINKSEL=linksel or {}, INTERFACES=interfaces, FALLBACK_INTERFACE=fallback, DOMAINNAME='c',
        NAMESERVERS='2001:db8:1::1', NAMESERVERS_IPV6='2001:db8:1::1', NTPSERVERS='',
        RESERVATIONS={name: [] for name in names}, OMAPIKEY=None, TSIGKEY=None, TSIGALGO=None)
    return json.loads("\n".join(re.sub(r'#.*$', '', line) for line in out.splitlines()))


def _subnet6_blocks(rendered):
    blocks = list(rendered['Dhcp6'].get('subnet6', []))
    for share in rendered['Dhcp6'].get('shared-networks', []):
        blocks.extend(share.get('subnet6', []))
    return blocks


def test_matched_network_still_names_its_interface():
    """The normal case, and the one that must not move: a controller address in the network."""
    blocks = _subnet6_blocks(_render6({'a': 'eth0'}, subnets={'a': _sub6('2001:db8:a::')}))
    assert [b.get('interface') for b in blocks] == ['eth0']


def test_unmatched_network_names_no_interface():
    """kea refuses the whole file over an interface the host does not have."""
    blocks = _subnet6_blocks(_render6({}, subnets={'a': _sub6('2001:db8:a::')}))
    assert 'interface' not in blocks[0], (
        f"an unmatched subnet still names an interface ({blocks[0].get('interface')!r}). kea "
        f"rejects the entire configuration when that name is not present on the host, which "
        f"takes down DHCPv6 for every other network too.")


def test_relayed_subnet_renders_without_an_interface():
    """A relayed subnet has no local interface by definition; the relay is what selects it."""
    subnet = _sub6('2001:db8:b::', dhcp_relay=['2001:db8:ff::1'])
    blocks = _subnet6_blocks(_render6({}, subnets={'b': subnet}))
    assert 'interface' not in blocks[0], "a relayed subnet must not name a local interface"
    assert blocks[0]['relay'] == {'ip-addresses': ['2001:db8:ff::1']}, (
        "the relay block is what kea selects a relayed subnet by; it must survive.")


def test_shared_member_falls_back_to_the_shared_networks_interface():
    """Existing behaviour: a member with no interface of its own uses the share's."""
    shared = {'cluster': {'member': _sub6('2001:db8:c::')}}
    blocks = _subnet6_blocks(_render6({'cluster': 'eth0'}, shared=shared))
    assert [b.get('interface') for b in blocks] == ['eth0']


def test_shared_member_without_any_match_names_no_interface():
    shared = {'cluster': {'member': _sub6('2001:db8:c::', dhcp_relay=['2001:db8:ff::1'])}}
    blocks = _subnet6_blocks(_render6({}, shared=shared))
    assert 'interface' not in blocks[0]
    assert blocks[0]['relay'] == {'ip-addresses': ['2001:db8:ff::1']}


def test_link_selection_subnet_keeps_its_anchor_and_relay():
    """TRIX-1921's option-82.5 block: a link-anchored subnet is relayed, never local."""
    linksel = {'linked': {'anchor': ['2001:db8:d::/64'],
                          'boot': _sub6('2001:db8:e::', dhcp_relay=['2001:db8:ff::1'])}}
    rendered = _render6({}, linksel=linksel)
    # The shared-network holds the anchor subnet(s) and the boot subnet; only the second is
    # the one this template renders through the shared macro.
    boot = [b for b in _subnet6_blocks(rendered) if b['subnet'] == '2001:db8:e::/64'][0]
    assert 'interface' not in boot, "a link-anchored subnet must not name a local interface"
    assert boot['relay'] == {'ip-addresses': ['2001:db8:ff::1']}
    anchors = json.dumps(rendered['Dhcp6']['shared-networks'])
    assert '2001:db8:d::/64' in anchors, "the link-selection anchor subnet must still render"


# ---------------------------------------------------------------- the manual override
# Naming an interface for a subnet we cannot match was deliberate -- a way to force one on a
# controller whose interface cannot be found by address. That capability is kept; what changes
# is that the name comes from [DHCP] INTERFACE6 in luna.ini, which the installer can render on
# both controllers, instead of a literal in a template the next package upgrade replaces.

@pytest.mark.parametrize('block', ['subnets', 'shared', 'linksel'])
def test_configured_fallback_is_used_for_an_unmatched_subnet(block):
    subnet = _sub6('2001:db8:a::')
    kwargs = {'subnets': {'a': subnet}} if block == 'subnets' else \
        {'shared': {'cluster': {'a': subnet}}} if block == 'shared' else \
        {'linksel': {'a': {'anchor': ['2001:db8:d::/64'], 'boot': subnet}}}
    blocks = [b for b in _subnet6_blocks(_render6({}, fallback='ens6', **kwargs))
              if b['subnet'] == '2001:db8:a::/64']
    assert blocks[0].get('interface') == 'ens6', (
        f"the configured fallback interface is ignored for a {block} subnet; an administrator "
        f"who set [DHCP] INTERFACE6 gets no interface at all.")


def test_a_matched_interface_still_wins_over_the_fallback():
    blocks = _subnet6_blocks(_render6({'a': 'eth0'}, subnets={'a': _sub6('2001:db8:a::')},
                                      fallback='ens6'))
    assert blocks[0]['interface'] == 'eth0', "a real match must beat the configured fallback"


def test_no_hardcoded_interface_name_remains():
    """The defect was a literal interface name that only ever matched one developer's box."""
    source = open(os.path.join(TEMPLATE_DIR, 'templ_kea-dhcp6.cfg'), encoding='utf-8').read()
    assert 'ens6' not in source, (
        "templ_kea-dhcp6.cfg names a fixed interface again. kea fails the whole configuration "
        "when it is not present on the host.")


# ---------------------------------------------------------------- the report that replaces it
# Dropping the line means an unservable subnet no longer announces itself by destroying the
# configuration. It has to announce itself somewhere, so dhcp_overwrite names it in the log.

def test_unservable_subnets_are_reported():
    plain = {'lonely': _sub6('2001:db8:a::')}
    relayed = {'reachable': _sub6('2001:db8:b::', dhcp_relay=['2001:db8:ff::1'])}
    shared = {'cluster': {'orphan': _sub6('2001:db8:c::')}}
    linksel = {'linked': {'anchor': ['2001:db8:d::/64'],
                          'boot': _sub6('2001:db8:e::', dhcp_relay=['2001:db8:ff::1'])}}
    reported = Config().dhcp6_unservable({**plain, **relayed}, shared, linksel, {})
    assert sorted(reported) == ['lonely', 'orphan'], (
        "a subnet with neither a controller interface nor a relay can never be selected by kea, "
        "and nothing else in the pipeline says so.")


def test_matched_or_relayed_subnets_are_not_reported():
    subnets = {'matched': _sub6('2001:db8:a::'),
               'relayed': _sub6('2001:db8:b::', dhcp_relay=['2001:db8:ff::1'])}
    shared = {'cluster': {'viashare': _sub6('2001:db8:c::')}}
    assert Config().dhcp6_unservable(subnets, shared, {}, {'matched': 'eth0', 'cluster': 'eth1'}) == []
