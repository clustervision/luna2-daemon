#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
# GPL-3.0-or-later

"""
One entry at a time: adding, replacing and removing a mount by its path on the
cluster, a group and a node, and assigning a profile beside the ones a node or
group has. A group or node without a document of its own starts from what it
resolves to, so an add never hides the cluster's shares by accident.
"""

import json
from base64 import b64decode, b64encode
from unittest.mock import patch

import pytest

from utils import mounts
from test_mounts import CORPUS, db  # noqa: F401 - db is a fixture
from test_profiles import _make as _make_profile


def _doc(value):
    return json.loads(b64decode(value).decode())


def _paths(value):
    return [m['path'] for m in _doc(value)['mounts']]


ARCHIVE = {'path': '/trinity/archive2', 'server': 'controller', 'source': '/srv/archive2',
           'export': {'clients': [{'to': 'cluster', 'options': 'ro'}]}, 'options': 'ro,_netdev,nofail'}


# --- the pure operations ---------------------------------------------------------------

def test_upsert_adds_then_updates_in_place_and_remove_reports_whether_it_found_one():
    value = mounts.upsert_entry('', {'path': '/a', 'server': 'controller', 'export': {'clients': [{'to': '*'}]}})
    value = mounts.upsert_entry(value, {'path': '/b'})
    assert _paths(value) == ['/a', '/b']
    # the fields given update the entry at its path; the export it already had stays
    value = mounts.upsert_entry(value, {'path': '/a', 'server': 'nas', 'options': 'ro'})
    assert _paths(value) == ['/a', '/b']
    assert _doc(value)['mounts'][0] == {'path': '/a', 'server': 'nas', 'options': 'ro', 'export': {'clients': [{'to': '*'}]}}
    value, found = mounts.remove_entry(value, '/nope')
    assert found is False
    value, found = mounts.remove_entry(value, '/a')
    assert found is True and _paths(value) == ['/b']
    with pytest.raises(mounts.MountsInvalid):
        mounts.upsert_entry(value, {'server': 'controller'})


# --- the three levels, against a real schema ---------------------------------------------

def _stored(table, name=None):
    from utils.database import Database
    where = f"name = '{name}'" if name else None
    return Database().get_record(table=table, where=where)[0].get('mounts') or ''


def _cluster_with_corpus():
    from base.cluster import Cluster
    with patch('base.cluster.Service'):
        assert Cluster().update_cluster({'config': {'cluster': {
            'mounts': b64encode(json.dumps(CORPUS).encode()).decode()}}})[0] is True


def test_cluster_add_replace_remove(db):
    from base.cluster import Cluster
    _cluster_with_corpus()
    with patch('base.cluster.Service') as service:
        status, message = Cluster().update_mount(ARCHIVE)
        assert status is True, message
        service.return_value.queue.assert_any_call('mounts', 'render')
    assert _paths(_stored('cluster'))[-1] == '/trinity/archive2'
    with patch('base.cluster.Service') as service:
        assert Cluster().update_mount(ARCHIVE) == (True, 'Mounts document unchanged.')
        service.return_value.queue.assert_not_called()
        assert Cluster().update_mount(dict(ARCHIVE, options='rw'))[0] is True
    assert _paths(_stored('cluster')).count('/trinity/archive2') == 1
    assert [m for m in _doc(_stored('cluster'))['mounts'] if m['path'] == '/trinity/archive2'][0]['options'] == 'rw'
    with patch('base.cluster.Service'):
        status, message = Cluster().remove_mount({'path': '/trinity/nope'})
        assert status is False and 'no mount at /trinity/nope' in message
        assert Cluster().remove_mount({'path': '/trinity/archive2'})[0] is True
    assert '/trinity/archive2' not in _paths(_stored('cluster'))


def test_cluster_add_still_validates_and_checks_clashes(db):
    from base.cluster import Cluster
    _cluster_with_corpus()
    with patch('base.cluster.Service'):
        status, message = Cluster().update_mount({'path': '/x', 'mode': 'rwx'})
    assert status is False and 'mode' in message


def test_node_add_copies_the_effective_document_down_first_and_says_so(db):
    from base.node import Node
    _cluster_with_corpus()
    with patch('base.node.Service'):
        assert Node().update_node('node001', {'config': {'node': {'node001': {'group': 'compute'}}}})[0] is True
    assert _stored('node', 'node001') == ''
    with patch('base.node.Service'):
        status, message = Node().update_mount('node001', ARCHIVE)
    assert status is True, message
    assert 'copied to node node001 first' in message and 'cluster mounts document' in message
    # every cluster entry survived, and the new one sits at the end
    assert _paths(_stored('node', 'node001')) == [m['path'] for m in CORPUS['mounts']] + ['/trinity/archive2']
    # a second add on the now-owned document copies nothing and says nothing about it
    with patch('base.node.Service'):
        status, message = Node().update_mount('node001', dict(ARCHIVE, options='rw'))
    assert status is True and 'copied' not in message
    with patch('base.node.Service'):
        assert Node().remove_mount('node001', {'path': '/trinity/home'})[0] is True
    assert '/trinity/home' not in _paths(_stored('node', 'node001'))


def test_group_add_copies_down_too_and_an_unknown_group_is_refused(db):
    from base.group import Group
    _cluster_with_corpus()
    with patch('base.group.Service'):
        status, message = Group().update_mount('compute', ARCHIVE)
    assert status is True and 'copied to group compute first' in message
    assert _paths(_stored('group', 'compute'))[-1] == '/trinity/archive2'
    assert Group().update_mount('nogroup', ARCHIVE) == (False, 'Group nogroup is not present in database')
    assert Group().remove_mount('compute', {}) == (False, 'Invalid request: a path is needed')


# --- profiles, one at a time -----------------------------------------------------------

def _profiles(name):
    from base.profile import Profile
    from utils.database import Database
    return Profile().profile_names(Database().get_record(table='node', where=f"name = '{name}'")[0].get('profiles'))


def test_assign_and_unassign_one_profile_beside_the_others(db):
    from base.node import Node
    from base.profile import Profile
    from utils.database import Database
    from utils.dbstructure import DBStructure
    for table in ['profile', 'profilefile', 'ownercache']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    for profile in ('alpha', 'beta'):
        assert Profile().update_profile(profile, _make_profile(profile))[0] is True
    with patch('base.node.Service'):
        assert Node().update_node('node001', {'config': {'node': {'node001': {'group': 'compute', 'profiles': 'alpha'}}}})[0] is True
        assert Node().assign_profile('node001', {'profile': 'beta'})[0] is True
    assert _profiles('node001') == ['alpha', 'beta']
    with patch('base.node.Service'):
        status, message = Node().assign_profile('node001', {'profile': 'beta'})
        assert status is True and 'already assigned' in message
        status, message = Node().assign_profile('node001', {'profile': 'gamma'})
        assert status is False and 'gamma' in message
        assert Node().unassign_profile('node001', {'profile': 'alpha'})[0] is True
        status, message = Node().unassign_profile('node001', {'profile': 'alpha'})
        assert status is False and 'not assigned' in message
    assert _profiles('node001') == ['beta']
