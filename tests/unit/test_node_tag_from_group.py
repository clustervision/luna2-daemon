#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: a node that takes its osimage from its group is given a tag of that osimage.

Assigning a tag to a node never creates one: the tag has to exist on the node's osimage.
For a node without an osimage of its own that is the group's, but update_node tested
whether the node record had an osimageid key rather than a value, looked for the tag on
osimage 'None', and refused every tag.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables a node update touches."""
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


@pytest.fixture
def seed(db):
    """Two osimages with a tag each, a group on the first, and a node that inherits it."""
    from utils.helper import Helper

    ids = {}
    ids['image'] = db.insert('osimage', Helper().make_rows({'name': 'ubuntu'}))
    ids['other'] = db.insert('osimage', Helper().make_rows({'name': 'rocky'}))
    ids['tag'] = db.insert('osimagetag', Helper().make_rows(
        {'name': 'ubuntu:22.04', 'osimageid': ids['image']}))
    ids['othertag'] = db.insert('osimagetag', Helper().make_rows(
        {'name': 'rocky:9', 'osimageid': ids['other']}))
    ids['group'] = db.insert('group', Helper().make_rows(
        {'name': 'compute', 'osimageid': ids['image']}))
    db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': ids['group']}))
    return ids


def tag(name, tagname):
    """Change a node's tag through the real update path; returns (status, response)."""
    from base.node import Node
    return Node().update_node(name=name,
                              request_data={'config': {'node': {name: {'osimagetag': tagname}}}})


def test_a_node_takes_a_tag_of_its_groups_osimage(db, seed):
    status, response = tag('node001', 'ubuntu:22.04')
    assert status is True, f'the tag of the group osimage was refused: {response}'
    row = db.get_record(table='node', where='name = "node001"')[0]
    assert str(row['osimagetagid']) == str(seed['tag'])
    assert not row['osimageid'], 'the node keeps taking its osimage from its group'


def test_an_unknown_tag_is_still_refused(db, seed):
    status, response = tag('node001', 'ubuntu:24.04')
    assert status is False
    assert 'Unknown tag' in str(response)


def test_a_tag_of_another_osimage_is_still_refused(db, seed):
    status, response = tag('node001', 'rocky:9')
    assert status is False
    assert 'Unknown tag' in str(response)
