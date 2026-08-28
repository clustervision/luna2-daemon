#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a group clone resolves every named reference a group update does.

update_group and clone_group each translated the names a group points at -- its
bmcsetup, its redfishsetup, its osimage -- into the ids the columns hold, from a
copy each. The copies drifted on osimage: the update refused a name that does not
resolve, while the clone deleted the key, wrote a null id and reported success.

A null osimageid is not a loud failure. The group exists, the command said it
worked, and the group has no image. These tests are derived from the one list so
a reference added later cannot go missing from either path.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables a group clone touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'node', 'cluster', 'osimage', 'osimagetag', 'bmcsetup',
                  'redfishsetup', 'network', 'groupinterface', 'ipaddress', 'monitor',
                  'queue', 'route', 'routemap', 'groupsecrets', 'switch', 'cloud']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    from utils.helper import Helper
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


# Seeded by table name rather than from the list under test, so the fixture still
# stands up on code that does not have that list.
REFERENCED = ['osimage', 'bmcsetup', 'redfishsetup']


@pytest.fixture
def seed(db):
    """One record in every referenced table, and a group to clone from."""
    from utils.helper import Helper

    ids = {table: db.insert(table, Helper().make_rows({'name': f'the{table}'}))
           for table in REFERENCED}
    db.insert('group', Helper().make_rows({'name': 'src', 'osimageid': ids['osimage']}))
    return ids


def clone(newname, **supplied):
    """Clone through the real path; returns (status, response)."""
    from base.group import Group
    record = dict(supplied)
    record['newgroupname'] = newname
    return Group().clone_group(name='src', request_data={'config': {'group': {'src': record}}})


def test_a_clone_refuses_an_osimage_that_does_not_exist(db, seed):
    """
    The one that had drifted. On the unfixed code this reports success and leaves a
    group behind whose osimageid is null, which is why it is named explicitly here.
    """
    status, response = clone('cloned', osimage='nosuchimage')
    assert status is False, f'clone naming a nonexistent osimage was accepted: {response}'
    assert 'does not exist' in str(response)
    assert not db.get_record(table='group', where='name = "cloned"'), \
        'a refused clone left a group behind'


def test_a_clone_refuses_every_reference_that_does_not_resolve(db, seed):
    """The class: enumerated from the list, so a reference added later is covered."""
    from base.group import NAME_REFERENCES

    for index, (key, (table, _label, _required)) in enumerate(NAME_REFERENCES.items()):
        name = f'bad{index:03d}'
        status, response = clone(name, **{key: 'nosuchthing'})
        assert status is False, f'clone naming a nonexistent {key} was accepted: {response}'
        assert not db.get_record(table='group', where=f'name = "{name}"')


def test_a_clone_resolves_every_reference_that_does(db, seed):
    """The other half: refusing everything would also pass the test above."""
    from base.group import NAME_REFERENCES

    for index, (key, (table, _label, _required)) in enumerate(NAME_REFERENCES.items()):
        name = f'good{index:03d}'
        status, response = clone(name, **{key: f'the{table}'})
        assert status is True, f'clone naming a valid {key} was refused: {response}'
        row = db.get_record(table='group', where=f'name = "{name}"')
        assert str(row[0][table + 'id']) == str(seed[table]), \
            f'clone did not resolve {key} to its id'


def test_an_optional_reference_can_still_be_cleared(db, seed):
    """
    Not every reference behaves the same, and the shared resolver must not flatten
    them: redfishsetup may be set to nothing, bmcsetup and osimage may not.
    """
    from base.group import Group, NAME_REFERENCES

    status, response = Group().update_group(
        name='src', request_data={'config': {'group': {'src': {'redfishsetupname': ''}}}})
    assert status is True, f'clearing an optional reference was refused: {response}'
    assert db.get_record(table='group', where='name = "src"')[0]['redfishsetupid'] == ''
    assert NAME_REFERENCES['redfishsetupname'][2] is False
    assert NAME_REFERENCES['bmcsetupname'][2] is True
