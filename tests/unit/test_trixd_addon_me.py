#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Where Luna's trixd addon reaches trixd. A single controller holds its only row as the
beacon, which the walk that names this machine skips, so the addon has to find its own
address from that row instead of falling back to the loopback no certificate names.
"""

import sys
import types

import pytest

NICS = ['10.141.255.254']


class FakeHA:
    """HA() as find_me answers it: a beacon row is skipped when the address is shared."""

    controllers: list = []
    sharedip = True

    def __init__(self):
        self.all_controllers = self.controllers

    def get_my_ip(self):
        return self.find_me(self.all_controllers, self.sharedip)[1]

    def find_me(self, controllers=(), sharedip=None):
        for controller in controllers:
            if sharedip and controller['beacon']:
                continue
            if controller['ipaddress'] in NICS:
                return controller['hostname'], controller['ipaddress']
        return None, None


class FakeHelper:
    def check_if_ipv6(self, address):
        return ':' in address


@pytest.fixture
def me(monkeypatch):
    import plugins.addons.trixd as addon

    monkeypatch.setitem(sys.modules, 'utils.ha', types.SimpleNamespace(HA=FakeHA))
    monkeypatch.setitem(sys.modules, 'utils.helper', types.SimpleNamespace(Helper=FakeHelper))

    def rows(*controllers, sharedip=True):
        monkeypatch.setattr(FakeHA, 'controllers', list(controllers))
        monkeypatch.setattr(FakeHA, 'sharedip', sharedip)
        return addon._me()

    return rows


def row(hostname, ipaddress, beacon):
    return {'hostname': hostname, 'ipaddress': ipaddress, 'ipaddress_ipv6': None, 'beacon': beacon}


def test_a_single_controller_reaches_trixd_by_its_own_address(me):
    assert me(row('trx16', '10.141.255.254', 1)) == '10.141.255.254'


def test_a_pair_still_names_the_controller_not_the_shared_address(me):
    assert me(row('beacon', '10.141.255.254', 1), row('controller1', '10.141.255.253', 0)) == '127.0.0.1'


def test_a_pair_names_its_own_row(me):
    assert me(row('beacon', '10.141.255.1', 1), row('controller1', '10.141.255.254', 0)) == '10.141.255.254'


def test_a_machine_that_is_no_controller_row_keeps_the_loopback(me):
    assert me(row('elsewhere', '198.51.100.1', 1)) == '127.0.0.1'
