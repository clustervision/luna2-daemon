#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1921 unit tests for option-82.5 (RFC 3527) link-selection support.

A relay that rewrites subnet selection with option 82 sub-option 5 makes Kea match the
link-selection address against subnet ranges and ignore relay.ip-addresses. The fix wraps
an opted-in network in a Kea shared-networks block: a pool-less anchor on the relay's link
prefix beside the boot subnet. These tests pin the pieces that are easy to get wrong:

 * the anchor prefix is family-correct and a bare address is refused (check_cidr);
 * config normalises the CSV to network form and drops the wrong family (dhcp_link_anchors);
 * a link requires a relay, and clearing the relay clears the link (validation + cascade);
 * the boot-subnet body is one Jinja macro, so the plain subnet and the link boot subnet
   cannot drift -- this is the guard for the copy-paste bug the feature was built to avoid.
"""

import inspect
import json
import os
import re

import pytest

from base.network import Network
from utils.config import Config
from utils.helper import Helper

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates')


# ------------------------------------------------------------------ check_cidr helper

@pytest.mark.parametrize('value,ipv6,expected', [
    ('10.144.35.0/24', False, True),
    ('10.144.35.253/24', False, True),      # host bits ok, normalised at render
    ('2001:db8:35::/64', True, True),
    ('10.144.35.0/24', True, False),        # wrong family
    ('2001:db8:35::/64', False, False),     # wrong family
    ('10.144.35.5', False, False),          # bare address, no prefix
    ('2001:db8:35::5', True, False),        # bare address, no prefix
    ('not-a-cidr', False, False),
    ('', False, False),
    ('10.144.35.0/24', None, True),         # family-agnostic still validates
])
def test_check_cidr(value, ipv6, expected):
    assert Helper().check_cidr(value, ipv6=ipv6) is expected


# ------------------------------------------------------------------ dhcp_link_anchors

@pytest.mark.parametrize('value,ipversion,expected', [
    ('10.144.35.253/24', 'ipv4', ['10.144.35.0/24']),          # normalised to network form
    ('10.144.35.0/24,10.144.36.0/24', 'ipv4', ['10.144.35.0/24', '10.144.36.0/24']),
    ('2001:db8:35::/64', 'ipv6', ['2001:db8:35::/64']),
    ('10.144.35.0/24,2001:db8:35::/64', 'ipv4', ['10.144.35.0/24']),   # drop wrong family
    ('10.144.35.0/24,2001:db8:35::/64', 'ipv6', ['2001:db8:35::/64']),
    ('', 'ipv4', []),
])
def test_dhcp_link_anchors(value, ipversion, expected):
    assert Config().dhcp_link_anchors(value, ipversion) == expected


# ------------------------------------------------------------------ validation & cascade
# Pinned to the shipping source in the same style as the dhcp_relay guards, so the rule
# cannot quietly disappear without failing here.

def test_link_requires_relay_is_validated():
    source = inspect.getsource(Network.update_network)
    assert "requires dhcp_relay to be set first" in source, (
        "dhcp_link_subnet no longer requires dhcp_relay. A link anchor is only meaningful on a "
        "relayed path; without a relay it is a misconfiguration.")


def test_link_is_validated_as_cidr():
    source = inspect.getsource(Network.update_network)
    assert "Helper().check_cidr(link, ipv6=None)" in source, (
        "dhcp_link_subnet entries are no longer validated as CIDRs of either family before being "
        "stored in the single twinless field.")


def test_clearing_relay_cascades_to_clear_link():
    source = inspect.getsource(Network.update_network)
    assert "data['dhcp_relay'] == ''" in source and "data['dhcp_link_subnet'] = ''" in source, (
        "clearing dhcp_relay no longer cascade-clears dhcp_link_subnet, so an orphaned option-82.5 "
        "anchor can be left behind.")


def test_link_field_triggers_dhcp_refresh():
    source = inspect.getsource(Network)
    assert "'dhcp_link_subnet'," in source, (
        "dhcp_link_subnet is missing from the DHCP runtime-refresh trigger set; a change to it "
        "would not regenerate the DHCP config.")


# ------------------------------------------------------------------ macro drift guard
# The boot-subnet body must be one source of truth. If the plain SUBNETS loop and the link
# boot subnet ever diverge, a feature (domain-name, ipxe class, reservations, ...) is present
# on a plain relay network and silently absent on a link network, or vice versa.

def _render(template, ctx):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    out = env.get_template(template).render(**ctx)
    return json.loads("\n".join(re.sub(r'#.*$', '', line) for line in out.splitlines()))


def _boot_subnet4():
    return {'network': '10.143.0.0', 'prefix': '24', 'netmask': '255.255.255.0', 'domain': 'edge',
            'nameserver_ip': '10.141.0.1', 'ntp_server': '10.141.0.1', 'nextserver': '10.141.0.1',
            'nextport': 7050, 'dhcp_relay': ['10.144.53.7'], 'range_begin': '10.143.0.20',
            'range_end': '10.143.0.200'}


def _strip(subnet):
    """Drop the fields that legitimately differ between a plain and a link boot subnet."""
    s = dict(subnet)
    s.pop('id', None)
    for pool in s.get('pools', []):
        pool.pop('client-class', None)      # the fence is link-only
    return s


def test_v4_link_boot_body_matches_plain_subnet_body():
    boot = _boot_subnet4()
    ctx = dict(CLASSES={}, SHARED={}, SUBNETS={'edge': boot}, ZONES={}, EMPTY={}, POOLS={},
               LINKSEL={}, DOMAINNAME='c', NAMESERVERS='10.141.0.1', NTPSERVERS='10.141.0.1',
               RESERVATIONS={'edge': []}, OMAPIKEY=None, TSIGKEY=None, TSIGALGO=None)
    plain = _render('templ_kea-dhcp4.cfg', ctx)['Dhcp4']['subnet4'][0]

    ctx2 = dict(ctx, SUBNETS={}, LINKSEL={'edge': {'anchor': ['10.144.35.0/24'], 'boot': boot}})
    link_net = _render('templ_kea-dhcp4.cfg', ctx2)['Dhcp4']['shared-networks'][0]['subnet4']
    link_boot = [s for s in link_net if s['subnet'] == '10.143.0.0/24'][0]

    assert _strip(plain) == _strip(link_boot), (
        "the v4 link boot subnet drifted from the plain SUBNETS body -- boot_subnet macro is not "
        "the single source, or a caller stopped using it.")


def test_v4_anchor_is_pool_less_and_authoritative_false():
    boot = _boot_subnet4()
    ctx = dict(CLASSES={}, SHARED={}, SUBNETS={}, ZONES={}, EMPTY={}, POOLS={},
               LINKSEL={'edge': {'anchor': ['10.144.35.0/24'], 'boot': boot}}, DOMAINNAME='c',
               NAMESERVERS='10.141.0.1', NTPSERVERS='10.141.0.1', RESERVATIONS={'edge': []},
               OMAPIKEY=None, TSIGKEY=None, TSIGALGO=None)
    subs = _render('templ_kea-dhcp4.cfg', ctx)['Dhcp4']['shared-networks'][0]['subnet4']
    anchor = [s for s in subs if s['subnet'] == '10.144.35.0/24'][0]
    assert anchor['pools'] == [] and anchor['authoritative'] is False


def test_v4_fence_preserves_plain_giaddr():
    """The pool fence must admit any plain-giaddr client and only gate the 82.5 path."""
    source = open(os.path.join(TEMPLATE_DIR, 'templ_kea-dhcp4.cfg')).read()
    assert "(not relay4[5].exists) or" in source, (
        "the link boot-class fence no longer starts with (not relay4[5].exists); it would deny "
        "non-boot clients arriving via plain giaddr, changing the merged relay behaviour.")


# ------------------------------------------------------------------ the anchor and its group
# An anchor is one pool-less subnet in the kea config, and kea refuses the whole configuration
# when the same prefix is rendered twice. These pin the two halves that keep that impossible:
# validation refuses a prefix another group already claims, and the render de-duplicates within
# a group and drops - loudly - anything that slipped past.

def test_duplicate_anchor_across_groups_is_refused():
    source = inspect.getsource(Network.update_network)
    assert "same_shared_group" in source and "is already " in source, (
        "a dhcp_link_subnet already claimed by a network outside this one's shared group is no "
        "longer refused. kea allows a prefix in one shared-network only and refuses the entire "
        "configuration otherwise, so the DHCP config silently stops tracking the database.")


def test_same_shared_group_reads_the_pending_value():
    """A request that joins a group must be judged on where it is going, not where it has been."""
    source = inspect.getsource(Network.same_shared_group)
    assert "'shared' in data" in source, (
        "same_shared_group no longer prefers the pending 'shared' value over the stored one, so a "
        "request that joins a group is judged against its old group.")


def test_render_drops_a_duplicate_anchor_rather_than_emitting_it():
    source = inspect.getsource(Config.dhcp_overwrite)
    assert "kea allows a prefix in one" in source and "anchors[group].remove(prefix)" in source, (
        "the render no longer drops a duplicated link anchor. Validation refuses one, but a "
        "database that predates it would produce a configuration kea rejects in its entirety - "
        "and dhcp_overwrite then holds BOTH families back, so nothing at all is installed.")


def test_anchor_joins_the_shared_group_it_belongs_to():
    source = inspect.getsource(Config.dhcp_overwrite)
    assert "group = shared_group_of.get(key)" in source, (
        "a link anchor no longer joins its network's shared group. Split into a private block, the "
        "group siblings sit outside every scope kea can reach from the anchor, so a node reserved "
        "in a sibling is served from the wrong network's pool.")


def test_kea_class_reference_is_a_name_and_never_an_expression():
    """kea reads a client-class value as a NAME. An expression there matches nothing and takes the
    subnet out of selection, with nothing reported at parse time or at run time."""
    for template in ('templ_kea-dhcp4.cfg', 'templ_kea-dhcp6.cfg'):
        body = open(os.path.join(TEMPLATE_DIR, template), encoding='utf-8').read()
        for line in body.splitlines():
            if '"client-class"' not in line and '"client-classes"' not in line:
                continue
            value = line.split(':', 1)[1]
            assert 'not member(' not in value and ' or member(' not in value, (
                f"{template} puts an expression where kea expects a class name: {line.strip()}")


def test_kea_templates_use_the_spelling_both_platforms_accept():
    """Plural client-classes at subnet or pool level is kea 3.0 only; kea 2.6 refuses the whole
    file - and because both families install together, that holds DHCPv4 back as well."""
    for template in ('templ_kea-dhcp4.cfg', 'templ_kea-dhcp6.cfg'):
        body = open(os.path.join(TEMPLATE_DIR, template), encoding='utf-8').read()
        for line in body.splitlines():
            # the bare '"client-classes": [' that opens the definition array carries no value
            if '"client-classes"' not in line or line.strip() == '"client-classes": [':
                continue
            assert "HOST[" in line, (
                f"{template} uses the plural client-classes outside a host reservation, which "
                f"kea 2.6 (EL9, EL10.0) refuses: {line.strip()}")


# ------------------------------------------------------------------ is the group one link?
# luna's 'shared' means "the same wire" for a host and its BMC, and is only the precondition
# dhcp_relay insists on for a relayed network. An anchor may join the group only in the first
# sense, so this truth table is where the judgement lives.

def _nets(**spec):
    """name -> row, from name=(shared_carrier, relays) pairs."""
    return {name: {'shared': shared, 'dhcp_relay': relay}
            for name, (shared, relay) in spec.items()}


@pytest.mark.parametrize('networks,network,carrier,expected,why', [
    # the wire: nobody is relayed, so nothing argues the link is not shared
    (_nets(cluster=(None, None), ipmi=('cluster', None)), 'cluster', 'cluster', True,
     'a group with no relays anywhere is one wire'),
    # the reported case: two networks reached through the same relays
    (_nets(cluster=(None, '10.0.12.7,10.0.12.8'), inband=('cluster', '10.0.12.7,10.0.12.8')),
     'cluster', 'cluster', True, 'relays in common are the evidence the link is shared'),
    # an untidy relay list still overlaps, and the anchor should still merge
    (_nets(cluster=(None, '10.0.12.7,10.0.12.8'), inband=('cluster', '10.0.11.253,10.0.12.7')),
     'cluster', 'cluster', True, 'a partial overlap is still the same link'),
    # two relayed networks on different links: merging would make selection ambiguous
    (_nets(cluster=(None, None), remote=('cluster', '10.0.150.1'), edge=('cluster', '10.0.160.1')),
     'edge', 'cluster', False, 'a relayed member on another link must keep the anchor out'),
    # a member with no relay is on the wire and cannot be picked out by a relay either way
    (_nets(cluster=(None, '10.0.160.1'), ipmi=('cluster', None)), 'cluster', 'cluster', True,
     'an unrelayed member does not argue against a shared link'),
    # networks outside the group are irrelevant however they are relayed
    (_nets(cluster=(None, '10.0.160.1'), other=(None, '10.0.99.1')), 'cluster', 'cluster', True,
     'a network in another group has no bearing on this one'),
])
def test_dhcp_group_shares_link(networks, network, carrier, expected, why):
    assert Config().dhcp_group_shares_link(network, carrier, networks) is expected, why
