#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2193: every osimage route that packs on the master queues the peer sync. A route
that packs without it leaves the peer naming files it does not have, and a node booting
from the peer gets the previous image. The pack route had the call, the kernel route did
not; this pins all of them against the same rule.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app

PACKING_ROUTES = [
    ('get', '/config/osimage/img/_pack', 'pack', None),
    ('get', '/config/osimage/img/_updatecerts', 'update_certs', None),
    ('post', '/config/osimage/img/kernel', 'change_kernel',
     {'config': {'osimage': {'img': {'kernelversion': '1.0'}}}}),
]


@pytest.fixture
def master(monkeypatch):
    """HA enabled, this controller the master; the pack itself is stubbed as queued."""
    import routes.config_osimage as route
    monkeypatch.setattr(route.HA, 'get_hastate', lambda self: True)
    monkeypatch.setattr(route.HA, 'get_role', lambda self: True)
    synced = []
    monkeypatch.setattr(route.Journal, 'queue_source_sync',
                        lambda self, name, request_id=None: synced.append((name, request_id)))
    return synced


@pytest.mark.parametrize('method, path, base_method, body', PACKING_ROUTES)
def test_a_pack_on_the_master_queues_the_peer_sync(sqlite_db, master, monkeypatch, method, path, base_method, body):
    from common.constant import CONSTANT
    import routes.config_osimage as route
    monkeypatch.setattr(route.OSImage, base_method,
                        lambda self, *args, **kwargs: (True, 'osimage pack for img queued', 'rid-1'))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    kwargs = {'headers': {'x-access-tokens': token}}
    if body is not None:
        kwargs.update(data=json.dumps(body), content_type='application/json')
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 200, response.data
    assert master == [('img', 'rid-1')], f'{path} packed on the master without queueing the peer sync'
