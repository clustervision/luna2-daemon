#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
POST /monitor/status, the receiver of status messages pushed from elsewhere. A message
carries its own status and the row keeps it, so a failure line reads as one; a message
that names none is a plain 200.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app


def _push(client, request_id, messages):
    from common.constant import CONSTANT
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    body = {'monitor': {'status': {'request_id': request_id, 'messages': messages}}}
    return client.post('/monitor/status', data=json.dumps(body), content_type='application/json',
                       headers={'x-access-tokens': token})


def _rows(request_id):
    from utils.database import Database
    rows = Database().get_record(table='status', where=f"request_id = '{request_id}'") or []
    return [(row['message'], int(row['status'])) for row in rows]


def test_a_pushed_message_keeps_its_own_status(sqlite_db):
    response = _push(routes_app().test_client(), '1761835000.12345', [
        {'message': 'play started', 'status': 200},
        {'message': 'build failed', 'status': 501},
        {'message': 'EOF'},
    ])
    assert response.status_code == 201, response.data
    assert _rows('1761835000.12345') == [('play started', 200), ('build failed', 501), ('EOF', 200)]
