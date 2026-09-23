#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: the node registration route reads fields from an object. A body of any
other shape is refused like any other failed attempt, instead of ending in a 500.
"""

import json

import pytest

from cases.route_requirements_cases import app as routes_app


@pytest.mark.parametrize('body', [[], ['a'], 'text', 5], ids=['empty list', 'list', 'text', 'number'])
def test_a_body_that_is_not_an_object_is_refused_not_a_500(sqlite_db, body):
    response = routes_app().test_client().post('/tpm/node001', data=json.dumps(body),
                                               content_type='application/json')
    assert response.status_code == 401, response.data
    assert b'Invalid request' in response.data or b'data structure' in response.data
