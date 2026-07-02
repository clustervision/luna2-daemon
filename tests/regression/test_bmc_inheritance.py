#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for unmanaged_bmc_users inheritance and bmcsetup name resolution.

The detailed group/node views resolve unmanaged_bmc_users through a precedence
chain and tag each resolved value with a '_<key>_source' marker:

  group view : group override  -> bmcsetup
  node view  : node override   -> group -> bmcsetup -> default

They also surface '!!Invalid!!' as the bmcsetup name when a record points at a
bmcsetupid that no longer exists. These run against a temp SQLite database built
from the daemon's own schema (see the sqlite_db fixture); the real data layer is
exercised, not a mock.
"""

import pytest


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


def _id(table, name):
    from utils.database import Database
    return Database().get_record(table=table, where=f'name="{name}"')[0]["id"]


@pytest.fixture
def base(sqlite_db):
    """
    The detailed group view dereferences cluster[0] unconditionally, so a cluster
    row must exist for any get_group call to succeed.
    """
    _insert("cluster", name="cluster")
    return sqlite_db


# --- group view: unmanaged_bmc_users inheritance ------------------------------

@pytest.mark.regression
def test_group_inherits_unmanaged_from_bmcsetup(base):
    """Empty group value falls back to the linked bmcsetup's value."""
    from base.group import Group
    _insert("bmcsetup", name="bmc1", unmanaged_bmc_users="root,admin")
    _insert("group", name="compute", bmcsetupid=_id("bmcsetup", "bmc1"))

    ok, response = Group().get_group("compute")
    assert ok is True
    group = response["config"]["group"]["compute"]
    assert group["unmanaged_bmc_users"] == "root,admin"
    assert group["_unmanaged_bmc_users_source"] == "bmcsetup"


@pytest.mark.regression
def test_group_override_wins_over_bmcsetup(base):
    """A group's own value takes precedence over the bmcsetup value."""
    from base.group import Group
    _insert("bmcsetup", name="bmc1", unmanaged_bmc_users="root,admin")
    _insert("group", name="compute", bmcsetupid=_id("bmcsetup", "bmc1"),
            unmanaged_bmc_users="operator")

    ok, response = Group().get_group("compute")
    group = response["config"]["group"]["compute"]
    assert group["unmanaged_bmc_users"] == "operator"
    assert group["_unmanaged_bmc_users_source"] == "group"


@pytest.mark.regression
def test_group_no_bmcsetup_no_value_defaults(base):
    """With neither a group value nor a bmcsetup, the source is 'default'."""
    from base.group import Group
    _insert("group", name="compute")

    ok, response = Group().get_group("compute")
    group = response["config"]["group"]["compute"]
    assert group["_unmanaged_bmc_users_source"] == "default"


@pytest.mark.regression
def test_group_dangling_bmcsetupid_is_invalid(base):
    """A bmcsetupid pointing at a missing record yields '!!Invalid!!'."""
    from base.group import Group
    _insert("group", name="compute", bmcsetupid=999)

    ok, response = Group().get_group("compute")
    group = response["config"]["group"]["compute"]
    assert group["bmcsetupname"] == "!!Invalid!!"


@pytest.mark.regression
def test_get_all_group_inherits_unmanaged_from_bmcsetup(base):
    """get_all_group applies the same group-override-then-bmcsetup fallback."""
    from base.group import Group
    _insert("bmcsetup", name="bmc1", unmanaged_bmc_users="root,admin")
    _insert("group", name="inherits", bmcsetupid=_id("bmcsetup", "bmc1"))
    _insert("group", name="overrides", bmcsetupid=_id("bmcsetup", "bmc1"),
            unmanaged_bmc_users="operator")

    ok, response = Group().get_all_group()
    groups = response["config"]["group"]
    assert groups["inherits"]["unmanaged_bmc_users"] == "root,admin"
    assert groups["overrides"]["unmanaged_bmc_users"] == "operator"


# --- node view: unmanaged_bmc_users inheritance -------------------------------

def _seed_node(group_kwargs=None, node_kwargs=None):
    """Create a group and a node in it; return the node name."""
    _insert("group", name="compute", **(group_kwargs or {}))
    _insert("node", name="node001", groupid=_id("group", "compute"),
            **(node_kwargs or {}))
    return "node001"


@pytest.mark.regression
def test_node_own_value_overrides(base):
    """A node's own value wins and flags the node as an override."""
    from base.node import Node
    name = _seed_node(node_kwargs={"unmanaged_bmc_users": "nodeuser"})

    ok, response = Node().get_node(name)
    node = response["config"]["node"][name]
    assert node["unmanaged_bmc_users"] == "nodeuser"
    assert node["_unmanaged_bmc_users_source"] == "node"
    assert node["_override"] is True


@pytest.mark.regression
def test_node_inherits_from_group(base):
    """Empty node value falls back to the group's value."""
    from base.node import Node
    name = _seed_node(group_kwargs={"unmanaged_bmc_users": "groupuser"})

    ok, response = Node().get_node(name)
    node = response["config"]["node"][name]
    assert node["unmanaged_bmc_users"] == "groupuser"
    assert node["_unmanaged_bmc_users_source"] == "group"


@pytest.mark.regression
def test_node_inherits_from_bmcsetup_via_group(base):
    """With node and group empty, the group's bmcsetup value is inherited."""
    from base.node import Node
    _insert("bmcsetup", name="bmc1", unmanaged_bmc_users="bmcuser")
    name = _seed_node(group_kwargs={"bmcsetupid": _id("bmcsetup", "bmc1")})

    ok, response = Node().get_node(name)
    node = response["config"]["node"][name]
    assert node["unmanaged_bmc_users"] == "bmcuser"
    assert node["_unmanaged_bmc_users_source"] == "bmcsetup"


@pytest.mark.regression
def test_node_no_value_defaults(base):
    """Nothing set anywhere: value is None and source is 'default'."""
    from base.node import Node
    name = _seed_node()

    ok, response = Node().get_node(name)
    node = response["config"]["node"][name]
    assert node["unmanaged_bmc_users"] is None
    assert node["_unmanaged_bmc_users_source"] == "default"


@pytest.mark.regression
def test_node_dangling_bmcsetupid_is_invalid(base):
    """A node bmcsetupid pointing at a missing record yields '!!Invalid!!'."""
    from base.node import Node
    name = _seed_node(node_kwargs={"bmcsetupid": 999})

    ok, response = Node().get_node(name)
    node = response["config"]["node"][name]
    assert node["bmcsetup"] == "!!Invalid!!"
