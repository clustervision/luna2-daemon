#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression for the two family-handling shapes on the network fields:

 * nameserver_ip (TWINNED columns) -- one flag carries a mixed v4/v6 CSV and the daemon segregates
   by family into nameserver_ip and nameserver_ip_ipv6 at write. Closes the gap where the v6 twin
   was renderable but had no CLI/API writer.
 * dhcp_link_subnet (TWINLESS, like dhcp_relay) -- the mixed CSV is stored verbatim in one column
   and filtered per family at render; there is no dhcp_link_subnet_ipv6 column.
"""

import pytest


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


def _update(name, **fields):
    from base.network import Network
    return Network().update_network(name, {"config": {"network": {name: dict(fields)}}})


def _row(name):
    from utils.database import Database
    return Database().get_record(table="network", where=f'name="{name}"')[0]


@pytest.fixture(autouse=True)
def _services(constant, monkeypatch):
    constant["SERVICES"].update({"DHCP": "kea-dhcp4", "DHCP6": "kea-dhcp6", "DNS": "named"})
    monkeypatch.setattr("utils.service.Service.queue", lambda *a, **k: None)


def test_nameserver_ip_segregates_by_family(sqlite_db):
    _insert("network", name="dns", network="10.150.0.0", subnet="255.255.0.0",
            network_ipv6="2001:db8:150::", subnet_ipv6="64")

    ok, msg = _update("dns", nameserver_ip="10.150.0.1,2001:db8:150::1,10.150.0.2")
    assert ok is True, msg
    row = _row("dns")
    assert row["nameserver_ip"] == "10.150.0.1,10.150.0.2"
    assert row["nameserver_ip_ipv6"] == "2001:db8:150::1"

    # the single field is the complete set: a v4-only input clears the v6 twin
    ok, msg = _update("dns", nameserver_ip="10.150.0.9")
    assert ok is True, msg
    row = _row("dns")
    assert row["nameserver_ip"] == "10.150.0.9"
    assert not row["nameserver_ip_ipv6"]


def test_dhcp_link_subnet_stores_mixed_families_twinless(sqlite_db):
    _insert("network", name="base", network="10.150.0.0", subnet="255.255.0.0")
    _insert("network", name="prov", network="10.151.0.0", subnet="255.255.0.0",
            shared="base", dhcp_relay="10.152.0.1,2001:db8:152::1")

    # one twinless field, like dhcp_relay: the mixed CSV is stored verbatim and the render filters
    # it per family. There is no dhcp_link_subnet_ipv6 column to segregate into.
    ok, msg = _update("prov", dhcp_link_subnet="192.0.2.0/24,2001:db8:35::/64")
    assert ok is True, msg
    row = _row("prov")
    assert row["dhcp_link_subnet"] == "192.0.2.0/24,2001:db8:35::/64"
    assert "dhcp_link_subnet_ipv6" not in row


def test_dhcp_link_subnet_requires_relay(sqlite_db):
    _insert("network", name="base2", network="10.150.0.0", subnet="255.255.0.0")
    _insert("network", name="norelay", network="10.153.0.0", subnet="255.255.0.0", shared="base2")

    ok, msg = _update("norelay", dhcp_link_subnet="192.0.2.0/24")
    assert ok is False
    assert "requires dhcp_relay" in msg
