#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: a dns change that applies no entry at all is refused, instead of answering
that entries were added or changed and queueing a reload for nothing.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


RELOADS = []


class FakeService():
    """Records the reload a change asks for; the real one needs the rendered daemon config."""
    def queue(self, service, action):
        RELOADS.append((service, action))


@pytest.fixture(name='post')
def post_fixture(sqlite_db, monkeypatch):
    from common.constant import CONSTANT
    RELOADS.clear()
    monkeypatch.setattr('base.dns.Service', FakeService)
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(entries):
        response = client.post('/config/dns/cluster', headers={'x-access-tokens': token},
                               data=json.dumps({'config': {'dns': {'cluster': entries}}}), content_type='application/json')
        return response.status_code, json.loads(response.data or b'{}').get('message', '')
    return post


def dns_rows():
    return [(row['host'], row['ipaddress']) for row in Database().get_record(table='dns') or []]


def reloads():
    return list(RELOADS)


def test_a_valid_entry_is_stored_and_reloads(post):
    code, message = post([{'host': 'web', 'ipaddress': '10.141.1.1'}])
    assert code == 201, message
    assert dns_rows() == [('web', '10.141.1.1')] and reloads() == [('dns', 'reload')]


@pytest.mark.parametrize('entries', [[], [{'host': 'web'}], [{'host': 'web', 'ipaddress': 'not-an-ip'}], ['host ipaddress']],
                         ids=['empty list', 'no ipaddress', 'invalid ipaddress', 'text entry'])
def test_nothing_applied_is_refused_and_does_not_reload(post, entries):
    code, message = post(entries)
    assert code == 400, (code, message)
    assert dns_rows() == [] and not reloads()
