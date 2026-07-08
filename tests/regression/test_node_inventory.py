#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for node hardware inventory (TRIX-1750) against a real SQLite
database. Exercises the genuine NodeInventory base logic and data layer: the
parent rollup row, the nodeinventorydisk / nodeinventorygpu child tables, the
atomic per-source refresh, per-device querying, and the node-delete cascade.
No mocking of the data layer.
"""

import pytest


@pytest.fixture
def database(sqlite_db):
    from utils.database import Database
    return Database()


@pytest.fixture
def node(database):
    """A node row to hang inventory off; returns its id."""
    return database.insert("node", [{"column": "name", "value": "node001"}])


def _payload(disks, gpus, source="inband"):
    return {"config": {"node": {"node001": {"inventory": {
        "source": source,
        "manufacturer": "Dell",
        "product": "PowerEdge R660",
        "serial": "ABC123",
        "cpu_model": "Xeon Gold 6438Y",
        "cpu_count": 2,
        "memory_mb": 262144,
        "bios_version": "2.1.5",
        "disks": disks,
        "gpus": gpus,
    }}}}}


_DISKS = [
    {"name": "sda", "size_gb": 480, "type": "ssd", "model": "SAMSUNG MZ7", "serial": "S1"},
    {"name": "nvme0n1", "size_gb": 4000, "type": "nvme", "model": "KIOXIA", "serial": "S2"},
]
_GPUS = [
    {"busid": "0000:81:00.0", "vendor": "NVIDIA", "model": "H100", "memory_mb": 81920, "uuid": "GPU-1"},
]


@pytest.mark.regression
def test_update_inventory_creates_parent_and_children(database, node):
    from base.nodeinventory import NodeInventory

    status, _ = NodeInventory().update_inventory("node001", _payload(_DISKS, _GPUS))
    assert status is True

    parent = database.get_record(table="nodeinventory", where=f'nodeid="{node}"')
    assert len(parent) == 1
    assert parent[0]["source"] == "inband"
    assert parent[0]["disk_count"] == 2
    assert parent[0]["disk_total_gb"] == 4480    # 480 + 4000, rollup of heterogeneous disks
    assert parent[0]["gpu_count"] == 1
    assert parent[0]["hash"]

    disks = database.get_record(table="nodeinventorydisk", where=f'nodeid="{node}"')
    gpus = database.get_record(table="nodeinventorygpu", where=f'nodeid="{node}"')
    assert len(disks) == 2
    assert len(gpus) == 1


@pytest.mark.regression
def test_per_disk_query_is_plain_sql(database, node):
    """The whole point of child tables: filter on an individual disk attribute."""
    from base.nodeinventory import NodeInventory
    NodeInventory().update_inventory("node001", _payload(_DISKS, _GPUS))

    big = database.get_record(table="nodeinventorydisk", where="size_gb > 1000")
    assert len(big) == 1
    assert big[0]["name"] == "nvme0n1"


@pytest.mark.regression
def test_get_inventory_returns_devices(node):
    from base.nodeinventory import NodeInventory
    inv = NodeInventory()
    inv.update_inventory("node001", _payload(_DISKS, _GPUS))

    status, response = inv.get_inventory("node001")
    assert status is True
    snapshots = response["config"]["node"]["node001"]["inventory"]
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap["source"] == "inband"
    assert snap["disk_total_gb"] == 4480
    assert {d["name"] for d in snap["disks"]} == {"sda", "nvme0n1"}
    assert snap["gpus"][0]["model"] == "H100"


@pytest.mark.regression
def test_refresh_replaces_rows(database, node):
    """A second collection for the same source overwrites, never appends."""
    from base.nodeinventory import NodeInventory
    inv = NodeInventory()
    inv.update_inventory("node001", _payload(_DISKS, _GPUS))

    # Re-collect with a single disk and no GPUs.
    one_disk = [{"name": "sda", "size_gb": 960, "type": "ssd", "model": "INTEL", "serial": "S9"}]
    inv.update_inventory("node001", _payload(one_disk, []))

    parent = database.get_record(table="nodeinventory", where=f'nodeid="{node}"')
    assert len(parent) == 1                      # still one parent row for the source
    assert parent[0]["disk_count"] == 1
    assert parent[0]["disk_total_gb"] == 960
    assert parent[0]["gpu_count"] == 0

    disks = database.get_record(table="nodeinventorydisk", where=f'nodeid="{node}"')
    gpus = database.get_record(table="nodeinventorygpu", where=f'nodeid="{node}"')
    assert len(disks) == 1
    assert disks[0]["size_gb"] == 960
    assert not gpus


@pytest.mark.regression
def test_two_sources_coexist(database, node):
    """An inband and a redfish snapshot live side by side, keyed by source."""
    from base.nodeinventory import NodeInventory
    inv = NodeInventory()
    inv.update_inventory("node001", _payload(_DISKS, _GPUS, source="inband"))
    inv.update_inventory("node001", _payload(_DISKS[:1], [], source="redfish"))

    parent = database.get_record(table="nodeinventory", where=f'nodeid="{node}"')
    assert len(parent) == 2
    assert {p["source"] for p in parent} == {"inband", "redfish"}


@pytest.mark.regression
def test_delete_cascade_removes_all_three(database, node):
    from base.nodeinventory import NodeInventory
    inv = NodeInventory()
    inv.update_inventory("node001", _payload(_DISKS, _GPUS))

    inv.delete_inventory(node)

    for table in ["nodeinventory", "nodeinventorydisk", "nodeinventorygpu"]:
        assert not database.get_record(table=table, where=f'nodeid="{node}"')


@pytest.mark.regression
def test_node_delete_cascades_inventory(database, node):
    """Deleting the node itself must clear its inventory (base/node.py cascade)."""
    from base.nodeinventory import NodeInventory
    from base.node import Node
    NodeInventory().update_inventory("node001", _payload(_DISKS, _GPUS))

    Node().delete_node(node)

    for table in ["nodeinventory", "nodeinventorydisk", "nodeinventorygpu"]:
        assert not database.get_record(table=table, where=f'nodeid="{node}"')


@pytest.mark.regression
def test_list_inventory_summarises(node):
    from base.nodeinventory import NodeInventory
    inv = NodeInventory()
    inv.update_inventory("node001", _payload(_DISKS, _GPUS))

    status, response = inv.list_inventory()
    assert status is True
    summary = response["config"]["node"]["node001"]
    assert summary["source"] == "inband"
    assert summary["disk_count"] == 2
    assert summary["gpu_count"] == 1
    # a light summary must not carry the per-device arrays
    assert "disks" not in summary
