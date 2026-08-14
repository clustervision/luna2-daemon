#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1939 unit tests for NTP-server address-family handling in the DHCP config.

An ntp_server may be an IPv4 address, an IPv6 address, or a host name, and the two DHCP
families carry different subsets: the dhcp4 ntp-servers option (42) takes IPv4 addresses
only, while the dhcp6 ntp-server option (56, RFC 5908) is a container whose address goes in
the srv-addr sub-option and whose name goes in the srv-fqdn sub-option. Feeding kea a value
its option cannot hold fails the whole subnet element, so config.py classifies the value
once (ntp_server_kind) and each template emits only what it can carry, dropping the rest.

These tests render the shipping templates and pin that split: the v4 config emits ntp-servers
only for an IPv4 value; the v6 config emits srv-addr for an IPv6 value and srv-fqdn for a name,
and neither for an IPv4 value.
"""

import inspect
import json
import os
import re

import pytest

from base.network import Network
from utils.config import Config
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.queue import Queue
from utils.service import Service

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates')


def _kind(ntp):
    """The classification config.py applies, reproduced for the fixtures."""
    if not ntp:
        return None
    if ':' in ntp:
        return 'ipv6'
    try:
        import ipaddress
        ipaddress.ip_address(ntp)
        return 'ipv4'
    except ValueError:
        return 'fqdn'


def _render(template, ctx):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    out = env.get_template(template).render(**ctx)
    return json.loads("\n".join(re.sub(r'#.*$', '', line) for line in out.splitlines()))


def _sub4(net, ntp):
    return {'network': net, 'prefix': '24', 'netmask': '255.255.255.0', 'domain': net,
            'nameserver_ip': '10.1.0.1', 'ntp_server': ntp, 'ntp_server_kind': _kind(ntp),
            'range_begin': net.rsplit('.', 1)[0] + '.20', 'range_end': net.rsplit('.', 1)[0] + '.200'}


def _sub6(net, ntp):
    return {'network': net, 'prefix': '64', 'domain': net, 'nameserver_ip_ipv6': '2001:db8:1::1',
            'ntp_server': ntp, 'ntp_server_kind': _kind(ntp),
            'range_begin': net + '20', 'range_end': net + '200'}


def _opt_names(subnet):
    return [o.get('name') for o in subnet.get('option-data', [])]


def _ctx4(subnets):
    return dict(CLASSES={}, SHARED={}, SUBNETS=subnets, ZONES={}, EMPTY={}, POOLS={}, LINKSEL={},
                DOMAINNAME='c', NAMESERVERS='10.1.0.1', NTPSERVERS='10.1.0.1',
                RESERVATIONS={k: [] for k in subnets}, OMAPIKEY=None, TSIGKEY=None, TSIGALGO=None)


def _ctx6(subnets):
    return dict(CLASSES={}, SHARED={}, SUBNETS=subnets, ZONES={}, EMPTY={}, POOLS={}, LINKSEL={},
                INTERFACES={}, DOMAINNAME='c', NAMESERVERS='2001:db8:1::1', NAMESERVERS_IPV6='2001:db8:1::1',
                NTPSERVERS='', RESERVATIONS={k: [] for k in subnets}, OMAPIKEY=None, TSIGKEY=None, TSIGALGO=None)


def test_v4_emits_ntp_servers_only_for_ipv4():
    subs = {'a': _sub4('10.1.0.0', '10.1.0.9'), 'b': _sub4('10.2.0.0', '2001:db8:1::9'),
            'c': _sub4('10.3.0.0', 'europe.pool.ntp.org')}
    d = _render('templ_kea-dhcp4.cfg', _ctx4(subs))['Dhcp4']['subnet4']
    got = {s['subnet']: ('ntp-servers' in _opt_names(s)) for s in d}
    assert got == {'10.1.0.0/24': True, '10.2.0.0/24': False, '10.3.0.0/24': False}, (
        "the dhcp4 ntp-servers option (42) must be emitted only for an IPv4 ntp_server; an IPv6 "
        "address or a host name fails 'Failed to convert string to address' and takes the whole "
        "subnet4 element with it.")


def test_v6_emits_srv_addr_for_ipv6_and_srv_fqdn_for_name():
    subs = {'a': _sub6('2001:db8:a::', '10.1.0.9'), 'b': _sub6('2001:db8:b::', '2001:db8:1::9'),
            'c': _sub6('2001:db8:c::', 'europe.pool.ntp.org')}
    d = _render('templ_kea-dhcp6.cfg', _ctx6(subs))['Dhcp6']['subnet6']
    got = {s['subnet']: sorted(n for n in _opt_names(s) if 'ntp' in n) for s in d}
    assert got == {
        '2001:db8:a::/64': [],                          # IPv4 ntp cannot be carried in v6 -> dropped
        '2001:db8:b::/64': ['ntp-server-srv-addr'],     # IPv6 address -> srv-addr sub-option
        '2001:db8:c::/64': ['ntp-server-srv-fqdn'],     # host name -> srv-fqdn sub-option
    }, "the dhcp6 ntp-server (option 56) must carry an IPv6 address as srv-addr and a name as srv-fqdn."


def test_v6_defines_both_ntp_suboptions():
    """The srv-addr and srv-fqdn sub-options must be defined, or kea has no code 1/3 in the space."""
    source = open(os.path.join(TEMPLATE_DIR, 'templ_kea-dhcp6.cfg')).read()
    assert '"space": "ntp-server"' in source and '"type": "ipv6-address"' in source and '"type": "fqdn"' in source, (
        "templ_kea-dhcp6.cfg no longer defines the ntp-server srv-addr / srv-fqdn sub-options.")


# ---------------------------------------------------------------- the entry point
# Rendering an IPv6 ntp_server correctly is worth nothing while the only way an administrator
# can set one refuses it. update_network is that one way -- create and update both come through
# it, and so does a replicated request from the peer -- so the value has to survive it. Seeding
# the row directly, which is what the render tests above do, cannot see this.

@pytest.fixture
def network_db(db, seed, monkeypatch):
    """The db fixture plus the ipaddress table, with the post-validation side effects stubbed.

    A value that passes validation goes on to queue work and poke services, which builds and
    runs real commands. Stub those rather than skip the test: the accepting path IS the case.
    """
    Database().create('ipaddress', DBStructure().get_database_table_structure('ipaddress'))
    monkeypatch.setattr(Network, '_queue_network_services', lambda self: None)
    monkeypatch.setattr(Queue, 'add_task_to_queue', lambda *args, **kwargs: (1, 'stubbed'))
    monkeypatch.setattr(Queue, 'next_task_in_queue', lambda *args, **kwargs: None)
    return db


@pytest.mark.parametrize('value', ['2001:db8:1::9', '10.1.0.9', 'europe.pool.ntp.org'])
def test_every_ntp_server_kind_survives_update_network(network_db, value):
    """All three kinds this fix renders must be settable through the only path that sets them."""
    status, response = Network().update_network(
        'cluster', {'config': {'network': {'cluster': {'ntp_server': value}}}})
    assert status is True, (
        f"update_network rejected ntp_server={value!r}: {response}. The dhcp6 side is the only "
        f"family able to serve an IPv6 NTP address, and rejecting it here leaves that half of "
        f"the rendering unreachable by any administrator.")
    stored = Database().get_record(table='network', where="name='cluster'")[0]['ntp_server']
    assert stored == value, f"ntp_server stored as {stored!r}, not {value!r}"


def _isc_ntp_lines(template, subnets):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    out = env.get_template(template).render(
        CLASSES={}, SHARED={}, SUBNETS=subnets, ZONES={}, EMPTY={}, POOLS={}, LINKSEL={},
        INTERFACES={}, DOMAINNAME='c', NAMESERVERS='10.1.0.1', NAMESERVERS_IPV6='2001:db8:1::1',
        NTPSERVERS='', RESERVATIONS={k: [] for k in subnets}, OMAPIKEY=None,
        TSIGKEY=None, TSIGALGO=None)
    return [line.strip() for line in out.splitlines() if 'ntp-servers' in line]


def _isc_sub(template, ntp):
    """One ISC subnet. The v4 template nests its options inside the nextserver branch, so a
    fixture without one renders a subnet carrying no options at all and proves nothing."""
    if template == 'templ_dhcpd.cfg':
        sub = _sub4('10.9.0.0', ntp)
        sub.update({'nextserver': '10.9.0.1', 'nextport': 7050})
        return sub
    return _sub6('2001:db8:9::', ntp)


@pytest.mark.parametrize('template', ['templ_dhcpd.cfg', 'templ_dhcpd6.cfg'])
def test_isc_templates_drop_an_ipv6_ntp_server(template):
    """isc-dhcpd refuses an IPv6 address in option ntp-servers -- in a v6 config as much as a v4
    one, verified against 4.4.2b1 -- and one refused option costs the whole file. Both ISC
    templates therefore drop that value, exactly as the kea dhcp4 template does."""
    kept = _isc_ntp_lines(template, {'a': _isc_sub(template, 'europe.pool.ntp.org')})
    dropped = _isc_ntp_lines(template, {'a': _isc_sub(template, '2001:db8:1::9')})
    assert kept and 'europe.pool.ntp.org' in kept[0], (
        f"{template} stopped emitting a host-name ntp_server; that value works today and this "
        f"change must not take it away.")
    assert dropped == [], (
        f"{template} emitted an IPv6 ntp_server. dhcpd rejects the option and discards the "
        f"entire configuration file, freezing DHCP on its last-good config.")


def test_config_classifies_ntp_server_through_the_helper():
    """Pin the classification to the shipping source: it must route through the family helper."""
    source = inspect.getsource(Config.dhcp_subnet_config)
    assert "ntp_server_kind" in source and "check_if_ipv6(nwk['ntp_server'])" in source, (
        "dhcp_subnet_config no longer classifies ntp_server via Helper().check_if_ipv6; a hand-rolled "
        "family test here is exactly what breaks on host names like europe.pool.ntp.org.")
