#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: an Invalid request is a 400 on every route. These routes set 404 for any
failure, or their base worded a request error without saying so; the code now follows
the message through get_access_code, as everywhere else. Success codes are unchanged.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


@pytest.fixture(name='post')
def post_fixture(sqlite_db):
    from common.constant import CONSTANT
    db = Database()
    db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    db.insert('osimage', Helper().make_rows({'name': 'img1', 'path': '/trinity/images/img1'}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(path, body):
        response = client.post(path, headers={'x-access-tokens': token}, data=json.dumps(body),
                               content_type='application/json')
        return response.status_code, json.loads(response.data or b'{}').get('message', '')
    return post


CASES = [
    ('/config/node/inventory/_redfish', {'config': {'node': {}}}),
    ('/config/node/redfishaccounts/_provision', {'config': {'node': {}}}),
    ('/config/osimage/img1/_clone', {'config': {'osimage': {'img1': {}}}}),
    ('/config/osimage/img1/kernel', {'config': {'osimage': {'img1': {'zzz_not_a_column': 1}}}}),
    ('/config/rack/inventory', {'config': {'rack': {'inventory': [{'type': 'node'}]}}}),
]


@pytest.mark.parametrize('path,body', CASES, ids=[c[0] for c in CASES])
def test_an_invalid_request_is_a_400(post, path, body):
    code, message = post(path, body)
    assert message.startswith('Invalid request'), message
    assert code == 400, (code, message)
