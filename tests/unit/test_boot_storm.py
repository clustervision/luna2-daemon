#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
A whole cluster booting at once, against the collection this repo just gained.

The development rig is a handful of nodes and the clusters are thousands, so the
cost of one node here is multiplied by a number nobody is looking at. Two of those
multiplications are real:

  * the event fires from update_nodestatus, which every node calls during install
  * the drain shares push_mother with the osimage syncs, so anything it waits on
    delays those

Both are measured rather than argued, because a paragraph of reasoning cannot say
how long a pass takes. The BMCs here are addressed into a range nothing answers -
a dark cluster is the realistic bad case, not an unusual one.
"""

import time

import pytest

from base.monitor import Monitor
from utils.bios_push import BiosPush
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue

NODES = 1500


@pytest.fixture(name='cluster')
def cluster_fixture(sqlite_db):
    """A cluster of dark BMCs: addressed, assigned a redfishsetup, answering nothing."""
    Database().insert('group', [{"column": "name", "value": 'compute'},
                                {"column": "id", "value": 1}])
    Database().insert('redfishsetup', [{"column": "name", "value": 'dc'},
                                       {"column": "id", "value": 1},
                                       {"column": "scheme", "value": 'https'}])
    Database().insert('redfishaccount', [{"column": "id", "value": 1},
                                         {"column": "redfishsetupid", "value": 1},
                                         {"column": "name", "value": 'ro'},
                                         {"column": "username", "value": 'ro'},
                                         {"column": "password", "value": 'pw'},
                                         {"column": "role", "value": 'ReadOnly'}])
    for num in range(1, NODES + 1):
        Database().insert('node', [{"column": "name", "value": f'node{num:04d}'},
                                   {"column": "id", "value": num},
                                   {"column": "groupid", "value": 1},
                                   {"column": "redfishsetupid", "value": 1}])
        Database().insert('nodeinterface', [{"column": "id", "value": num},
                                            {"column": "nodeid", "value": num},
                                            {"column": "interface", "value": 'BMC'}])
        Database().insert('ipaddress', [{"column": "id", "value": num},
                                        {"column": "tableref", "value": 'nodeinterface'},
                                        {"column": "tablerefid", "value": num},
                                        {"column": "ipaddress",
                                         "value": f'10.254.{num // 250}.{(num % 250) + 1}'}])
    return NODES


def storm(count=NODES):
    for num in range(1, count + 1):
        Monitor().redfish_on_setupbmc(nodename=f'node{num:04d}', state='install.setupbmc')


def collections():
    """
    Counted as a delta rather than a total. The queue table is not this test's
    alone, so an absolute count measures whatever else has been through it - which
    passes or fails on test ordering and says nothing about the storm.
    """
    return [row for row in Database().get_record(table='queue') or []
            if row['task'] == 'collect_redfish_inventory']


def test_the_event_costs_one_task_per_node_and_no_more(cluster):
    """
    One entry per node, not a fan-out. Measured at ~1 ms a node, so the whole
    cluster reporting the stage costs a couple of seconds spread over however long
    an install takes - the event is not the expensive part.
    """
    before = len(collections())
    started = time.time()
    storm()
    elapsed = time.time() - started
    assert len(collections()) - before == NODES
    assert elapsed < 30, f'{NODES} events took {elapsed:.1f}s'


def test_none_of_them_is_selectable_yet(cluster):
    """
    Every one is deferred, so a storm does not hand the worker fifteen hundred
    tasks the moment it arrives - it hands them over once the BMCs have had time
    to come up.
    """
    storm()
    assert not Queue().next_task_in_queue('redfish', status='queued')


def test_a_cluster_reporting_twice_does_not_double_the_queue(cluster):
    """
    The fifteen-minute collapse, at scale. A node that reboots into the same stage
    during a storm - which is exactly when it happens - must not add a second sweep.
    """
    storm()
    after_first = len(collections())
    storm(count=200)
    assert len(collections()) == after_first, (
        'a second report from 200 nodes queued more work'
    )


def test_the_drain_returns_even_though_every_bmc_is_dark(cluster):
    """
    The property that matters. push_mother also carries the osimage syncs, so a
    drain that waited on the BMCs would hold those for as long as fifteen hundred
    connect timeouts take - which is the shape of an outage, not a slow pass.

    It schedules and returns, so the whole dark cluster costs a fraction of a
    second. The bound is generous against the measured time on purpose: this is
    here to catch a change that makes it collect inline, not to police the clock.

    The storm is aged first because every task is deferred five minutes when it is
    queued - without that the drain finds nothing selectable and measures the empty
    case, which is the wrong reassurance entirely.
    """
    storm()
    Database().update('queue', Helper().make_rows({'created': 'NOW'}),
                      [{"column": "task", "value": 'collect_redfish_inventory'}])
    started = time.time()
    assert BiosPush().collect_queued_inventory() is True
    elapsed = time.time() - started
    assert elapsed < 10, f'the drain blocked for {elapsed:.1f}s on dark BMCs'
    assert not collections(), 'the queue is emptied by draining it'
