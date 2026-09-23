#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: the node, group and cluster entry routes take a list of objects. Anything
else is refused with a 400 before an entry is read; it used to end in a 500.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper

ROUTES = [('/config/secrets/node/n1', ('node', 'n1')), ('/config/secrets/node/n1/s1', ('node', 'n1')),
          ('/config/secrets/node/n1/s1/_clone', ('node', 'n1')),
          ('/config/secrets/group/g1', ('group', 'g1')), ('/config/secrets/group/g1/s1', ('group', 'g1')),
          ('/config/secrets/group/g1/s1/_clone', ('group', 'g1')),
          ('/config/secrets/cluster', ('cluster', None)), ('/config/secrets/cluster/s1', ('cluster', None)),
          ('/config/secrets/cluster/s1/_clone', ('cluster', None))]


@pytest.fixture(name='post')
def post_fixture(sqlite_db):
    from common.constant import CONSTANT
    db = Database()
    db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    groupid = db.insert('group', Helper().make_rows({'name': 'g1'}))
    db.insert('node', Helper().make_rows({'name': 'n1', 'groupid': groupid}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(path, scope, value):
        kind, name = scope
        inner = {kind: {name: value}} if name else {kind: value}
        response = client.post(path, headers={'x-access-tokens': token},
                               data=json.dumps({'config': {'secrets': inner}}), content_type='application/json')
        return response.status_code, json.loads(response.data or b'{}').get('message', '')
    return post


@pytest.mark.parametrize('path,scope', ROUTES)
@pytest.mark.parametrize('value', [{'name': 's1', 'content': 'x'}, ['s1'], [['s1']]],
                         ids=['a dict for the list', 'a list of text', 'a list of lists'])
def test_anything_but_a_list_of_objects_is_a_400(post, path, scope, value):
    code, message = post(path, scope, value)
    assert code == 400 and 'Invalid request' in message, (code, message)


@pytest.mark.parametrize('path,scope', ROUTES[:1] + ROUTES[3:4] + ROUTES[6:7])
def test_a_list_of_objects_still_goes_through(post, path, scope):
    code, message = post(path, scope, [{'name': 's1', 'content': 'x', 'path': '/tmp/s1'}])
    assert code in (200, 201, 204), (code, message)
