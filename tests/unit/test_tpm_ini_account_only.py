#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
A node signs in through /tpm as the configuration-file account, never as a person:
the authentication chain is never asked, and the configuration-file account still goes
through get_token's own password check.
"""

import json

import pytest
from jwt import decode

from cases.route_requirements_cases import app as routes_app

pytest.importorskip('base.authentication')


@pytest.fixture
def node_and_cluster(db, seed):
    from utils.dbstructure import DBStructure
    db.create('cluster', DBStructure().get_database_table_structure('cluster'))
    db.insert('cluster', [{'column': 'name', 'value': 'trinity'}, {'column': 'security', 'value': 0}])
    return seed['nodeid']


@pytest.fixture
def auth(monkeypatch):
    import common.constant as constant
    from base.authentication import Authentication
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    return Authentication()


@pytest.fixture
def chain_calls(monkeypatch):
    """Record every walk of the authentication chain; the node route must make none."""
    from base.authentication import Authentication
    calls = []

    def login(self, username=None, password=None):
        calls.append(username)
        return 7, 'verified'
    monkeypatch.setattr(Authentication, 'login', login)
    return calls


def stored(db):
    return db.get_record(table='node', where="name = 'node001'")[0]['tpm_sha256']


def test_a_person_is_refused_before_the_chain_is_asked(db, node_and_cluster, chain_calls, auth):
    body = {'tpm_sha256': 'a' * 64, 'username': 'someone', 'password': 'theirs'}
    status, response = auth.node_token(body, 'node001')
    assert status is False
    assert 'configuration-file account' in response
    assert chain_calls == [], "the authentication chain must not be consulted for a node sign-in"
    assert not stored(db), "a refused sign-in must not store the measurement it carried"


def test_the_configuration_file_account_still_needs_its_password(db, node_and_cluster, chain_calls, auth):
    status, response = auth.node_token({'username': 'luna', 'password': 'wrong'}, 'node001')
    assert status is False
    assert 'Incorrect password' in response['message']
    assert chain_calls == []


def test_the_configuration_file_account_gets_a_provision_token(db, node_and_cluster, chain_calls, auth):
    status, response = auth.node_token({'username': 'luna', 'password': 'luna'}, 'node001')
    assert status is True
    claims = decode(response['token'], 'test', algorithms=['HS256'])
    assert claims['node'] == 'node001' and claims['scope'] == 'provision'
    assert chain_calls == []


def test_the_route_answers_a_person_with_401(sqlite_db, chain_calls, monkeypatch):
    import common.constant as constant
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    body = {'tpm_sha256': 'a' * 64, 'username': 'someone', 'password': 'theirs'}
    response = routes_app().test_client().post('/tpm/node001', data=json.dumps(body),
                                               content_type='application/json')
    assert response.status_code == 401, response.data
    assert json.loads(response.data)['message'].endswith('is not the configuration-file account')
    assert chain_calls == []
