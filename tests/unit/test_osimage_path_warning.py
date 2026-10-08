#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1634: a path set by hand that does not exist on this controller is reported, not
refused. The report has to reach the caller: a successful change answers 204, which
carries no body, so an answer with a warning in it answers 201 instead.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app


def _post(client, name, body):
    from common.constant import CONSTANT
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    return client.post(f'/config/osimage/{name}', data=json.dumps({'config': {'osimage': {name: body}}}),
                       content_type='application/json', headers={'x-access-tokens': token})


@pytest.fixture
def client(sqlite_db, monkeypatch):
    import routes.config_osimage as route
    monkeypatch.setattr(route.HA, 'get_hastate', lambda self: False)
    return routes_app().test_client()


def test_a_warning_keeps_the_body_a_204_would_drop():
    from utils.helper import Helper
    assert Helper().get_access_code(True, 'OS Image x updated') == 204
    assert Helper().get_access_code(True, 'OS Image x updated; warning: path /nope does not exist on this controller') == 201
    assert Helper().get_access_code(True, 'OS Image x created') == 201
    assert Helper().get_access_code(True, 'Firmware catalog x updated; note: stage it on the active controller') == 201
    assert Helper().get_access_code(True, 'Secret x updated. Warning: owner is not resolvable') == 201


@pytest.mark.parametrize('message', [
    'Group notebooks removed',
    'Group warning-team removed',
    'Group release-note removed',
    'Group x updated with warning text',
    'Group x deleted with note text',
])
def test_words_that_contain_warning_or_note_do_not_keep_a_success_body(message):
    from utils.helper import Helper
    assert Helper().get_access_code(True, message) == 204


def test_a_missing_path_is_reported_on_create_and_on_change(client, tmp_path):
    created = _post(client, 'img', {'path': '/nope/img'})
    assert created.status_code == 201
    assert 'warning: path /nope/img does not exist' in created.get_json()['message']
    changed = _post(client, 'img', {'path': '/nope/elsewhere'})
    assert changed.status_code == 201, 'a change with a warning must answer 201 or the warning is lost'
    assert 'warning: path /nope/elsewhere does not exist' in changed.get_json()['message']


def test_an_existing_path_and_a_change_without_a_path_answer_as_before(client, tmp_path):
    there = tmp_path / 'img'
    there.mkdir()
    created = _post(client, 'img', {'path': str(there)})
    assert created.status_code == 201 and 'warning' not in created.get_json()['message']
    changed = _post(client, 'img', {'comment': 'x'})
    assert changed.status_code == 204, 'no warning, nothing to say: 204 as today'
