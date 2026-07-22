#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unify redesign: the management IP moves into a switchinterface row flagged mgmt=1, and rendering
keys off that flag (bare <switch> for the mgmt interface, <switch>-<interface> for the rest, with a
first-wins safety net if several rows are accidentally mgmt=1)."""
import pytest


def _insert(table, **cols):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in cols.items()])


@pytest.fixture(autouse=True)
def _svc(constant, monkeypatch):
    constant["SERVICES"].update({"DHCP": "kea-dhcp4", "DHCP6": "kea-dhcp6", "DNS": "named"})
    monkeypatch.setattr("utils.service.Service.queue", lambda *a, **k: None)


def _seed_switch_primary():
    from utils.database import Database
    _insert("network", name="cluster", network="10.141.0.0", subnet="255.255.0.0", dhcp=1)
    netid = Database().get_record(table="network", where='name="cluster"')[0]["id"]
    _insert("switch", name="sw1", macaddress="aa:bb:cc:00:00:01")
    swid = Database().get_record(table="switch", where='name="sw1"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.5", tableref="switch", tablerefid=swid, networkid=netid)
    return {"swid": swid, "netid": netid}


@pytest.mark.regression
def test_migration_moves_primary_to_mgmt_interface(sqlite_db):
    from utils.database import Database
    from common.bootstrap import migrate_switch_interfaces
    swid = _seed_switch_primary()["swid"]
    migrate_switch_interfaces()
    ifaces = Database().get_record(table="switchinterface", where=f"switchid={swid}")
    assert len(ifaces) == 1
    assert ifaces[0]["interface"] == "eth0" and ifaces[0]["mgmt"] == 1
    assert ifaces[0]["macaddress"] == "aa:bb:cc:00:00:01"
    ip = Database().get_record(table="ipaddress",
                               where=f"tablerefid={ifaces[0]['id']} AND tableref='switchinterface'")
    assert ip and ip[0]["ipaddress"] == "10.141.0.5"
    assert not Database().get_record(table="ipaddress", where=f"tableref='switch' AND tablerefid={swid}")
    assert not Database().get_record(table="switch", where=f"id={swid}")[0]["macaddress"]


@pytest.mark.regression
def test_migration_is_idempotent(sqlite_db):
    from utils.database import Database
    from common.bootstrap import migrate_switch_interfaces
    swid = _seed_switch_primary()["swid"]
    migrate_switch_interfaces()
    migrate_switch_interfaces()
    assert len(Database().get_record(table="switchinterface", where=f"switchid={swid}")) == 1


def _seed_two_iface_switch():
    """A migrated switch: eth0 (mgmt=1) + eth1 (mgmt=0), each with a mac/ip on cluster."""
    from utils.database import Database
    _insert("network", name="cluster", network="10.141.0.0", subnet="255.255.0.0", dhcp=1)
    netid = Database().get_record(table="network", where='name="cluster"')[0]["id"]
    _insert("switch", name="sw1")
    swid = Database().get_record(table="switch", where='name="sw1"')[0]["id"]
    _insert("switchinterface", switchid=swid, interface="eth0", macaddress="aa:bb:cc:00:00:01", mgmt=1)
    m = Database().get_record(table="switchinterface", where="interface='eth0'")[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.5", tableref="switchinterface", tablerefid=m, networkid=netid)
    _insert("switchinterface", switchid=swid, interface="eth1", macaddress="aa:bb:cc:00:00:02", mgmt=0)
    e1 = Database().get_record(table="switchinterface", where="interface='eth1'")[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.6", tableref="switchinterface", tablerefid=e1, networkid=netid)
    return {"swid": swid, "netid": netid, "mgmtid": m, "eth1id": e1}


def _change(name, iface):
    from base.interface import Interface
    return Interface().change_switch_interface(name, {"config": {"switch": {name: {"interfaces": [iface]}}}})


@pytest.mark.regression
def test_rename_any_interface(sqlite_db):
    from utils.database import Database
    _seed_two_iface_switch()
    ok, msg = _change("sw1", {"interface": "eth1", "newinterfacename": "swp1"})
    assert ok is True, msg
    assert Database().get_record(table="switchinterface", where="interface='swp1'")
    assert not Database().get_record(table="switchinterface", where="interface='eth1'")


@pytest.mark.regression
def test_rename_the_mgmt_interface_keeps_it_mgmt(sqlite_db):
    from utils.database import Database
    _seed_two_iface_switch()
    ok, msg = _change("sw1", {"interface": "eth0", "newinterfacename": "ma1"})
    assert ok is True, msg
    row = Database().get_record(table="switchinterface", where="interface='ma1'")
    assert row and row[0]["mgmt"] == 1


@pytest.mark.regression
def test_rename_to_existing_name_rejected(sqlite_db):
    _seed_two_iface_switch()
    ok, msg = _change("sw1", {"interface": "eth1", "newinterfacename": "eth0"})
    assert ok is False and "already has an interface" in msg


@pytest.mark.regression
def test_setting_mgmt_moves_the_prime(sqlite_db):
    from utils.database import Database
    seeded = _seed_two_iface_switch()
    ok, msg = _change("sw1", {"interface": "eth1", "mgmt": True})
    assert ok is True, msg
    assert Database().get_record(table="switchinterface", where=f"id={seeded['eth1id']}")[0]["mgmt"] == 1
    assert Database().get_record(table="switchinterface", where=f"id={seeded['mgmtid']}")[0]["mgmt"] == 0


@pytest.mark.regression
def test_delete_sole_mgmt_is_declined(sqlite_db):
    from base.interface import Interface
    _seed_two_iface_switch()
    ok, _ = Interface().delete_switch_interface("sw1", "eth1")   # non-mgmt, allowed
    assert ok is True
    ok, msg = Interface().delete_switch_interface("sw1", "eth0") # the sole mgmt, declined
    assert ok is False and "management interface" in msg


@pytest.mark.regression
def test_switch_add_creates_mgmt_interface(sqlite_db):
    """`switch add` with -I/-N/-m creates the switch's mgmt=1 interface and routes the IP+MAC onto
    it (unify model) -- nothing lands on the switch row or tableref='switch'."""
    from utils.database import Database
    from base.switch import Switch
    _insert("network", name="cluster", network="10.141.0.0", subnet="255.255.0.0", dhcp=1)
    rd = {"config": {"switch": {"sw1": {"macaddress": "aa:bb:cc:00:00:07",
                                        "network": "cluster", "ipaddress": "10.141.0.9"}}}}
    ok, msg = Switch().update_switch("sw1", rd)
    assert ok is True, msg
    swid = Database().get_record(table="switch", where="name='sw1'")[0]["id"]
    ifaces = Database().get_record(table="switchinterface", where=f"switchid={swid} AND mgmt=1")
    assert len(ifaces) == 1 and ifaces[0]["interface"] == "eth0"
    assert ifaces[0]["macaddress"] == "aa:bb:cc:00:00:07"
    assert not Database().get_record(table="switch", where=f"id={swid}")[0]["macaddress"]
    ip = Database().get_record(table="ipaddress",
                               where=f"tablerefid={ifaces[0]['id']} AND tableref='switchinterface'")
    assert ip and ip[0]["ipaddress"] == "10.141.0.9"
    assert not Database().get_record(table="ipaddress", where=f"tableref='switch' AND tablerefid={swid}")


@pytest.mark.regression
def test_switch_interface_change_and_delete_queue_dns_reload(sqlite_db, monkeypatch):
    """A switch interface renders DNS A/PTR records (bare <switch> for mgmt, <switch>-<interface>
    otherwise), so editing one must refresh DNS, not only DHCP -- as the node/group interface path
    already does. Without the dns reload the zone keeps stale records until some other trigger."""
    calls = []
    monkeypatch.setattr("utils.service.Service.queue", lambda *a, **k: calls.append(a[1:]))
    _seed_two_iface_switch()
    ok, msg = _change("sw1", {"interface": "eth1", "newinterfacename": "swp1"})
    assert ok is True, msg
    assert ("dns", "reload") in calls, f"interface change must queue a dns reload; queued {calls}"
    calls.clear()
    from base.interface import Interface
    ok, msg = Interface().delete_switch_interface("sw1", "swp1")   # non-mgmt, allowed
    assert ok is True, msg
    assert ("dns", "reload") in calls, f"interface delete must queue a dns reload; queued {calls}"
