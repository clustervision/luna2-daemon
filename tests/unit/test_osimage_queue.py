#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1930: osimage queue concurrency, liveness and recovery.

Pins the primitives the fix rests on, against a throwaway SQLite database so the real Queue /
OsImage code is exercised:

- claim_task is a genuine compare-and-set (two mothers cannot both take one task),
- pid liveness tells a live worker from a dead one AND from a reused pid (start-time guard),
- next_task_in_queue with owner_pid steps around a chain a live worker already owns - which the
  atomic claim alone cannot do, because the two mothers take different task ids of one chain,
- the reaper aborts a chain whose worker is gone, leaves a live one strictly alone, and does not
  touch a just-queued chain that is merely awaiting its mother.
"""

import os
import pytest

from utils.helper import Helper


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the queue and status tables created."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'queue.db')
    database.local_thread.connection = None
    for table in ['queue', 'status']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _add(db, **fields):
    """Insert one queue row through the real insert path; return its id."""
    from utils.database import Database
    row = {'subsystem': 'osimage', 'status': 'queued', 'request_id': 'r',
           'task': 'pack_osimage', 'param': 'img', 'noeof': 0, 'created': 'NOW'}
    row.update(fields)
    return Database().insert('queue', Helper().make_rows(row))


def _reaper():
    """An OsImage with just a logger, so reap_osimage_queue runs without loading plugins."""
    from utils.osimage import OsImage
    from utils.log import Log
    oi = OsImage.__new__(OsImage)
    oi.logger = Log.get_logger()
    return oi


# --------------------------------------------------------------- atomic claim

def test_claim_task_is_compare_and_set(db):
    """First caller wins the row; a second caller on the same id loses - no double dispatch."""
    from utils.queue import Queue
    tid = _add(db, request_id='r1')
    assert Queue().claim_task(tid, 111, 'aaa') is True
    assert Queue().claim_task(tid, 222, 'bbb') is False
    row = db.get_record(table='queue', where=f"id='{tid}'")[0]
    assert row['status'] == 'in progress'
    assert str(row['owner_pid']) == '111', "the winner's owner stamp must survive"


# --------------------------------------------------------------- pid liveness

def test_pid_liveness_and_reuse(helper):
    me = os.getpid()
    started = helper.proc_start_time(me)
    assert started is not None
    assert helper.pid_alive(me, started) is True
    assert helper.pid_alive(me, '0') is False, "mismatched start-time = a reused pid, treat as dead"
    assert helper.pid_alive(999999, '1') is False, "no such process"
    assert helper.pid_alive(None) is False


# --------------------------------------------------------------- chain ownership

def test_chain_live_owner(db):
    from utils.queue import Queue
    me = os.getpid()
    started = Helper().proc_start_time(me)
    _add(db, request_id='A', status='in progress', owner_pid=me, owner_started=started)
    _add(db, request_id='B', status='in progress', owner_pid=me, owner_started='0')      # reused
    _add(db, request_id='C', status='in progress', owner_pid=999999, owner_started='1')  # dead
    assert Queue().chain_live_owner('A', my_pid=1) == me, "a live, foreign owner is reported"
    assert Queue().chain_live_owner('A', my_pid=me) is None, "my own ownership is not foreign"
    assert Queue().chain_live_owner('B', my_pid=1) is None, "a reused pid does not count as owner"
    assert Queue().chain_live_owner('C', my_pid=1) is None, "a dead pid does not count as owner"


def test_next_task_in_queue_skips_owned_chain(db):
    """The owner-aware selector is what prevents co-processing one chain; plain mode is unchanged."""
    from utils.queue import Queue
    me = os.getpid()
    started = Helper().proc_start_time(me)
    _add(db, request_id='A', status='in progress', owner_pid=me, owner_started=started)
    t2 = _add(db, request_id='A', status='queued')
    t3 = _add(db, request_id='B', status='queued')
    assert Queue().next_task_in_queue('osimage', 'queued') == t2, "plain: lowest-id queued task"
    assert Queue().next_task_in_queue('osimage', 'queued', owner_pid=1) == t3, \
        "owner-aware for another mother: skip A (live foreign owner), take B"


# --------------------------------------------------------------- reaper (cleanup-only)

def test_reap_aborts_dead_owner_chain(db):
    """A worker died mid-chain: its tasks are removed and its client is EOF'd."""
    _add(db, request_id='D', status='in progress', owner_pid=999999, owner_started='1')
    _reaper().reap_osimage_queue()
    assert not db.get_record(table='queue', where="request_id='D'"), "dead chain's tasks removed"
    assert db.get_record(table='status', where="request_id='D' AND message='EOF'"), \
        "the reaped chain must EOF its client, so the CLI unblocks"


def test_reap_leaves_a_live_owner_alone(db):
    me = os.getpid()
    started = Helper().proc_start_time(me)
    _add(db, request_id='L', status='in progress', owner_pid=me, owner_started=started)
    _reaper().reap_osimage_queue()
    assert db.get_record(table='queue', where="request_id='L'"), "a live worker's chain is untouched"


def test_reap_leaves_a_just_queued_orphan(db):
    """A queued chain with no owner may just be awaiting its mother - within grace, leave it."""
    _add(db, request_id='Y', status='queued', created='NOW')
    _reaper().reap_osimage_queue()
    assert db.get_record(table='queue', where="request_id='Y'"), "young orphan kept (grace window)"
