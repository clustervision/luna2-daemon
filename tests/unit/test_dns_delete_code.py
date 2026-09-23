#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: removing a dns entry answers what the removal did. The route answered 204
for any request the journal accepted, also for an entry that does not exist.
"""

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


class FakeService():
    def queue(self, service, action):
        return True


@pytest.fixture(name='delete')
def delete_fixture(sqlite_db, monkeypatch):
    from common.constant import CONSTANT
    monkeypatch.setattr('base.dns.Service', FakeService)
    networkid = Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Database().insert('dns', Helper().make_rows({'host': 'web', 'ipaddress': '10.141.1.1', 'networkid': networkid}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    return lambda network, host: client.get(f'/config/dns/{network}/{host}/_delete',
                                            headers={'x-access-tokens': token}).status_code


def test_an_existing_entry_is_removed_with_204(delete):
    assert delete('cluster', 'web') == 204
    assert not Database().get_record(table='dns')


@pytest.mark.parametrize('network,host', [('cluster', 'nosuchhost'), ('nosuchnet', 'web')])
def test_a_missing_entry_or_network_is_a_404(delete, network, host):
    assert delete(network, host) == 404
    assert len(Database().get_record(table='dns')) == 1
