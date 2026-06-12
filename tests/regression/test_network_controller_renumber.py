#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for controller-hostname renumbering in Network.update_network.

When a network address/family changes, update_network re-homes the controllers
living on that network. The request keys carrying the new controller IPs arrive
from the API's arg-parser, which rewrites '-' to '_', so a controller named
'controller-1' is addressed in the request as 'controller_1'. The method
normalises both the beacon's generic 'controller' key and each controller's
hostname with .replace('-','_') before matching (TRIX-1882).

These run the real update_network against a temp SQLite database. The method's
asynchronous tail (background ip-redistribution worker with sleep loops, the
task queue, and service reloads) is neutralised by the `network_harness`
fixture using monkeypatch only -- no daemon code is modified, and the patches
revert after each test so the suite stays independent.
"""

import pytest


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


def _record(table, where):
    from utils.database import Database
    return Database().get_record(table=table, where=where)


@pytest.fixture
def network_harness(monkeypatch, sqlite_db):
    """
    Make Network.update_network synchronously testable.

    Neutralises only the work that happens *after* the controller renumbering is
    written to the database:
      - the background ip-redistribution worker (the sleep(10) loops),
      - the dhcp-range recalculation,
      - the task queue (short-circuited so no ThreadPoolExecutor is spawned),
      - service reloads (recorded instead of executed).

    Returns a dict whose 'services' list captures the (name, action) reloads the
    method requested, so tests can assert the post-change refresh was triggered.
    """
    import time
    from utils.config import Config
    from utils.service import Service
    from utils.queue import Queue

    recorded = {"services": []}

    monkeypatch.setattr(Config, "update_dhcp_range_on_network_change",
                        lambda self, name: None)
    monkeypatch.setattr(Config, "update_interface_ipaddress_on_network_change",
                        lambda self, name: None)
    # queue_id != next_id -> the executor branch that runs the background worker
    # is skipped entirely, so no thread is ever spawned.
    monkeypatch.setattr(Queue, "add_task_to_queue",
                        lambda self, task=None, param=None, subsystem=None, **k: (1, None))
    monkeypatch.setattr(Queue, "next_task_in_queue",
                        lambda self, subsystem=None, **k: 0)
    # Service() reads service names from CONSTANT['SERVICES'] at construction,
    # which the test stub does not populate; neutralise construction so the queue
    # recorder below is all that runs.
    monkeypatch.setattr(Service, "__init__", lambda self: None)
    monkeypatch.setattr(Service, "queue",
                        lambda self, name, action: recorded["services"].append((name, action)))
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    return recorded


def _seed(hostname, controller_ip, beacon=1):
    """Seed network 'cluster' (10.141.0.0/16) with one controller on it."""
    _insert("network", name="cluster", network="10.141.0.0", subnet="16",
            network_ipv6="", subnet_ipv6="")
    networkid = _record("network", 'name="cluster"')[0]["id"]
    _insert("controller", hostname=hostname, beacon=beacon)
    controllerid = _record("controller", f'hostname="{hostname}"')[0]["id"]
    _insert("ipaddress", ipaddress=controller_ip, tableref="controller",
            tablerefid=controllerid, networkid=networkid)
    return networkid, controllerid


def _request(**network_fields):
    return {"config": {"network": {"cluster": dict(network_fields)}}}


# --- the new IP is rejected only if the dashed hostname was matched ------------

@pytest.mark.regression
def test_dashed_controller_matched_via_underscore_key(network_harness):
    """
    'controller-1' is addressed as 'controller_1' in the request. The normalised
    match routes the supplied (out-of-range) IP through controller validation,
    yielding the 'address mismatch' error. Without the .replace('-','_') the key
    would not match and the method would instead complain that the existing
    controller sits outside the new network -- a different message.
    """
    from base.network import Network
    _seed("controller-1", "10.141.0.10")
    req = _request(network="10.142.0.0/16", controller_1="10.99.0.5")

    ok, msg = Network().update_network("cluster", req)
    assert ok is False
    assert "Controller address mismatch" in msg


@pytest.mark.regression
def test_generic_controller_key_remapped_to_dashed_beacon(network_harness):
    """
    The generic 'controller' key is remapped onto the beacon's normalised
    hostname ('controller_1'), so it too reaches controller validation.
    """
    from base.network import Network
    _seed("controller-1", "10.141.0.10", beacon=1)
    req = _request(network="10.142.0.0/16", controller="10.99.0.5")

    ok, msg = Network().update_network("cluster", req)
    assert ok is False
    assert "Controller address mismatch" in msg


@pytest.mark.regression
def test_plain_controller_hostname_still_matched(network_harness):
    """A non-dashed hostname is unaffected by normalisation and still matches."""
    from base.network import Network
    _seed("controller", "10.141.0.10", beacon=1)
    req = _request(network="10.142.0.0/16", controller="10.99.0.5")

    ok, msg = Network().update_network("cluster", req)
    assert ok is False
    assert "Controller address mismatch" in msg


@pytest.mark.regression
def test_controller_outside_new_range_without_new_ip_rejected(network_harness):
    """
    With no new IP supplied for a controller whose existing address falls outside
    the new network, the method reports the controller no longer fits.
    """
    from base.network import Network
    _seed("controller-1", "10.141.0.10")
    req = _request(network="10.142.0.0/16")

    ok, msg = Network().update_network("cluster", req)
    assert ok is False
    assert "doesn't match address/subnet" in msg


# --- happy path: renumber is persisted, async tail runs through the harness ----

@pytest.mark.regression
def test_dashed_controller_renumber_persists_new_ip(network_harness):
    """
    A valid new IP for the dashed controller (via the underscore key) is written
    to the ipaddress table, the network row takes the new address, and the
    post-change service refresh is queued -- exercising the full method through
    the queue/service harness.
    """
    from base.network import Network
    networkid, controllerid = _seed("controller-1", "10.141.0.10")
    req = _request(network="10.142.0.0/16", controller_1="10.142.0.10")

    ok, msg = Network().update_network("cluster", req)
    assert ok is True
    assert "updated successfully" in msg

    ip_row = _record("ipaddress", f"tablerefid={controllerid} AND tableref='controller'")
    assert ip_row[0]["ipaddress"] == "10.142.0.10"

    net_row = _record("network", 'name="cluster"')[0]
    assert net_row["network"] == "10.142.0.0"
    assert net_row["subnet"] == "16"

    assert ("dns", "reload") in network_harness["services"]
