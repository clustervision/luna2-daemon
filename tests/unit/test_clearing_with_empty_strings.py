#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: an empty string clears a field. The value quoting, the body shape check and
the column checks added for the endpoint sweep must all leave that working.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


@pytest.mark.parametrize('field', ['comment', 'kerneloptions'])
def test_a_node_field_is_cleared_with_an_empty_string(sqlite_db, field):
    from common.constant import CONSTANT
    db = Database()
    db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    groupid = db.insert('group', Helper().make_rows({'name': 'g1'}))
    db.insert('node', Helper().make_rows({'name': 'n1', 'groupid': groupid, field: 'set'}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    response = client.post('/config/node/n1', headers={'x-access-tokens': token},
                           data=json.dumps({'config': {'node': {'n1': {field: ''}}}}), content_type='application/json')
    assert response.status_code in (200, 201, 204), response.data
    assert Database().get_record(table='node', where="name = 'n1'")[0][field] in ('', None)
