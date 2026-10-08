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


def test_log_tasks_in_queue_renders_pid_column(db):
    """The queue-log table display must render the PID column without erroring, owner or not."""
    from utils.queue import Queue
    _add(db, request_id='LG1', status='in progress', owner_pid=12345, owner_started='1')
    _add(db, request_id='LG2', status='queued')                       # no owner -> blank PID
    assert Queue().log_tasks_in_queue(subsystem='osimage') is True


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


def test_subsystem_requests_excludes_parked_only_chains(db):
    """A parked-only request_id (deferred HA sync) is not a reaper candidate; a real chain is."""
    from utils.queue import Queue
    _add(db, request_id='PK', task='sync_osimage_with_master', status='parked')
    assert 'PK' not in [r['request_id'] for r in Queue().subsystem_requests('osimage')], \
        "a completed pack's lone parked sync is deferred work, not an orphan"
    _add(db, request_id='WK', task='pack_osimage', status='in progress', owner_pid=999999, owner_started='1')
    assert 'WK' in [r['request_id'] for r in Queue().subsystem_requests('osimage')]


def test_reaper_keeps_lone_parked_sync_but_clears_a_failed_chain(db):
    """Reaper preserves a completed pack's parked sync; a failed chain takes its parked with it."""
    _add(db, request_id='DONE', task='sync_osimage_with_master', status='parked')
    _add(db, request_id='FAIL', task='pack_osimage', status='in progress', owner_pid=999999, owner_started='1')
    _add(db, request_id='FAIL', task='sync_osimage_with_master', status='parked')
    _reaper().reap_osimage_queue()
    assert db.get_record(table='queue', where="request_id='DONE'"), "completed pack's parked sync preserved"
    assert not db.get_record(table='queue', where="request_id='FAIL'"), "failed chain incl. its parked sync removed"


# --------------------------------------------------------------- safe cancel (kill gate)

def test_safe_kill_worker_refuses_dead_vital_and_self(helper):
    assert helper.safe_kill_worker(999999, '1') is False, "a dead/gone pid delivers nothing"
    assert helper.safe_kill_worker(1, '1') is False, "pid 1 is refused"
    me = os.getpid()
    assert helper.safe_kill_worker(me, helper.proc_start_time(me)) is False, "never signal self"


def test_safe_kill_worker_kills_an_isolated_child(helper):
    """A worker in its own session (setsid) is group-killed, taking its children with it."""
    import subprocess
    import time
    child = subprocess.Popen(['sleep', '30'], start_new_session=True)
    try:
        started = helper.proc_start_time(child.pid)
        assert started is not None
        assert helper.safe_kill_worker(child.pid, started) is True
        for _ in range(50):
            if child.poll() is not None:
                break
            time.sleep(0.05)
        assert child.poll() is not None, "the isolated worker group should have been killed"
    finally:
        if child.poll() is None:
            child.kill()


def _base_osimage():
    from base.osimage import OSImage
    from utils.log import Log
    oi = OSImage.__new__(OSImage)
    oi.logger = Log.get_logger()
    return oi


def test_cancel_pack_no_active_pack(db):
    assert _base_osimage().cancel_pack('nope')[0] is False, "nothing to cancel -> False"


def test_cancel_pack_aborts_a_dead_worker_chain(db):
    """Cancel with a worker already gone still aborts the chain and EOFs the client."""
    _add(db, request_id='P', param='imgP', status='in progress', owner_pid=999999, owner_started='1')
    ok, _msg = _base_osimage().cancel_pack('imgP')
    assert ok is True
    assert not db.get_record(table='queue', where="request_id='P'"), "chain removed"
    assert db.get_record(table='status', where="request_id='P' AND message='EOF'"), "client EOF'd"


def test_cancel_pack_kills_a_live_in_progress_worker(db, helper, monkeypatch):
    """The primary case: a running pack is cancelled by actually killing its live worker."""
    import subprocess
    import time
    from utils.osimage import OsImage
    monkeypatch.setattr(OsImage, 'cleanup_image_mounts',
                        lambda self, name: (True, 'no mounts remain'))
    worker = subprocess.Popen(['sleep', '30'], start_new_session=True)   # a live session leader
    try:
        started = helper.proc_start_time(worker.pid)
        _add(db, request_id='LP', param='imgLP', status='in progress',
             owner_pid=worker.pid, owner_started=started)
        ok, msg = _base_osimage().cancel_pack('imgLP')
        assert ok is True
        assert 'worker stopped' in msg, "a live worker must actually be signalled, not just cleaned up"
        for _ in range(50):
            if worker.poll() is not None:
                break
            time.sleep(0.05)
        assert worker.poll() is not None, "the live in-progress worker must be killed"
        assert not db.get_record(table='queue', where="request_id='LP'"), "chain aborted"
    finally:
        if worker.poll() is None:
            worker.kill()


def test_cancel_leaves_no_artifacts_across_subsystems_and_statuses(db):
    """A cancel must leave nothing behind - chain steps, the housekeeper cleanup tasks, AND the
    parked sync_osimage_with_master all share the pack's request_id, so all go."""
    _add(db, request_id='C1', param='imgC', task='pack_n_build_osimage',
         status='in progress', owner_pid=999999, owner_started='1')
    _add(db, request_id='C1', param='imgC', task='build_osimage', status='queued')
    _add(db, request_id='C1', param='imgC', task='cleanup_old_file',
         subsystem='housekeeper', status='queued')
    _add(db, request_id='C1', param='imgC:controller1', task='sync_osimage_with_master',
         status='parked')
    ok, _msg = _base_osimage().cancel_pack('imgC')
    assert ok is True
    assert not db.get_record(table='queue', where="request_id='C1'"), \
        "no leftover tasks of any subsystem or status (queued/in progress/parked)"


def test_pack_of_an_unknown_image_queues_nothing(db):
    """A pack request names an image that does not exist: refuse it at the API rather than
    queue a worker that fails and leaves a parked sync row behind on an HA pair."""
    from utils.dbstructure import DBStructure
    db.create('osimage', DBStructure().get_database_table_structure('osimage'))
    ok, message = _base_osimage().pack('nope')[:2]
    assert ok is False
    assert 'does not exist' in str(message)
    assert not db.get_record(table='queue'), "nothing was queued for an image that does not exist"



# ------------------------------------------------- cancel lets the worker unmount (TRIX-2210)

def _cancel_signals(monkeypatch, worker_survives_term):
    """cancel_pack with the kill and the liveness check stubbed: which signals does it send?"""
    import signal
    from utils.helper import Helper
    sent = []
    monkeypatch.setattr(Helper, 'safe_kill_worker', lambda self, pid, started, sig=signal.SIGKILL: sent.append(sig) or True)
    monkeypatch.setattr(Helper, 'pid_alive', lambda self, pid, started=None: worker_survives_term)
    return sent


def test_cancel_sends_sigterm_and_leaves_a_stopping_worker_alone(db, monkeypatch):
    """A worker that stops on SIGTERM runs its own finally, which takes the host's dev, proc and
    sys out of the image tree. Cancel must not follow up with SIGKILL."""
    import signal
    sent = _cancel_signals(monkeypatch, worker_survives_term=False)
    _add(db, request_id='T', param='imgT', status='in progress', owner_pid=4242, owner_started='1')
    assert _base_osimage().cancel_pack('imgT')[0] is True
    assert sent == [signal.SIGTERM], f"got {sent}"


def test_cancel_kills_a_worker_that_outlives_the_grace(db, monkeypatch):
    """A worker still there after the grace is killed, then daemon core cleans its mounts."""
    import signal
    from base.osimage import OSImage
    from utils.osimage import OsImage
    cleaned = []
    monkeypatch.setattr(OSImage, 'CANCEL_GRACE_SECONDS', 0.3, raising=False)
    monkeypatch.setattr(OsImage, 'cleanup_image_mounts',
                        lambda self, name: cleaned.append(name) or (True, 'no mounts remain'))
    sent = _cancel_signals(monkeypatch, worker_survives_term=True)
    _add(db, request_id='K', param='imgK', status='in progress', owner_pid=4242, owner_started='1')
    assert _base_osimage().cancel_pack('imgK')[0] is True
    assert sent == [signal.SIGTERM, signal.SIGKILL], f"got {sent}"
    assert cleaned == ['imgK']


def test_cancel_reports_failed_mount_cleanup_after_sigkill(db, monkeypatch):
    """Do not claim a safe cancel when core cannot clear mounts left by the killed plugin."""
    from base.osimage import OSImage
    from utils.osimage import OsImage
    monkeypatch.setattr(OSImage, 'CANCEL_GRACE_SECONDS', 0, raising=False)
    monkeypatch.setattr(OsImage, 'cleanup_image_mounts',
                        lambda self, name: (False, '/images/imgF/sys'))
    _cancel_signals(monkeypatch, worker_survives_term=True)
    _add(db, request_id='F', param='imgF', status='in progress', owner_pid=4242, owner_started='1')

    ok, message = _base_osimage().cancel_pack('imgF')

    assert ok is False
    assert 'mount cleanup failed' in message
    assert not db.get_record(table='queue', where="request_id='F'"), "cancelled chain is still cleared"


def test_cancel_clears_chain_when_mount_discovery_raises(db, monkeypatch):
    """A findmnt or JSON error must not strand a dead worker's unfinished queue chain."""
    from base.osimage import OSImage
    from utils.osimage import OsImage
    monkeypatch.setattr(OSImage, 'CANCEL_GRACE_SECONDS', 0, raising=False)

    def cleanup_raises(_self, _name):
        raise RuntimeError('findmnt failed')

    monkeypatch.setattr(OsImage, 'cleanup_image_mounts', cleanup_raises)
    _cancel_signals(monkeypatch, worker_survives_term=True)
    _add(db, request_id='E', param='imgE', status='in progress', owner_pid=4242, owner_started='1')
    _add(db, request_id='E', param='imgE', task='build_osimage', status='queued')

    ok, message = _base_osimage().cancel_pack('imgE')

    assert ok is False
    assert 'could not inspect or clean image mounts: findmnt failed' in message
    assert not db.get_record(table='queue', where="request_id='E'"), "cancelled chain is cleared"
    assert db.get_record(table='status', where="request_id='E' AND message='EOF'"), "client EOF'd"


def test_mount_targets_below_are_deepest_first(tmp_path, monkeypatch):
    """Core cleanup uses findmnt and keeps nested and stacked mount targets."""
    from utils.osimage import OsImage
    import json
    image = tmp_path / 'image'
    image.mkdir()
    output = {'filesystems': [
        {'target': f'{image}/dev'},
        {'target': f'{image}/sys'},
        {'target': f'{image}/sys/firmware/efi/efivars'},
        {'target': f'{image}/dev'},
        {'target': '/unrelated'},
    ]}

    def run(command, **_kwargs):
        assert command == ['/usr/bin/findmnt', '--list', '--json', '--output', 'TARGET']
        return type('Result', (), {
            'returncode': 0, 'stdout': json.dumps(output), 'stderr': ''})()

    monkeypatch.setattr('utils.osimage.subprocess.run', run)
    targets = OsImage._mount_targets_below(str(image))

    assert targets[0] == f"{image}/sys/firmware/efi/efivars"
    assert targets.count(f"{image}/dev") == 2
    assert '/unrelated' not in targets


def test_cleanup_image_mounts_lazy_unmounts_until_empty(db, tmp_path, monkeypatch):
    """A SIGKILL fallback detaches all nested and stacked mounts, deepest first."""
    from utils.dbstructure import DBStructure
    from utils.osimage import OsImage
    from utils.helper import Helper
    import common.constant as constant

    db.create('osimage', DBStructure().get_database_table_structure('osimage'))
    image = tmp_path / 'img'
    image.mkdir()
    db.insert('osimage', Helper().make_rows({'name': 'img', 'path': str(image)}))
    original_directory = constant.CONSTANT['FILES']['IMAGE_DIRECTORY']
    constant.CONSTANT['FILES']['IMAGE_DIRECTORY'] = str(tmp_path)
    passes = [[f"{image}/sys/efi", f"{image}/sys", f"{image}/dev", f"{image}/dev"], []]
    seen = []

    def targets(_path):
        return passes.pop(0)

    def run(command, **_kwargs):
        seen.append(command)
        return type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()

    monkeypatch.setattr(OsImage, '_mount_targets_below', staticmethod(targets))
    monkeypatch.setattr('utils.osimage.subprocess.run', run)
    try:
        ok, message = _reaper().cleanup_image_mounts('img')
    finally:
        constant.CONSTANT['FILES']['IMAGE_DIRECTORY'] = original_directory

    assert ok is True, message
    assert seen == [
        ['/usr/bin/umount', '--lazy', '--', f"{image}/sys/efi"],
        ['/usr/bin/umount', '--lazy', '--', f"{image}/sys"],
        ['/usr/bin/umount', '--lazy', '--', f"{image}/dev"],
        ['/usr/bin/umount', '--lazy', '--', f"{image}/dev"],
    ]
