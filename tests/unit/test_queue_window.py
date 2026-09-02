"""
The queue's hour-long window and the drains that outlive it.

next_task_in_queue only returns tasks created in the last hour. A BIOS push
reboots each node and can take minutes per node, a profile delivery waits on
nodes, and an install storm defers inventory collections: any of these queues
grows past an hour of work, and everything behind that hour was left queued
forever, never served, never reaped, visible as 'queued' in the status view.
"""

import pytest


@pytest.fixture
def queue_db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'queue.db')
    database.local_thread.connection = None
    Database().create('queue', DBStructure().get_database_table_structure('queue'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _queue(db, subsystem, tasks, backdate_minutes=()):
    """Queue the tasks; backdate the ones with a minute count, straight in the file."""
    import sqlite3
    import common.constant as constant
    from utils.helper import Helper
    for index, task in enumerate(tasks):
        db.insert('queue', Helper().make_rows({'subsystem': subsystem, 'task': task, 'param': task,
                                               'status': 'queued', 'request_id': f'r{index}', 'created': 'NOW'}))
    with sqlite3.connect(constant.CONSTANT['DATABASE']['DATABASE']) as raw:
        for index, minutes in enumerate(backdate_minutes):
            if minutes:
                raw.execute(f"UPDATE queue SET created = datetime('now','-{minutes} minute') WHERE request_id = 'r{index}'")


def _drain(subsystem, **kwargs):
    from utils.queue import Queue
    from utils.database import Database
    served = []
    while next_id := Queue().next_task_in_queue(subsystem, status='queued', **kwargs):
        served.append(next_id)
        Database().update('queue', [{'column': 'status', 'value': 'done'}], [{'column': 'id', 'value': next_id}])
    return served


def test_a_drain_without_the_window_serves_the_whole_queue(queue_db):
    _queue(queue_db, 'bios', ['push_bios:node001', 'push_bios:node002', 'push_bios:node003'], (61, 61, 0))
    assert len(_drain('bios', window=None)) == 3


def test_the_default_window_still_drops_the_hour_old_tail(queue_db):
    """The short-lived subsystems keep the hour; this pins what they get."""
    _queue(queue_db, 'service', ['a', 'b', 'c'], (61, 61, 0))
    assert len(_drain('service')) == 1


def test_every_long_running_drain_asks_for_no_window():
    """Derived: the drains that outlive an hour must say so, or the tail is lost again."""
    import os, re
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon', 'utils')
    for name, subsystem in (('bios_push.py', 'bios'), ('bios_push.py', 'redfish'), ('profile_sync.py', 'profile')):
        body = open(os.path.join(here, name), encoding='utf-8').read()
        calls = re.findall(rf"next_task_in_queue\('{subsystem}'[^)]*\)", body)
        assert calls and all('window=None' in call for call in calls), f'{name}: {subsystem} drain keeps the hour window: {calls}'
