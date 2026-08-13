#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1937 unit tests for address-family purity in the rendered DHCP configuration.

A v4 service config may contain only v4 addresses and a v6 config only v6 ones. This is
not a preference: the server refuses the config. dhcpd fails to parse an IPv6 address in
a v4 option and rejects the whole file, and kea fails the entire subnet4 element rather
than the offending line. Either way the daemon keeps the last-good config, so the fault
surfaces as "DHCP stopped changing" rather than as an error where the mistake was made.

Helper().check_ip() accepts both families, so a field validated with it alone accepts
either. The fields here reach a family-specific renderer and must therefore decide.

Helper().check_if_ipv6() is the one place that decision is made, and every guard routes
through it rather than repeating a colon test. It used to answer True for a leading [a-f]
as well as for a colon, which reads a name like europe.pool.ntp.org as IPv6 -- so it
rejected the server names ntp_server exists to accept, and bracketed host names into
broken URLs in the request layer. It now tests the colon alone: no IPv4 address and no
host name can contain one, and no valid IPv6 address is without one. These tests pin both
halves -- that it still catches IPv6, and that it no longer catches names.
"""

import inspect

import pytest

from base.cluster import Cluster
from utils.config import Config
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.helper import Helper


@pytest.fixture
def cluster_db(db):
    """The shared db fixture plus the single cluster row update_cluster validates against."""
    Database().create('cluster', DBStructure().get_database_table_structure('cluster'))
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    return db


def _update_cluster(payload):
    return Cluster().update_cluster({'config': {'cluster': payload}})


# ---------------------------------------------------------------- the shared family test
# Pure, and the foundation of every guard below.

@pytest.mark.parametrize('value', ['fd00::1', '2001:db8::5', 'fd00::/64', '::1'])
def test_check_if_ipv6_catches_addresses(value):
    assert Helper().check_if_ipv6(value) is True, f"{value!r} is IPv6 and was not detected"


@pytest.mark.parametrize('value', [
    '10.141.255.1', '192.168.164.225', '10.141.0.0/16',
    'europe.pool.ntp.org', 'debian.pool.ntp.org', 'africa.pool.ntp.org',
    'clock.example.com', 'ntp.example.com', '0.pool.ntp.org',
    'controller1', 'ha2-controller2.cluster',
    '', None,
])
def test_check_if_ipv6_does_not_catch_ipv4_or_names(value):
    """A leading a-f is a letter, not an address family."""
    assert Helper().check_if_ipv6(value) is False, (
        f"{value!r} was read as IPv6. That rejects valid NTP server names, and brackets host "
        f"names into broken URLs in utils/request.py."
    )


# ---------------------------------------------------------------- cluster fields
# These render into dhcpd.conf as GLOBAL options, so a bad value costs the whole file
# rather than one subnet.

@pytest.mark.parametrize('field', ['ntp_server', 'nameserver_ip'])
def test_cluster_v4_field_rejects_ipv6(cluster_db, field):
    """An IPv6 address here is a dhcpd parse error that discards the entire config."""
    status, response = _update_cluster({field: 'fd00::1'})
    assert status is False and 'IPv4 address is expected' in str(response), (
        f"cluster.{field} accepted an IPv6 address. It renders into dhcpd.conf as a global "
        f"option, where it is a parse error: the whole file is rejected and DHCPv4 silently "
        f"freezes on its last-good config. Got: {response}"
    )


# The mirror case -- that a valid IPv4 value still passes -- is pinned at the helper
# instead of here: check_if_ipv6('10.141.255.1') is False above, so the guard cannot fire
# on IPv4. Driving the accepting path through update_cluster would run past validation
# into Service(), which builds and executes a real command, and a unit test must not
# shell out.


# ---------------------------------------------------------------- network.ntp_server
# This field accepts a server NAME as well as an address, which is what makes the family
# test subtle: a name is not an address and must not be read as one.
#
# It is no longer guarded at the input, and that is a deliberate move rather than a removal.
# The field feeds BOTH families -- the dhcp6 ntp-server option (56) carries an IPv6 address
# or a name where the dhcp4 option (42) carries neither -- so it belongs with dhcp_relay
# below, filtered per family at the render, and not with the cluster fields above, which
# render into one family's config and are rejected at the input. Rejecting IPv6 here left
# the only family able to serve it unable to hold it, so no administrator could reach that
# half of the rendering at all.
#
# The entry point and each template's emission are pinned in tests/unit/test_ntp_server.py.
# What stays here is the reading of a NAME, which is what this file is about, and what a
# family test on this field gets wrong first.

@pytest.mark.parametrize('hostname', [
    'europe.pool.ntp.org',   # leading 'e'
    'debian.pool.ntp.org',   # leading 'd'
    'africa.pool.ntp.org',   # leading 'a'
    'clock.example.com',     # leading 'c'
])
def test_ntp_hostnames_are_not_read_as_ipv6(hostname):
    """The values that were rejected in the field, at the level that decides it."""
    assert Helper().check_if_ipv6(hostname) is False, (
        f"{hostname!r} is a server name. Read as IPv6 it is classified as an address, so the "
        f"dhcp6 config carries it as srv-addr, which kea rejects: a name is not an address."
    )


# ---------------------------------------------------------------- dhcp_relay render
# One field feeds both templates and has no _ipv6 twin, so the render filters it.

def _relays_for(ipversion, dhcp_relay):
    """The relay list dhcp_subnet_config would hand to the template for one family."""
    relays = [relay.strip() for relay in (dhcp_relay or '').split(',') if relay.strip()]
    return [relay for relay in relays if Helper().check_if_ipv6(relay) == (ipversion == 'ipv6')]


@pytest.mark.parametrize('ipversion,dhcp_relay,expected', [
    ('ipv4', '10.141.255.1,fd00::1', ['10.141.255.1']),
    ('ipv6', '10.141.255.1,fd00::1', ['fd00::1']),
    ('ipv4', 'fd00::1', []),
    ('ipv6', '10.141.255.1', []),
    ('ipv4', '10.141.255.1,10.141.255.2', ['10.141.255.1', '10.141.255.2']),
    ('ipv6', 'fd00::1,fd00::2', ['fd00::1', 'fd00::2']),
    ('ipv4', '', []),
])
def test_dhcp_relay_render_filters_by_family(ipversion, dhcp_relay, expected):
    """Each config carries only its own family. A mismatch fails the whole subnet element."""
    assert _relays_for(ipversion, dhcp_relay) == expected


def test_dhcp_relay_filter_matches_the_renderer():
    """Pin the filter to the real code, so this test cannot drift from what ships."""
    source = inspect.getsource(Config.dhcp_subnet_config)
    assert "check_if_ipv6(relay) == (ipversion == 'ipv6')" in source, (
        "dhcp_subnet_config no longer filters dhcp_relay by address family. An IPv6 relay in the "
        "kea dhcp4 config fails the entire subnet4 element: 'address fd00::1 is not a: IPv4address'."
    )
