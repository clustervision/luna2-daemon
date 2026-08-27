#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Unit tests: the group listing and the single group read agree on _override.

Both endpoints answer the same question -- does this group hold something of its
own, rather than inherit it -- and they answered it from two separate lists. The
listing's list carried unmanaged_bmc_users and the single read's did not, so a
group whose only local value was that field was marked as deviating in
'luna group list' and reported as not deviating by 'luna group show', which
renders the flag as an info line.

The list is now one list, and these tests are derived from it.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables a group read touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'node', 'cluster', 'osimage', 'osimagetag', 'bmcsetup',
                  'network', 'groupinterface', 'ipaddress', 'monitor', 'queue',
                  'route', 'routemap', 'groupsecrets', 'switch', 'cloud']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    from utils.helper import Helper
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def override_pair(name):
    """Returns (_override as the listing reports it, as the single read reports it)."""
    from base.group import Group
    _, listing = Group().get_all_group()
    _, single = Group().get_group(name=name)
    return (listing['config']['group'][name].get('_override'),
            single['config']['group'][name].get('_override'))


def test_the_two_reads_agree_on_unmanaged_bmc_users(db):
    """
    The field that had drifted. Named explicitly, because this is the regression:
    on the unfixed code the listing says True and the single read says False for
    the same group, and 'group show' renders that flag as an info line.
    """
    from utils.helper import Helper

    db.insert('group', Helper().make_rows({'name': 'ownusers', 'unmanaged_bmc_users': 'alice'}))
    listed, shown = override_pair('ownusers')
    assert listed is True, 'a group holding its own unmanaged_bmc_users is not listed as deviating'
    assert shown == listed, \
        f'listing and single read disagree: list says {listed}, show says {shown}'


def test_both_reads_agree_on_every_overridable_field(db):
    """
    Enumerated from the list itself: a field added later is covered here without
    anybody remembering to come back, which is how the two drifted apart.
    """
    from base.group import OVERRIDABLE
    from utils.helper import Helper

    for index, field in enumerate(OVERRIDABLE):
        name = f'holds{index:03d}'
        db.insert('group', Helper().make_rows({'name': name, field: 'somevalue'}))
        listed, shown = override_pair(name)
        assert listed is True, f'a group holding its own {field} is not listed as deviating'
        assert shown == listed, \
            f'listing and single read disagree on a group holding {field}: {listed} vs {shown}'


def test_a_group_holding_nothing_of_its_own_deviates_in_neither_read(db):
    """The negative control: agreement must not come from answering True to everything."""
    from utils.helper import Helper

    db.insert('group', Helper().make_rows({'name': 'inherited'}))
    assert override_pair('inherited') == (False, False)
