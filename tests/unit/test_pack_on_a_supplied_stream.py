#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2355: a pack can report on a status stream the caller already owns.

A caller that is being polled hands its request_id to the POST route, and the chain writes
there instead of to one of its own. Two things have to hold, and neither is visible from the
GET route:

- the route takes the id from the body and the stream it reports back is the one supplied,
  so the caller keeps polling where it already is;
- when the request is deduped into a chain that is already queued, that chain writes to a
  different stream, so nothing will ever write to the caller's again. The guard has to end
  it, or the caller polls for ever.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app


def test_the_post_route_packs_on_the_supplied_stream(sqlite_db, monkeypatch):
    """The id in the body is what reaches pack() and what comes back as the stream."""
    from common.constant import CONSTANT
    import routes.config_osimage as route
    monkeypatch.setattr(route.HA, 'get_hastate', lambda self: False)
    monkeypatch.setattr(route.OSImage, 'pack',
                        lambda self, name, request_id=None: (
                            True, f'osimage pack for {name} queued', request_id))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    response = client.post('/config/osimage/img/_pack',
                           headers={'x-access-tokens': token},
                           data=json.dumps({'config': {'osimage': {'img': {'request_id': 'rid-x'}}}}),
                           content_type='application/json')

    # the status code first: with no POST handler the method is not allowed, and that has to
    # be what fails rather than a lookup in a body that was never a pack response.
    assert response.status_code == 200, response.data
    assert response.get_json().get('request_id') == 'rid-x', \
        'the pack must report on the stream the caller supplied, not one of its own'


@pytest.mark.parametrize('body, ha_master, pack_returns, code, message', [
    ({}, None, None, 400, 'Invalid request:'),
    ({'request_id': 'rid-x'}, False, None, 503, 'not the master'),
    ({'request_id': 'rid-x'}, None, (False, 'pack failed: no such path'), 404,
     'pack failed: no such path'),
])
def test_the_post_route_refusals(sqlite_db, monkeypatch, body, ha_master, pack_returns, code,
                                 message):
    """Each refusal keeps its status code, and the message says why the pack did not happen."""
    from common.constant import CONSTANT
    import routes.config_osimage as route
    monkeypatch.setattr(route.HA, 'get_hastate', lambda self: ha_master is not None)
    monkeypatch.setattr(route.HA, 'get_role', lambda self: ha_master)
    monkeypatch.setattr(route.OSImage, 'pack', lambda self, name, request_id=None: pack_returns)
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    response = client.post('/config/osimage/img/_pack',
                           headers={'x-access-tokens': token},
                           data=json.dumps({'config': {'osimage': {'img': body}}}),
                           content_type='application/json')

    assert response.status_code == code, response.data
    assert message in (response.get_json() or {}).get('message', '')
    if code == 400:
        assert response.get_json()['message'].startswith(message)


def test_the_dedupe_guard_ends_the_supplied_stream(sqlite_db):
    """Folded into a chain that is already queued: say where it went, then EOF the caller."""
    from base.osimage import OSImage
    from utils.database import Database
    from utils.helper import Helper
    from utils.log import Log
    Database().insert('osimage', Helper().make_rows({'name': 'img', 'path': '/img'}))
    Database().insert('queue', Helper().make_rows(
        {'subsystem': 'osimage', 'task': 'pack_n_build_osimage', 'param': 'img',
         'status': 'queued', 'request_id': 'running-chain', 'noeof': 0, 'created': 'NOW'}))
    image = OSImage.__new__(OSImage)
    image.logger = Log.get_logger()

    returned = image.pack('img', request_id='mine')

    assert returned[0] is True
    assert returned[2] == 'running-chain', 'the caller is told which chain it was folded into'
    assert Database().get_record(
        table='status', where="request_id='mine' AND message='EOF'"), \
        'the supplied stream is never written to again, so it must be ended'
