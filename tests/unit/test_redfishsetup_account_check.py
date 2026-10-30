#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2332: a redfishsetup request that is refused writes nothing. Every account is
checked before the setup or any account is written, so a 400 leaves the database as it was.
"""

import json

from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


def post(name=None, body=None):
    from common.constant import CONSTANT
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    return routes_app().test_client().post(
        f'/config/redfishsetup/{name}', headers={'x-access-tokens': token},
        content_type='application/json',
        data=json.dumps({'config': {'redfishsetup': {name: body}}}))


def names(table=None):
    return sorted(row['name'] for row in Database().get_record(table=table) or [])


def existing_setup():
    Database().insert('redfishsetup', Helper().make_rows({'id': 1, 'name': 'rf-a', 'scheme': 'https'}))
    Database().insert('redfishaccount', Helper().make_rows({
        'redfishsetupid': 1, 'name': 'admin', 'username': 'rfadmin',
        'password': 'rfpw', 'role': 'Administrator'}))


def test_a_new_setup_with_an_invalid_account_writes_nothing(sqlite_db):
    response = post('rf-new', {'scheme': 'https', 'accounts': [{'name': 'ops', 'username': 'op'}]})
    assert response.status_code == 400, response.data
    assert b'password is required' in response.data
    assert names('redfishsetup') == []
    assert names('redfishaccount') == []


def test_a_valid_account_before_an_invalid_one_is_not_written(sqlite_db):
    existing_setup()
    response = post('rf-a', {'accounts': [
        {'name': 'ops', 'username': 'op', 'password': 'oppw', 'role': 'Operator'},
        {'name': 'ro', 'username': 'ro'}]})
    assert response.status_code == 400, response.data
    assert b'password is required' in response.data
    assert names('redfishaccount') == ['admin']


def test_a_valid_request_creates_the_setup_and_its_accounts(sqlite_db):
    response = post('rf-new', {'accounts': [
        {'name': 'ops', 'username': 'op', 'password': 'oppw', 'role': 'Operator'},
        {'name': 'ro', 'username': 'ro', 'password': 'ropw', 'role': 'ReadOnly'}]})
    assert response.status_code == 201, response.data
    setup = Database().get_record(table='redfishsetup', where="name = 'rf-new'")
    assert setup and setup[0]['scheme'] == 'https'
    accounts = Database().get_record(table='redfishaccount',
                                     where=f"redfishsetupid = '{setup[0]['id']}'")
    assert sorted((row['name'], row['username'], row['role']) for row in accounts) == [
        ('ops', 'op', 'Operator'), ('ro', 'ro', 'ReadOnly')]


def test_changing_an_existing_account_needs_no_password(sqlite_db):
    existing_setup()
    response = post('rf-a', {'accounts': [{'name': 'admin', 'role': 'Operator'}]})
    assert response.status_code == 204, response.data
    account = Database().get_record(table='redfishaccount', where="name = 'admin'")[0]
    assert (account['role'], account['password']) == ('Operator', 'rfpw')


def test_an_account_created_earlier_in_the_request_can_be_changed_later_in_it(sqlite_db):
    existing_setup()
    response = post('rf-a', {'accounts': [
        {'name': 'ops', 'username': 'op', 'password': 'oppw', 'role': 'Operator'},
        {'name': 'ops', 'role': 'ReadOnly'}]})
    assert response.status_code == 204, response.data
    account = Database().get_record(table='redfishaccount', where="name = 'ops'")[0]
    assert (account['username'], account['role']) == ('op', 'ReadOnly')
