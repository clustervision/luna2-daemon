#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: insert and update quote every value they write, whatever its type.

The quote handling applied to strings only, and a list or dict was turned into text
after it, bringing quotes of its own into the statement: the write failed, or reached
rows it was not meant to.
"""

from utils.database import Database
from utils.helper import Helper


def comments():
    return {row['name']: row['comment'] for row in Database().get_record(table='group') or []}


def seed():
    for name in ('one', 'two', 'three'):
        Database().insert('group', Helper().make_rows({'name': name}))


def test_an_update_with_a_list_value_changes_only_its_own_row(sqlite_db):
    seed()
    target = Database().get_record(table='group', where="name = 'two'")[0]['id']
    assert Database().update('group', Helper().make_rows({'comment': ["it's"]}),
                             [{'column': 'id', 'value': target}]) is True
    assert comments() == {'one': None, 'two': '["it"s"]', 'three': None}


def test_an_insert_with_a_list_value_is_stored_as_text(sqlite_db):
    assert Database().insert('group', Helper().make_rows({'name': 'four', 'comment': ["it's"]}))
    assert comments() == {'four': '["it"s"]'}


def test_a_string_keeps_the_quote_handling_it_always_had(sqlite_db):
    seed()
    target = Database().get_record(table='group', where="name = 'one'")[0]['id']
    assert Database().update('group', Helper().make_rows({'comment': "it's"}),
                             [{'column': 'id', 'value': target}]) is True
    assert comments()['one'] == 'it"s'
