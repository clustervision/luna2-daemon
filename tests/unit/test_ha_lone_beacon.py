#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Which address is this machine's when the beacon is the only controller row. find_me
skips the beacon while the address is shared, because on a pair it is held by whichever
controller is master; a single controller holds no other row, so HA().get_my_ip() can
be asked to take it, and Luna's trixd addon asks. Nothing changes for a call without the
keyword, or for a pair.
"""

import pytest

# IPv6 first, as the walk in Helper returns them.
NICS = [('ipv6', 'enp2s0f0np0', 'fd00:141::254'),
        ('ipv4', 'enp2s0f0np0', '10.141.255.254')]


@pytest.fixture
def cluster(tmp_path, monkeypatch):
    """The controller rows this machine's pretend NICs are matched against."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['network', 'controller', 'ipaddress', 'ha']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    networkid = Database().insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Helper.address_cache.clear()
    monkeypatch.setattr(Helper, 'local_addresses', lambda self: list(NICS))

    def rows(*controllers, sharedip=1):
        Database().insert('ha', Helper().make_rows({'sharedip': sharedip}))
        for hostname, address, beacon in controllers:
            controller_id = Database().insert('controller', Helper().make_rows(
                {'hostname': hostname, 'beacon': beacon}))
            column = 'ipaddress_ipv6' if ':' in address else 'ipaddress'
            Database().insert('ipaddress', Helper().make_rows(
                {'tableref': 'controller', 'tablerefid': controller_id,
                 column: address, 'networkid': networkid}))

    yield rows
    Helper.address_cache.clear()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def my_ip(**asked):
    """A get_my_ip that also answers without the keyword, so a missing one fails the assertion."""
    from utils.ha import HA
    ha = HA()
    try:
        return ha.get_my_ip(**asked)
    except TypeError:
        return ha.get_my_ip()


# --- HA: the lone beacon ---------------------------------------------------------

def test_a_lone_beacon_is_this_machine_when_asked(cluster):
    cluster(('controller', '10.141.255.254', 1))
    assert my_ip(lone_beacon=True) == '10.141.255.254'


def test_without_the_keyword_a_lone_beacon_still_names_nobody(cluster):
    """Every caller that does not ask gets the answer it always got."""
    cluster(('controller', '10.141.255.254', 1))
    assert my_ip() is None


def test_a_pair_never_takes_the_shared_address(cluster):
    cluster(('controller', '10.141.255.254', 1), ('controller1', '10.141.255.253', 0))
    assert my_ip(lone_beacon=True) is None


def test_a_pair_names_its_own_row_with_or_without_the_keyword(cluster):
    cluster(('controller', '10.141.255.1', 1), ('controller1', '10.141.255.254', 0))
    assert my_ip() == '10.141.255.254'
    assert my_ip(lone_beacon=True) == '10.141.255.254'


def test_a_machine_that_is_no_controller_row_stays_nobody(cluster):
    cluster(('elsewhere', '198.51.100.1', 1))
    assert my_ip(lone_beacon=True) is None


def test_an_unshared_beacon_already_answered_and_still_does(cluster):
    cluster(('controller', '10.141.255.254', 1), sharedip=0)
    assert my_ip() == '10.141.255.254'
    assert my_ip(lone_beacon=True) == '10.141.255.254'


# --- the trixd addon: asks, brackets, falls back ---------------------------------

@pytest.fixture
def me(cluster):
    import plugins.addons.trixd as addon

    def rows(*controllers):
        cluster(*controllers)
        return addon._me()

    return rows


def test_the_addon_reaches_a_single_controller_by_its_own_address(me):
    assert me(('controller', '10.141.255.254', 1)) == '10.141.255.254'


def test_the_addon_brackets_an_ipv6_address(me):
    assert me(('controller', 'fd00:141::254', 1)) == '[fd00:141::254]'


def test_the_addon_keeps_the_loopback_where_no_row_is_this_machine(me):
    assert me(('elsewhere', '198.51.100.1', 1)) == '127.0.0.1'
