#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for the synthetic management interface in the switch interface listing.

A switch's management IP is stored on the switch row (ipaddress table, tableref="switch") rather
than in the switchinterface table. get_all_switch_interface presents it as a read-only interface
named Interface.MGMT_INTERFACE so `luna switch listinterface` and `luna switch show` agree, without
any storage change. These tests pin: the synthesis, its ordering, that a real row of the same name
takes over (forward-compat with a future migration), the empty case, the ip-gated rule, and the
write-guards that keep the management name single-sourced.

The render-isolation guarantee (the synthetic interface must never reach DHCP/DNS) is pinned
separately in test_switch_ztp.py, next to the render harness.
"""

import pytest


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


@pytest.fixture
def swseed(sqlite_db):
    """A network and a switch whose management IP lives on tableref="switch" (no interface rows)."""
    from utils.database import Database

    _insert("network", name="cluster", network="10.141.0.0", subnet="255.255.0.0", dhcp=1)
    netid = Database().get_record(table="network", where='name="cluster"')[0]["id"]
    _insert("switch", name="sw1", macaddress="aa:bb:cc:dd:ee:01")
    swid = Database().get_record(table="switch", where='name="sw1"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.1", tableref="switch", tablerefid=swid, networkid=netid)
    return {"swid": swid, "netid": netid, "network": "cluster"}


@pytest.mark.regression
def test_listinterface_synthesizes_mgmt_interface_from_primary(swseed):
    """A switch with only its management IP lists a single synthetic interface carrying it."""
    from base.interface import Interface

    ok, resp = Interface().get_all_switch_interface("sw1")
    assert ok is True
    ifaces = resp["config"]["switch"]["sw1"]["interfaces"]
    assert len(ifaces) == 1
    mgmt = ifaces[0]
    assert mgmt["interface"] == Interface.MGMT_INTERFACE
    assert mgmt["ipaddress"] == "10.141.0.1"
    assert mgmt["network"] == "cluster"
    assert mgmt["macaddress"] == "aa:bb:cc:dd:ee:01"


@pytest.mark.regression
def test_mgmt_interface_precedes_real_interfaces(swseed):
    """The synthetic management interface is listed first, real switchinterface rows follow."""
    from base.interface import Interface
    from utils.database import Database

    _insert("switchinterface", switchid=swseed["swid"], interface="eth1",
            macaddress="aa:bb:cc:dd:ee:02")
    eth1id = Database().get_record(table="switchinterface", where='interface="eth1"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.2", tableref="switchinterface",
            tablerefid=eth1id, networkid=swseed["netid"])

    ok, resp = Interface().get_all_switch_interface("sw1")
    ifaces = resp["config"]["switch"]["sw1"]["interfaces"]
    assert [i["interface"] for i in ifaces] == [Interface.MGMT_INTERFACE, "eth1"]


@pytest.mark.regression
def test_real_row_of_same_name_suppresses_synthetic(swseed):
    """A real switchinterface row owning the management name takes over — no duplicate, real wins.

    This is the forward-compat hinge: once a migration materialises the primary as a real row, the
    synthetic path switches itself off with no code change.
    """
    from base.interface import Interface
    from utils.database import Database

    _insert("switchinterface", switchid=swseed["swid"], interface=Interface.MGMT_INTERFACE,
            macaddress="aa:bb:cc:dd:ee:09")
    rowid = Database().get_record(
        table="switchinterface", where=f'interface="{Interface.MGMT_INTERFACE}"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.9", tableref="switchinterface",
            tablerefid=rowid, networkid=swseed["netid"])

    ok, resp = Interface().get_all_switch_interface("sw1")
    ifaces = resp["config"]["switch"]["sw1"]["interfaces"]
    assert [i["interface"] for i in ifaces] == [Interface.MGMT_INTERFACE]
    # the REAL row's address, not the synthetic primary's (10.141.0.1)
    assert ifaces[0]["ipaddress"] == "10.141.0.9"
    assert ifaces[0]["macaddress"] == "aa:bb:cc:dd:ee:09"


@pytest.mark.regression
def test_no_primary_and_no_rows_reports_not_configured(sqlite_db):
    """Nothing to present → the original 'not configured' message stands."""
    from base.interface import Interface

    _insert("switch", name="bare")
    ok, message = Interface().get_all_switch_interface("bare")
    assert ok is False
    assert "does not have any interface configured" in message


@pytest.mark.regression
def test_mac_only_primary_is_not_synthesized(sqlite_db):
    """Synthesis is ip-gated, consistent with the listing's inner join: a mac-only primary (no IP
    on a network) is not shown, exactly as a mac-only real interface is not shown."""
    from base.interface import Interface

    _insert("switch", name="macsw", macaddress="aa:bb:cc:dd:ee:aa")
    ok, message = Interface().get_all_switch_interface("macsw")
    assert ok is False
    assert "does not have any interface configured" in message


@pytest.mark.regression
def test_get_single_interface_returns_synthetic_mgmt(swseed):
    """get_switch_interface serves the synthetic management interface by name (backs showinterface)."""
    from base.interface import Interface

    ok, resp = Interface().get_switch_interface("sw1", Interface.MGMT_INTERFACE)
    assert ok is True
    ifaces = resp["config"]["switch"]["sw1"]["interfaces"]
    assert len(ifaces) == 1
    assert ifaces[0]["interface"] == Interface.MGMT_INTERFACE
    assert ifaces[0]["ipaddress"] == "10.141.0.1"


@pytest.mark.regression
def test_get_single_interface_returns_real_row(swseed):
    """get_switch_interface serves a real switchinterface row by name."""
    from base.interface import Interface
    from utils.database import Database

    _insert("switchinterface", switchid=swseed["swid"], interface="eth1",
            macaddress="aa:bb:cc:dd:ee:02")
    eth1id = Database().get_record(table="switchinterface", where='interface="eth1"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.2", tableref="switchinterface",
            tablerefid=eth1id, networkid=swseed["netid"])

    ok, resp = Interface().get_switch_interface("sw1", "eth1")
    assert ok is True
    ifaces = resp["config"]["switch"]["sw1"]["interfaces"]
    assert [i["interface"] for i in ifaces] == ["eth1"]
    assert ifaces[0]["ipaddress"] == "10.141.0.2"


@pytest.mark.regression
def test_get_single_interface_unknown_name(swseed):
    """An unknown interface name is reported, not silently empty."""
    from base.interface import Interface

    ok, message = Interface().get_switch_interface("sw1", "swp99")
    assert ok is False
    assert "not present in database" in message


@pytest.mark.regression
def test_changeinterface_mgmt_name_rejected(swseed):
    """Creating a switchinterface under the management name is refused while it is synthetic, so
    the management IP stays single-sourced on tableref="switch"."""
    from base.interface import Interface

    rd = {"config": {"switch": {"sw1": {"interfaces": [
        {"interface": Interface.MGMT_INTERFACE, "ipaddress": "10.141.0.5", "network": "cluster"}]}}}}
    ok, message = Interface().change_switch_interface("sw1", rd)
    assert ok is False
    assert "management interface" in message


@pytest.mark.regression
def test_removeinterface_mgmt_name_rejected(swseed):
    """Deleting the (synthetic) management interface is refused — there is no row, and it is
    managed via 'luna switch change' / 'luna switch remove'."""
    from base.interface import Interface

    ok, message = Interface().delete_switch_interface("sw1", Interface.MGMT_INTERFACE)
    assert ok is False
    assert "management interface" in message
