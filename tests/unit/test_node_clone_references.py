#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a node clone resolves every named reference a node update does.

update_node and clone_node each translate the named things a node points at -- its
group, its osimage, its bmcsetup, its redfishsetup -- into the id the column holds.
They did so from two separate lists, and the clone's list stopped being updated: a
clone naming a cloud or a redfishsetup left the bare name in the payload, where the
column comparison rejected it and refused the whole clone.

The list is now one list, and these tests are derived from it, so a reference added
later is covered without anybody remembering to come back here.
"""

import inspect

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables a node clone touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['node', 'group', 'osimage', 'osimagetag', 'bmcsetup', 'redfishsetup',
                  'biosconfig', 'cloud', 'switch', 'nodeinterface', 'ipaddress', 'network', 'monitor',
                  'queue', 'route', 'routemap', 'nodesecrets', 'groupsecrets']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


# Seeded from the schema rather than from the list under test, so the fixture still
# stands up on code that does not have that list.
REFERENCED = ['group', 'osimage', 'bmcsetup', 'redfishsetup', 'biosconfig', 'cloud', 'switch']


@pytest.fixture
def seed(db):
    """One record in every referenced table, and a node in the group."""
    from utils.helper import Helper

    ids = {}
    for table in REFERENCED:
        ids[table] = db.insert(table, Helper().make_rows({'name': f'the{table}'}))
    ids['node'] = db.insert('node', Helper().make_rows(
        {'name': 'node001', 'groupid': ids['group']}))
    return ids


def clone(name, newname, **supplied):
    """Clone through the real path; returns (status, response)."""
    from base.node import Node
    record = dict(supplied)
    record['newnodename'] = newname
    return Node().clone_node(name=name, request_data={'config': {'node': {name: record}}})


def test_a_clone_resolves_a_redfishsetup_and_a_cloud(db, seed):
    """
    The two that had drifted. Named explicitly, because this is the regression: on
    the unfixed code the bare name survives into the column comparison and the whole
    clone is refused as 'Columns are incorrect'.
    """
    for index, reference in enumerate(['redfishsetup', 'cloud']):
        newname = f'drift{index:03d}'
        status, response = clone('node001', newname, **{reference: f'the{reference}'})
        assert status is True, f'clone naming a {reference} was refused: {response}'
        row = db.get_record(table='node', where=f'name = "{newname}"')
        assert str(row[0][reference + 'id']) == str(seed[reference])


def test_a_clone_resolves_every_named_reference(db, seed):
    """
    The class, not the instance: enumerated from the shared list, so a reference
    added later is covered here without anybody remembering to come back.
    """
    from base.node import NAME_REFERENCES

    for index, reference in enumerate(NAME_REFERENCES):
        newname = f'clone{index:03d}'
        status, response = clone('node001', newname, **{reference: f'the{reference}'})
        assert status is True, f'clone naming a {reference} was refused: {response}'
        row = db.get_record(table='node', where=f'name = "{newname}"')
        assert row, f'clone naming a {reference} created no node'
        assert str(row[0][reference + 'id']) == str(seed[reference]), \
            f'clone did not resolve {reference} to its id'


def test_an_unknown_reference_is_still_refused(db, seed):
    """Resolving more names must not mean accepting names that resolve to nothing."""
    status, response = clone('node001', 'clone900', redfishsetup='nosuchsetup')
    assert status is False
    assert 'not known or valid' in str(response)


def test_update_and_clone_read_the_same_list(db):
    """
    The structural half: both paths must use the shared list. Re-inlining a literal
    is how the two drifted apart in the first place, and it reads as tidy local code.
    """
    from base.node import Node

    for method in (Node.update_node, Node.clone_node):
        source = inspect.getsource(method)
        assert 'NAME_REFERENCES.items()' in source, \
            f'{method.__name__} no longer reads the shared reference list'
        assert 'checks = {' not in source, \
            f'{method.__name__} carries its own copy of the reference list again'
