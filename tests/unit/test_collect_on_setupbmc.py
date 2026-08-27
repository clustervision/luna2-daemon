#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2028: collect out of band when a node says its BMC is configured.

The trigger has to be the event and not a sweep for it. install.setupbmc lasts
about as long as it takes ipmitool to write a few LAN settings, so anything
sampling node state on a timer would catch it on a handful of nodes and miss it
on the rest - which is worse than missing it everywhere, because it looks like it
works.

Nothing new was invented for either half. Monitor.update_nodestatus already turns
a reported state into an event, and the Redfish worker already has a loop. What is
added is a queue entry between them, so the node's status update never waits on
its BMC and the collection never waits on a BIOS push.
"""

import pytest

from base.monitor import Monitor
from utils.bios_push import BiosPush
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue


@pytest.fixture(name='node')
def node_fixture(sqlite_db):
    Database().insert('group', [{"column": "name", "value": 'compute'},
                                {"column": "id", "value": 1}])
    Database().insert('node', [{"column": "name", "value": 'node001'},
                               {"column": "id", "value": 1},
                               {"column": "groupid", "value": 1}])
    Database().insert('redfishsetup', [{"column": "name", "value": 'dc'},
                                       {"column": "id", "value": 1},
                                       {"column": "scheme", "value": 'https'}])
    Database().insert('redfishaccount', [{"column": "id", "value": 1},
                                         {"column": "redfishsetupid", "value": 1},
                                         {"column": "name", "value": 'ro'},
                                         {"column": "username", "value": 'ro'},
                                         {"column": "password", "value": 'pw'},
                                         {"column": "role", "value": 'ReadOnly'}])
    Database().update('node', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "id", "value": 1}])
    return 'node001'


def queued():
    return [row for row in Database().get_record(table='queue') or []
            if row['task'] == 'collect_redfish_inventory']


# --- the event --------------------------------------------------------------

def test_reporting_the_stage_queues_a_collection(node):
    assert Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc')
    assert [row['param'] for row in queued()] == ['node001']


@pytest.mark.parametrize('state', [
    'install.download', 'install.unpack', 'install.success', 'install.booted', '',
])
def test_no_other_stage_queues_anything(node, state):
    """
    A node reports a dozen stages during one install. Only one of them means the
    BMC has just become reachable.
    """
    assert Monitor().redfish_on_setupbmc(nodename=node, state=state) is False
    assert not queued()


def test_a_node_without_a_redfishsetup_queues_nothing(node):
    """
    Every collection for it would be refused by the gate, so queueing four
    thousand of them is work and log noise for a foregone answer. The skip is
    logged with its reason - an unlogged skip is indistinguishable from a bug.
    """
    Database().update('node', Helper().make_rows({'redfishsetupid': ''}),
                      [{"column": "id", "value": 1}])
    assert Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc') is False
    assert not queued()


def test_reporting_it_twice_collects_once(node):
    """
    utils/queue.py collapses an identical subsystem+task+param inside fifteen
    minutes, so a node that reports the stage again does not queue a second sweep.
    """
    for _ in range(3):
        Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc')
    assert len(queued()) == 1


# --- the drain --------------------------------------------------------------

def test_the_worker_drains_them_in_one_batch(node, monkeypatch):
    """
    One call with every node, not one call per node. bulk_collect_redfish bounds
    its own concurrency; handing it the set once is what a boot storm needs, and
    handing it one node at a time would start a thread apiece.
    """
    for name in ('node002', 'node003'):
        Queue().add_task_to_queue(task='collect_redfish_inventory', param=name,
                                  subsystem='redfish')
    Queue().add_task_to_queue(task='collect_redfish_inventory', param='node001',
                              subsystem='redfish')
    calls = []
    monkeypatch.setattr('base.nodeinventory.NodeInventory.bulk_collect_redfish',
                        lambda self, request_data=None: calls.append(request_data) or (True, 'ok'))
    assert BiosPush().collect_queued_inventory() is True
    assert len(calls) == 1, 'one sweep, not one per node'
    hosts = calls[0]['config']['node']['hostlist'].split(',')
    assert sorted(hosts) == ['node001', 'node002', 'node003']
    assert not queued(), 'the queue is emptied by draining it'


def test_an_empty_queue_is_not_a_sweep(node, monkeypatch):
    calls = []
    monkeypatch.setattr('base.nodeinventory.NodeInventory.bulk_collect_redfish',
                        lambda self, request_data=None: calls.append(1) or (True, 'ok'))
    assert BiosPush().collect_queued_inventory() is False
    assert not calls


def test_the_drain_runs_before_a_push_can_hold_the_loop():
    """
    A staged BIOS push holds through reboots for up to fifteen minutes a stage. If
    the collections were drained after it, a node that just installed would wait
    that long for its inventory, for no reason at all.
    """
    import ast
    import inspect

    source = inspect.getsource(BiosPush.push_mother)
    tree = ast.parse(source.lstrip())
    order = [node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr in ('collect_queued_inventory', 'run_task')]
    assert order and order[0] == 'collect_queued_inventory'


def test_the_drain_does_not_block_the_worker(node, monkeypatch):
    """
    The one property this must have. bulk_collect_redfish schedules its sweep and
    returns, so a rack of dark BMCs times out on its own threads. A blocking call
    here would stall every BIOS push on the cluster with nothing saying why - so
    it is asserted rather than assumed.
    """
    Queue().add_task_to_queue(task='collect_redfish_inventory', param='node001',
                              subsystem='redfish')

    def slow(self, request_data=None):
        raise AssertionError('the worker waited on the sweep')

    # a sweep that never returns would hang the loop; the drain must hand off, so
    # what it calls has to be the scheduling call and not the collecting one
    source = __import__('inspect').getsource(BiosPush.collect_queued_inventory)
    assert 'bulk_collect_redfish' in source
    assert 'collect_child' not in source, (
        'collecting inline would block this loop for as long as the BMCs take'
    )


# --- deferred rather than retried -------------------------------------------

def test_the_collection_is_scheduled_into_the_future(node):
    """
    Luna has just given the BMC its address with ipmitool and the node is still
    installing, so the BMC is not necessarily answering Redfish yet. A collection
    fired at that moment would mostly fail.

    The queue already solves this: next_task_in_queue selects on created <= now,
    so a task created in the future is invisible until then. That is a delay
    instead of a retry loop, a backoff and a give-up count - none of which have to
    be written, tuned or explained.
    """
    Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc')
    row = queued()[0]
    assert not Queue().next_task_in_queue('redfish', status='queued'), (
        'a task queued for the future must not be selectable now'
    )
    assert row['param'] == 'node001'


def test_it_becomes_selectable_once_the_delay_has_passed(node):
    """The other half: deferred must not mean lost."""
    Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc')
    row = queued()[0]
    # bring the created time back as though the delay had elapsed
    Database().update('queue', Helper().make_rows({'created': '2026-08-27 00:00:00'}),
                      [{"column": "id", "value": row['id']}])
    Database().update('queue', Helper().make_rows({'created': 'NOW'}),
                      [{"column": "id", "value": row['id']}])
    assert Queue().next_task_in_queue('redfish', status='queued')


def test_deferring_does_not_break_the_duplicate_collapse(node):
    """
    The collapse looks for an identical task created inside the last fifteen
    minutes. A future created time is still inside that window, so a node
    reporting the stage twice must still queue once - checked, because a delay
    that quietly disabled deduplication would only show up in a boot storm.
    """
    for _ in range(4):
        Monitor().redfish_on_setupbmc(nodename=node, state='install.setupbmc')
    assert len(queued()) == 1
