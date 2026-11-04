#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2351: GET /config/osimage/<name>/_packing answers the request id and queue status of the
image's pack while it is in the queue, so a client can follow a pack someone else started and tell
a scheduled one from a running one without a second call.

The answer comes from the queue layer, as the boot pause's does, and packs are queued on the
master only: the caller asks the master, and another controller answers 503 rather than the
null that means "no pack in the queue".
"""

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app


@pytest.fixture
def get(sqlite_db, monkeypatch):
    from common.constant import CONSTANT
    from utils.database import Database
    from utils.helper import Helper
    from utils.ha import HA
    monkeypatch.setattr(HA, 'get_hastate', lambda self: False)
    for image in ('rocky9', 'alma9'):
        Database().insert('osimage', Helper().make_rows({'name': image, 'path': f'/{image}'}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    return lambda path: client.get(path, headers={'x-access-tokens': token})


def queue(task, param, request_id='r1', subsystem='osimage', status='in progress', created='NOW'):
    from utils.database import Database
    from utils.helper import Helper
    Database().insert('queue', Helper().make_rows({
        'subsystem': subsystem, 'status': status, 'request_id': request_id, 'task': task,
        'param': param, 'noeof': 0, 'created': created}))


def oldest_in_queue(**filters):
    from utils.queue import Queue
    try:
        task = Queue().tasks_in_queue(details=True, **filters)
    except TypeError:
        return 'no details argument'
    return task.get('request_id') if isinstance(task, dict) else task


def in_a_pair(monkeypatch, master):
    from utils.ha import HA
    monkeypatch.setattr(HA, 'get_hastate', lambda self: True)
    monkeypatch.setattr(HA, 'get_role', lambda self: master)


@pytest.mark.parametrize('task,param,subsystem,status,created,expected', [
    (None, None, 'osimage', None, None, False),
    ('pack_n_build_osimage', 'rocky9', 'osimage', 'in progress', 'NOW', 'r1'),
    ('pack_n_build_osimage', 'rocky9', 'osimage', 'queued', 'NOW +1 hour', 'r1'),
    ('pack_n_build_osimage', 'rocky9:nocleanup', 'osimage', 'in progress', 'NOW', False),
    ('pack_n_build_osimage', 'rocky9', 'housekeeper', 'in progress', 'NOW', False),
    ('updatecerts_osimage', 'rocky9', 'osimage', 'in progress', 'NOW', False),
    ('pack_n_build_osimage', 'alma9', 'osimage', 'in progress', 'NOW', False),
])
def test_the_queue_answers_what_the_boot_pause_counts_as_a_pack(sqlite_db, task, param, subsystem, status, created, expected):
    from utils.queue import Queue
    if task:
        queue(task, param, subsystem=subsystem, status=status, created=created)
    busy = Queue().tasks_in_queue(subsystem='osimage', task='pack_n_build_osimage', subitem='rocky9')
    assert busy is (expected is not False)
    assert oldest_in_queue(subsystem='osimage', task='pack_n_build_osimage', subitem='rocky9') == expected


def test_the_queue_answers_the_oldest_of_two(sqlite_db):
    queue('pack_n_build_osimage', 'rocky9', request_id='first')
    queue('pack_n_build_osimage', 'rocky9', request_id='second')
    assert oldest_in_queue(subsystem='osimage', task='pack_n_build_osimage', subitem='rocky9') == 'first'


def test_the_route_answers_from_the_queue_layer(get, monkeypatch):
    from utils.queue import Queue
    monkeypatch.setattr(Queue, 'tasks_in_queue',
                        lambda self, details=False, **_: {'request_id': 'from-the-queue-layer', 'status': 'in progress'} if details else True)
    response = get('/config/osimage/rocky9/_packing')
    assert response.status_code == 200, response.data
    assert response.get_json() == {'request_id': 'from-the-queue-layer', 'status': 'in progress'}


@pytest.mark.parametrize('ha', [False, True])
@pytest.mark.parametrize('row,expected', [
    (None, {'request_id': None, 'status': None}),
    (('in progress', 'NOW'), {'request_id': 'r1', 'status': 'in progress'}),
    (('queued', 'NOW +1 hour'), {'request_id': 'r1', 'status': 'queued'}),
])
def test_the_master_or_a_single_controller_answers_from_its_own_queue(get, monkeypatch, ha, row, expected):
    if ha:
        in_a_pair(monkeypatch, master=True)
    if row:
        queue('pack_n_build_osimage', 'rocky9', status=row[0], created=row[1])
    response = get('/config/osimage/rocky9/_packing')
    assert response.status_code == 200, response.data
    assert response.get_json() == expected


def test_a_secondary_answers_503_and_not_its_own_queue(get, monkeypatch):
    in_a_pair(monkeypatch, master=False)
    queue('pack_n_build_osimage', 'rocky9', request_id='its-own-stale-row')
    response = get('/config/osimage/rocky9/_packing')
    assert response.status_code == 503, response.data
    assert 'not the master' in (response.get_json() or {}).get('message', '')
    assert 'its-own-stale-row' not in response.get_data(as_text=True)


def test_an_image_that_does_not_exist_is_not_reported_idle(get):
    response = get('/config/osimage/nosuch/_packing')
    assert response.status_code == 404, response.data
    assert response.get_json() == {'message': 'OS image nosuch does not exist'}


@pytest.mark.parametrize('param,subsystem,status,expected', [
    ('rocky9', 'osimage', 'in progress', {'request_id': 'r1', 'status': 'in progress'}),
    ('rocky9', 'osimage', 'queued', {'request_id': 'r1', 'status': 'queued'}),
    ('alma9', 'osimage', 'in progress', {'request_id': None, 'status': None}),
    ('rocky9', 'housekeeper', 'in progress', {'request_id': None, 'status': None}),
])
def test_a_create_answers_until_its_pack_is_queued(get, param, subsystem, status, expected):
    queue('create_osimage', param, subsystem=subsystem, status=status)
    response = get('/config/osimage/rocky9/_packing')
    assert response.status_code == 200, response.data
    assert response.get_json() == expected


@pytest.mark.parametrize('pack_request_id', ['r1', 'a-later-pack'])
def test_the_pack_answers_over_an_older_create(get, pack_request_id):
    queue('create_osimage', 'rocky9', request_id='r1')
    assert get('/config/osimage/rocky9/_packing').get_json() == {'request_id': 'r1', 'status': 'in progress'}
    queue('pack_n_build_osimage', 'rocky9', request_id=pack_request_id, status='queued')
    assert get('/config/osimage/rocky9/_packing').get_json() == {'request_id': pack_request_id, 'status': 'queued'}
