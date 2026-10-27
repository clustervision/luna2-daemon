#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: a redfishsetup rename is an update, and answers 204 like the other renames,
which is what luna redfishsetup rename waits for. It answered 201 and the CLI exited 1.
"""

import json

from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


def test_a_rename_answers_204_and_renames(sqlite_db):
    from common.constant import CONSTANT
    Database().insert('redfishsetup', Helper().make_rows({'name': 'rf-a', 'scheme': 'https'}))
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    response = routes_app().test_client().post(
        '/config/redfishsetup/rf-a', headers={'x-access-tokens': token}, content_type='application/json',
        data=json.dumps({'config': {'redfishsetup': {'rf-a': {'newredfishsetupname': 'rf-b'}}}}))
    assert response.status_code == 204, response.data
    assert [row['name'] for row in Database().get_record(table='redfishsetup')] == ['rf-b']
