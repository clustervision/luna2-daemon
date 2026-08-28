# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TRIX-1946: the daemon reads its own NICs in one place, and everything else matches
on top of that.

There were three walks - one for the interface name, one for the address, one for
which controller this machine is - and a fourth was about to be added for DNS. They
had drifted: the DNS zone published the controller's stored address in every zone,
which is always the cluster one, so an InfiniBand lookup answered with an ethernet
address. That is what three copies of a walk costs.

The class is closed here rather than the instance: netifaces is asserted to be
imported in exactly one module, so a fifth walk cannot be added quietly.
"""

import os
import re
import time

import pytest


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DAEMON = os.path.join(REPO, 'daemon')

# one interface carrying two networks, an InfiniBand interface beside it - the
# layout from the report
NICS = [('ipv6', 'enp2s0f0np0', 'fe80::1'),
        ('ipv4', 'enp2s0f0np0', '10.141.255.254'),
        ('ipv4', 'enp2s0f0np0', '10.131.255.254'),
        ('ipv4', 'ibp129s0', '10.139.1.102')]


@pytest.fixture
def db(tmp_path):
    """A fresh database with the networks the walk matches against."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['network', 'controller', 'ipaddress']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    for name, cidr in (('cluster', '10.141.0.0'), ('storage', '10.131.0.0'),
                       ('ib', '10.139.0.0')):
        Database().insert('network', Helper().make_rows(
            {'name': name, 'network': cidr, 'subnet': '16'}))
    Helper.address_cache.clear()
    yield Database()
    Helper.address_cache.clear()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def nics(monkeypatch):
    """Pretend NICs, installed at the one seam every caller goes through."""
    from utils.helper import Helper
    Helper.address_cache.clear()
    monkeypatch.setattr(Helper, 'local_addresses', lambda self: list(NICS))


# --- the class: there is one walk, and it cannot quietly become two -----------

def test_only_one_module_reads_the_nics():
    """
    A second import of netifaces is a second walk, and a second walk is how these
    answers drifted apart in the first place.
    """
    importers = []
    for where, dirs, files in os.walk(DAEMON):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(where, name)
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                if re.search(r'^\s*import\s+netifaces', handle.read(), re.M):
                    importers.append(os.path.relpath(path, REPO))
    assert importers == ['daemon/utils/helper.py'], (
        f'the NICs are read in more than one place: {importers}')


# --- the projections all come off that one walk ------------------------------

def test_the_interface_name_for_each_network(db, nics):
    from utils.helper import Helper

    found = Helper().get_controller_interfaces_for_networks()
    assert found['ipv4'] == {'cluster': 'enp2s0f0np0', 'storage': 'enp2s0f0np0',
                             'ib': 'ibp129s0'}


def test_the_address_for_each_network(db, nics):
    """This is the answer the InfiniBand zone was getting wrong."""
    from utils.helper import Helper

    found = Helper().get_controller_addresses_for_networks()
    assert found['ipv4'] == {'cluster': '10.141.255.254', 'storage': '10.131.255.254',
                             'ib': '10.139.1.102'}


def test_every_address_on_a_network_when_asked_for_all(db, monkeypatch):
    """
    An interface carries its own address and a floating one, and nothing local can
    tell which is which. A caller publishing them wants both; a caller that needs
    one wants the first. One method, so the two cannot drift apart.
    """
    from utils.helper import Helper

    Helper.address_cache.clear()
    monkeypatch.setattr(Helper, 'local_addresses',
                        lambda self: [('ipv4', 'ibp129s0', '10.139.1.102'),
                                      ('ipv4', 'ibp129s0', '10.139.1.199')])
    every = Helper().get_controller_addresses_for_networks(every=True)
    assert every['ipv4'] == {'ib': ['10.139.1.102', '10.139.1.199']}
    first = Helper().get_controller_addresses_for_networks()
    assert first['ipv4'] == {'ib': '10.139.1.102'}


def test_the_same_address_twice_is_reported_once(db, monkeypatch):
    from utils.helper import Helper

    Helper.address_cache.clear()
    monkeypatch.setattr(Helper, 'local_addresses',
                        lambda self: [('ipv4', 'ibp129s0', '10.139.1.102'),
                                      ('ipv4', 'ibp0', '10.139.1.102')])
    assert Helper().get_controller_addresses_for_networks(
        every=True)['ipv4'] == {'ib': ['10.139.1.102']}


def test_an_address_on_no_luna_network_is_not_reported(db, nics, monkeypatch):
    from utils.helper import Helper

    monkeypatch.setattr(Helper, 'local_addresses',
                        lambda self: [('ipv4', 'eth9', '192.0.2.7')])
    assert Helper().get_controller_addresses_for_networks()['ipv4'] == {}
    assert Helper().get_controller_interfaces_for_networks()['ipv4'] == {}


def test_find_me_matches_a_controller_row_against_the_same_walk(db, nics):
    from utils.ha import HA

    controllers = [{'hostname': 'controller2', 'ipaddress': '10.141.255.253',
                    'ipaddress_ipv6': None, 'beacon': 0},
                   {'hostname': 'controller1', 'ipaddress': '10.141.255.254',
                    'ipaddress_ipv6': None, 'beacon': 1}]
    assert HA().find_me(controllers) == ('controller1', '10.141.255.254')


def test_find_me_skips_the_beacon_when_the_address_is_shared(db, nics):
    """
    A shared address is held by whichever controller is master, so matching it
    would make both of them answer 'I am the beacon'.
    """
    from utils.ha import HA

    controllers = [{'hostname': 'beacon', 'ipaddress': '10.141.255.254',
                    'ipaddress_ipv6': None, 'beacon': 1},
                   {'hostname': 'controller1', 'ipaddress': '10.139.1.102',
                    'ipaddress_ipv6': None, 'beacon': 0}]
    assert HA().find_me(controllers, sharedip=True) == ('controller1', '10.139.1.102')


def test_find_me_says_nothing_rather_than_guessing(db, nics):
    from utils.ha import HA

    assert HA().find_me([{'hostname': 'elsewhere', 'ipaddress': '198.51.100.1',
                          'ipaddress_ipv6': None, 'beacon': 1}]) == (None, None)


# --- the cache ---------------------------------------------------------------

def test_the_walk_is_not_repeated_within_the_ttl(db, monkeypatch):
    """
    HA() reads this in its constructor and several routes build an HA() per
    request, so an unchanged set of interfaces was being enumerated once per
    request during a boot storm.
    """
    from utils.helper import Helper
    import utils.helper as helpermod

    walks = []
    monkeypatch.setattr(helpermod.ni, 'interfaces',
                        lambda: walks.append(1) or ['lo'])
    monkeypatch.setattr(helpermod.ni, 'ifaddresses', lambda interface: {})

    Helper.address_cache.clear()
    for _ in range(20):
        Helper().local_addresses()
    assert len(walks) == 1


def test_the_cache_lets_go_so_a_failover_is_noticed(db, monkeypatch):
    """
    A floating address moves on failover and find_me decides who is master from
    it, so this must not be held for the life of the process.
    """
    from utils.helper import Helper
    import utils.helper as helpermod

    walks = []
    monkeypatch.setattr(helpermod.ni, 'interfaces',
                        lambda: walks.append(1) or ['lo'])
    monkeypatch.setattr(helpermod.ni, 'ifaddresses', lambda interface: {})

    Helper.address_cache.clear()
    Helper().local_addresses()
    Helper.address_cache['local'] = (Helper.address_cache['local'][0],
                                     time.time() - Helper.address_cache_ttl - 1)
    Helper().local_addresses()
    assert len(walks) == 2
    assert Helper.address_cache_ttl <= 15, (
        'a stale answer is wrong exactly when it matters, so this stays short')
