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


# ------------------------------------------------------------------ the shared-group pool wiring
# dhcp_shared_pools decides, per member of a group, which pool it gets and what gates it. Three
# inputs interact - whether the member is relayed, whether the family wants the allow/deny policy,
# and whether the group carries a link anchor - and each combination has bitten.

def _group(**members):
    """name -> subnet dict, from name=relay pairs ('' for an unrelayed member)."""
    subnets = {}
    for name, relay in members.items():
        subnets[name] = {'network': '10.0.0.0', 'prefix': '16'}
        if relay:
            subnets[name]['dhcp_relay'] = [relay]
    return subnets


def _pools(*names, **ranges):
    pools = {name: {'range_begin': '10.0.1.1', 'range_end': '10.0.1.9'} for name in names}
    pools.update(ranges)
    return pools


def test_shared_pools_wire_members_are_told_apart_by_class():
    """The ipmi case: nobody is relayed, so the class is the only thing distinguishing them."""
    subnets = _group(cluster='', ipmi='')
    derived = Config().dhcp_shared_pools(subnets=subnets, pools=_pools('cluster-ipmi', 'ipmi'),
                                         group='cluster-ipmi', carrier='cluster', members=['ipmi'])
    assert subnets['cluster']['pool_class'] == 'cluster-ipmi-carrier-class'
    assert subnets['ipmi']['pool_class'] == 'ipmi-class'
    assert subnets['cluster']['range_begin'] == '10.0.1.1'
    assert [entry['name'] for entry in derived] == ['cluster-ipmi-carrier-class']
    assert derived[0]['test'] == "not member('ipmi-class')"


def test_shared_pools_the_carrier_excludes_every_member():
    """Two members, so the joiner is actually exercised: the carrier serves what is in NONE of
    them. Joined with 'or' it would serve anything outside any one of them - which is nearly
    everything, and a BMC would be able to draw from the carrier's pool."""
    subnets = _group(cluster='', ipmi='', bmc2='')
    derived = Config().dhcp_shared_pools(
        subnets=subnets, pools=_pools('cluster-ipmi-bmc2', 'ipmi', 'bmc2'),
        group='cluster-ipmi-bmc2', carrier='cluster', members=['ipmi', 'bmc2'])
    assert derived[0]['test'] == "not member('ipmi-class') and not member('bmc2-class')"


def test_shared_pools_a_relayed_member_gets_no_policy_class():
    """It is picked out by its relay. A class there refuses its own network's PXE clients, which
    then fall through to the carrier's pool and boot on the wrong subnet."""
    subnets = _group(cluster='', remote='10.0.150.1')
    Config().dhcp_shared_pools(subnets=subnets, pools=_pools('cluster-remote', 'remote'),
                               group='cluster-remote', carrier='cluster', members=['remote'])
    assert subnets['cluster']['pool_class'] == 'cluster-remote-carrier-class'
    assert 'pool_class' not in subnets['remote']
    assert subnets['remote']['range_begin'] == '10.0.1.1', 'it still gets its pool'


def test_shared_pools_an_anchored_group_fences_every_pool():
    """A foreign device on the link reaches the server too, so nothing in the block is left open.
    A member that also has a policy class gets both, as one derived class - kea takes one name."""
    subnets = _group(cluster='', inband='10.0.12.7')
    derived = Config().dhcp_shared_pools(subnets=subnets, pools=_pools('cluster-inband', 'inband'),
                                         group='cluster-inband', carrier='cluster',
                                         members=['inband'], fence='cluster-inband-boot-class')
    assert subnets['cluster']['pool_class'] == 'cluster-inband-cluster-pool-class'
    assert subnets['inband']['pool_class'] == 'cluster-inband-boot-class', (
        'a relayed member has no policy class, so the fence stands alone')
    names = [entry['name'] for entry in derived]
    assert names.index('cluster-inband-carrier-class') < names.index('cluster-inband-cluster-pool-class'), (
        'kea refuses a member() reference to a class defined later in the list')
    combined = [e for e in derived if e['name'] == 'cluster-inband-cluster-pool-class'][0]
    assert combined['test'] == ("member('cluster-inband-carrier-class') "
                                "and member('cluster-inband-boot-class')")


def test_shared_pools_v6_takes_no_policy_class_but_still_fences():
    """DHCPv6 expresses the same choice at subnet level, so its pools are left alone - except for
    the fence, which has no subnet-level equivalent."""
    subnets = _group(cluster='', inband='10.0.12.7')
    derived = Config().dhcp_shared_pools(subnets=subnets, pools=_pools('cluster-inband', 'inband'),
                                         group='cluster-inband', carrier='cluster',
                                         members=['inband'], policy=False,
                                         fence='cluster-inband-boot-class')
    assert subnets['cluster']['pool_class'] == 'cluster-inband-boot-class'
    assert subnets['inband']['pool_class'] == 'cluster-inband-boot-class'
    assert derived == [], 'no carrier negation and no combination is needed without the policy'


def test_shared_pools_a_member_with_no_range_gets_no_pool_and_no_class():
    """dhcp_nodes_only, or a network with no range: it still belongs in the block for its
    reservations, and a class on a pool it does not have would be meaningless."""
    subnets = _group(cluster='', ipmi='')
    Config().dhcp_shared_pools(subnets=subnets, pools=_pools('cluster-ipmi'),
                               group='cluster-ipmi', carrier='cluster', members=['ipmi'])
    assert 'pool_class' not in subnets['ipmi'] and 'range_begin' not in subnets['ipmi']
    assert subnets['cluster']['pool_class'] == 'cluster-ipmi-carrier-class'


# ------------------------------------------------------------------ the DHCPv6 selection class
# DHCPv6 carries the boot URL in a class, so every subnet is gated on the boot classes built for
# it. That is a list, which only kea 3.0 accepts; one derived class says the same thing on both.

def test_dhcp6_select_class_piggyback_on_the_wire_uses_its_own_class():
    name, definition = Config().dhcp6_select_class(subnet={}, name='ipmi', group='cluster-ipmi',
                                                   piggyback=True)
    assert (name, definition) == ('ipmi-class', None), 'the template already defines that one'


def test_dhcp6_select_class_a_relayed_piggyback_is_gated_on_boot_classes():
    """Relayed, so its own class does not apply - it is selected by the relay and gated like any
    other subnet."""
    subnet = {'dhcp_relay': ['10.0.12.7'], 'nextserver': '10.0.0.1'}
    name, definition = Config().dhcp6_select_class(subnet=subnet, name='inband',
                                                   group='cluster-inband', piggyback=True)
    assert name == 'cluster-inband-inband-select-class'
    assert definition['test'] == ("member('ipxe-cluster-inband-inband') or "
                                  "member('arch-x86-cluster-inband-inband') or "
                                  "member('arch-arm64-cluster-inband-inband') or "
                                  "member('arch-openpower')")


def test_dhcp6_select_class_a_plain_subnet_is_named_without_a_group():
    subnet = {'nextserver': '10.0.0.1'}
    name, definition = Config().dhcp6_select_class(subnet=subnet, name='cluster')
    assert name == 'cluster-select-class'
    assert "member('ipxe-cluster')" in definition['test']
    assert 'cluster-cluster' not in definition['test'], 'no group means no group in the names'


def test_dhcp6_select_class_without_a_nextserver_only_openpower_remains():
    """No next server means no boot URL to offer, so the arch and ipxe classes are not built for it
    and naming them would gate the subnet on classes that do not exist."""
    name, definition = Config().dhcp6_select_class(subnet={}, name='storage')
    assert name == 'storage-select-class'
    assert definition['test'] == "member('arch-openpower')"
