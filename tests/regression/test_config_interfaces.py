#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for the Config interface-management methods.

Exercise node/group interface create, update, rename and the dhcp-range
recalculation against a temp SQLite database. These methods return
(ok, message) tuples and mutate the nodeinterface / groupinterface / network
tables; we assert on both the return value and the stored rows.

The queue-driven propagation methods (update_interface_on_group_nodes,
update_interface_ipaddress_on_network_change) are intentionally not covered
here: they loop on the task queue and sleep(10) between rounds, so they need a
queue/service harness rather than a focused regression test.
"""

import pytest


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


@pytest.fixture
def seed(sqlite_db):
    """Seed a group, a node and a network; return their ids/names."""
    from utils.database import Database

    _insert("group", name="compute")
    groupid = Database().get_record(table="group", where='name="compute"')[0]["id"]
    _insert("node", name="node001", groupid=groupid)
    nodeid = Database().get_record(table="node", where='name="node001"')[0]["id"]
    _insert("network", name="cluster", network="10.141.0.0", subnet="255.255.0.0",
            dhcp=1, dhcp_range_begin="10.141.10.1", dhcp_range_end="10.141.10.254")
    return {"groupid": groupid, "nodeid": nodeid, "network": "cluster"}


# --- node_interface_config: validation ----------------------------------------

INVALID_NODE_IF = [
    ({"mtu": "99999"}, "mtu size out of range"),
    ({"bond_mode": "nonsense"}, "not supported"),
    ({"vlanid": "99999"}, "vlanid has to be a value between 0 and 4096"),
    ({"bond_mode": "802.3ad", "bond_slaves": "eth1,eth2", "vlan_parent": "eth0"},
     "bonded interface can not have a vlan_parent"),
    ({"bond_mode": "802.3ad", "bond_slaves": "eth1"},
     "bond_slaves should contain at least two interfaces"),
]


@pytest.mark.regression
@pytest.mark.parametrize("kwargs,expected", INVALID_NODE_IF,
                         ids=["mtu", "bond_mode", "vlanid", "bond+vlan_parent", "bond_slaves<2"])
def test_node_interface_config_validation(seed, kwargs, expected):
    from utils.config import Config
    ok, message = Config().node_interface_config(seed["nodeid"], "eth0", **kwargs)
    assert ok is False
    assert expected in message


# --- node_interface_config: create / update -----------------------------------

@pytest.mark.regression
def test_node_interface_config_creates_and_lowercases_mac(seed):
    from utils.config import Config
    from utils.database import Database

    ok, _ = Config().node_interface_config(seed["nodeid"], "BOOTIF",
                                           macaddress="AA:BB:CC:DD:EE:FF")
    assert ok is True
    row = Database().get_record(table="nodeinterface",
                                where=f'nodeid={seed["nodeid"]} AND interface="BOOTIF"')
    assert len(row) == 1
    assert row[0]["macaddress"] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.regression
def test_node_interface_config_updates_existing(seed):
    from utils.config import Config
    from utils.database import Database

    Config().node_interface_config(seed["nodeid"], "BOOTIF", macaddress="aa:bb:cc:dd:ee:ff")
    ok, _ = Config().node_interface_config(seed["nodeid"], "BOOTIF", mtu="9000")
    assert ok is True
    row = Database().get_record(table="nodeinterface",
                                where=f'nodeid={seed["nodeid"]} AND interface="BOOTIF"')
    assert row[0]["mtu"] == "9000"


# --- node_interface_rename ----------------------------------------------------

@pytest.mark.regression
def test_node_interface_rename_success(seed):
    from utils.config import Config
    from utils.database import Database

    Config().node_interface_config(seed["nodeid"], "BOOTIF", macaddress="aa:bb:cc:dd:ee:ff")
    ok, message = Config().node_interface_rename(seed["nodeid"], "BOOTIF", "eth0")
    assert ok is True
    assert "renamed to eth0" in message
    assert Database().get_record(table="nodeinterface",
                                 where=f'nodeid={seed["nodeid"]} AND interface="eth0"')


@pytest.mark.regression
def test_node_interface_rename_no_interfaces(seed):
    from utils.config import Config
    ok, message = Config().node_interface_rename(seed["nodeid"], "BOOTIF", "eth0")
    assert ok is False
    assert "no interfaces defined" in message


@pytest.mark.regression
def test_node_interface_rename_nonexistent(seed):
    from utils.config import Config
    Config().node_interface_config(seed["nodeid"], "BOOTIF", macaddress="aa:bb:cc:dd:ee:ff")
    ok, message = Config().node_interface_rename(seed["nodeid"], "absent", "eth0")
    assert ok is False
    assert "does not exist" in message


# --- group_interface_config ---------------------------------------------------

@pytest.mark.regression
def test_group_interface_config_requires_network(seed):
    from utils.config import Config
    ok, message = Config().group_interface_config(seed["groupid"], "eth0")
    assert ok is False
    assert "Network not provided or does not exist" in message


@pytest.mark.regression
def test_group_interface_config_creates_with_network(seed):
    from utils.config import Config
    from utils.database import Database

    ok, _ = Config().group_interface_config(seed["groupid"], "eth0", network=seed["network"])
    assert ok is True
    row = Database().get_record(table="groupinterface",
                                where=f'groupid={seed["groupid"]} AND interface="eth0"')
    assert len(row) == 1


@pytest.mark.regression
def test_group_interface_rename_success(seed):
    from utils.config import Config
    Config().group_interface_config(seed["groupid"], "eth0", network=seed["network"])
    ok, message = Config().group_interface_rename(seed["groupid"], "eth0", "bmc")
    assert ok is True
    assert "renamed to bmc" in message


# --- update_dhcp_range_on_network_change --------------------------------------

@pytest.mark.regression
def test_update_dhcp_range_within_network_no_change(seed):
    """Range already inside the /16 network -> reported as fitting, no change."""
    from utils.config import Config
    from utils.database import Database

    assert Config().update_dhcp_range_on_network_change(seed["network"]) is True
    net = Database().get_record(table="network", where=f'name="{seed["network"]}"')[0]
    assert net["dhcp_range_begin"] == "10.141.10.1"
    assert net["dhcp_range_end"] == "10.141.10.254"


@pytest.mark.regression
def test_update_dhcp_range_outside_network_recalculates(sqlite_db):
    """Range outside the /24 network -> recomputed inside it and persisted."""
    from utils.config import Config
    from utils.database import Database
    from utils.helper import Helper

    # range 10.141.10.x does not fit a /24 rooted at 10.141.0.0
    _insert("network", name="small", network="10.141.0.0", subnet="255.255.255.0",
            dhcp=1, dhcp_range_begin="10.141.10.1", dhcp_range_end="10.141.10.254")

    Config().update_dhcp_range_on_network_change("small")

    net = Database().get_record(table="network", where='name="small"')[0]
    assert (net["dhcp_range_begin"], net["dhcp_range_end"]) != ("10.141.10.1", "10.141.10.254")
    # the recomputed range now fits inside 10.141.0.0/24
    assert Helper().check_ip_range(net["dhcp_range_begin"], "10.141.0.0/24")
    assert Helper().check_ip_range(net["dhcp_range_end"], "10.141.0.0/24")
