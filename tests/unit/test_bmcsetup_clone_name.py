#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: a bmcsetup clone needs the new name. Without it the clone used to insert a
second row under the source's own name and report success with a placeholder name.
"""

from base.bmcsetup import BMCSetup
from utils.database import Database
from utils.helper import Helper


def names():
    return sorted(row['name'] for row in Database().get_record(table='bmcsetup') or [])


def seed():
    Database().insert('bmcsetup', Helper().make_rows({'name': 'base', 'username': 'u', 'password': 'p'}))


def test_a_clone_without_a_new_name_is_refused_and_writes_nothing(sqlite_db):
    seed()
    status, message = BMCSetup().clone_bmcsetup('base', {'config': {'bmcsetup': {'base': {}}}})
    assert status is False and message.startswith('Invalid request'), message
    assert names() == ['base']


def test_a_clone_with_a_new_name_still_works(sqlite_db):
    seed()
    status, message = BMCSetup().clone_bmcsetup('base', {'config': {'bmcsetup': {'base': {'newbmcname': 'copy'}}}})
    assert status is True, message
    assert names() == ['base', 'copy']
