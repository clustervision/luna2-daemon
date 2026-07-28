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

from utils.config import Config

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


def test_config_classifies_ntp_server_through_the_helper():
    """Pin the classification to the shipping source: it must route through the family helper."""
    source = inspect.getsource(Config.dhcp_subnet_config)
    assert "ntp_server_kind" in source and "check_if_ipv6(nwk['ntp_server'])" in source, (
        "dhcp_subnet_config no longer classifies ntp_server via Helper().check_if_ipv6; a hand-rolled "
        "family test here is exactly what breaks on host names like europe.pool.ntp.org.")
