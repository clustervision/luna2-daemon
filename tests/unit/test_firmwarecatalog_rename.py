#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: luna firmwarecatalog rename sends newfirmwarename, which the daemon did not
know: the update failed on the unknown column and the answer still said updated. A
rename now renames, and a field that is not a column is refused, as the neighbours do.
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
    for name in ('fw-a', 'fw-taken'):
        Database().insert('firmwarecatalog', Helper().make_rows(
            {'name': name, 'manufacturer': 'M', 'model': 'X', 'component': 'BMC', 'version': '1'}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(name, **fields):
        response = client.post(f'/config/firmwarecatalog/{name}', headers={'x-access-tokens': token},
                               data=json.dumps({'config': {'firmwarecatalog': {name: fields}}}),
                               content_type='application/json')
        return response.status_code, json.loads(response.data or b'{}').get('message', '')
    return post


def names():
    return sorted(row['name'] for row in Database().get_record(table='firmwarecatalog') or [])


def test_a_rename_renames(post):
    code, message = post('fw-a', newfirmwarename='fw-b')
    assert code == 204, message
    assert names() == ['fw-b', 'fw-taken']


def test_a_rename_onto_an_existing_entry_is_refused(post):
    code, message = post('fw-a', newfirmwarename='fw-taken')
    assert code == 400 and 'already exists' in message
    assert names() == ['fw-a', 'fw-taken']


def test_a_field_that_is_not_a_column_is_refused(post):
    code, message = post('fw-a', zzz_unknown_field=1)
    assert code == 400 and 'Columns are incorrect' in message
    assert names() == ['fw-a', 'fw-taken']


def test_a_comment_is_cleared_with_an_empty_string(post):
    assert post('fw-a', comment='set')[0] == 204
    code, message = post('fw-a', comment='')
    assert code == 204, message
    assert Database().get_record(table='firmwarecatalog', where="name = 'fw-a'")[0]['comment'] == ''
