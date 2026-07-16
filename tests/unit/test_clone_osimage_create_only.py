#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1937: the journal's param column is a string channel, and create_only forgot.

A replicated clone carries create_only in the journal's `param`. That column is a VARCHAR and
Database().insert builds its SQL with str(), so a Python True is stored as the text 'True' and
comes back as the text 'True'. clone_osimage then tested it with `is True`, which no string can
satisfy -- so the remote controller never honoured create_only and ran a full local clone
instead of the record-only create it was asked for. The direct call path passes a real bool and
worked, which is why it looked fine.

The tests pin the two halves separately: that param genuinely round-trips as text (so nobody
"fixes" the identity check back), and that clone_osimage reads it correctly regardless of
which side it came from -- text from a peer, or a bool from a direct call.
"""

import pytest

from utils.helper import Helper


@pytest.fixture
def db(tmp_path):
    """A throwaway database with the journal table, so the round-trip is the real one."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'journal.db')
    database.local_thread.connection = None
    Database().create('journal', DBStructure().get_database_table_structure('journal'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


# ------------------------------------------------- what the journal actually carries

def test_param_is_a_string_channel_not_a_bool_one(db):
    """The fact the fix rests on. param is a VARCHAR written with str()."""
    from utils.database import Database

    data = {'function': 'OSImage.clone_osimage', 'object': 'image1', 'param': True,
            'payload': None, 'masteronly': Helper().bool_to_string(False),
            'remoteonly': Helper().bool_to_string(True), 'misc': None,
            'sendby': 'controller1', 'sendto': 'controller2', 'created': 'NOW', 'tries': '0'}
    Database().insert('journal', Helper().make_rows(data))
    record = Database().get_record(table='journal')[0]

    assert record['param'] == 'True', f"param came back as {record['param']!r}"
    assert not isinstance(record['param'], bool), (
        "param round-tripped as a bool. If the column can now carry one, the make_bool in "
        "clone_osimage is harmless -- but check what else changed before trusting that."
    )
    assert record['param'] is not True, (
        "`param is True` -- the check clone_osimage used to make -- now passes. It did not "
        "before, which is the whole defect."
    )


def test_the_arity_guess_still_picks_the_three_argument_form(db):
    """A stored 'True' must stay non-None, or the journal would call the wrong signature."""
    from utils.database import Database

    data = {'function': 'OSImage.clone_osimage', 'object': 'image1', 'param': False,
            'payload': None, 'masteronly': Helper().bool_to_string(False),
            'remoteonly': Helper().bool_to_string(True), 'misc': None,
            'sendby': 'controller1', 'sendto': 'controller2', 'created': 'NOW', 'tries': '0'}
    Database().insert('journal', Helper().make_rows(data))
    record = Database().get_record(table='journal')[0]

    assert record['param'] is not None, (
        "param=False stored as NULL. The journal picks its call signature on `param is not None`, "
        "so this would silently dispatch clone_osimage(name, payload) instead."
    )


# ------------------------------------------------- what clone_osimage makes of it

@pytest.mark.parametrize('sent,expected', [
    (True, True),        # a direct call, or a peer once the value is normalised
    ('True', True),      # what a replicated True actually arrives as
    (False, False),
    ('False', False),
])
def test_create_only_reads_the_same_from_a_peer_as_from_a_direct_call(sent, expected):
    """The fix. Text from replication and a bool from a direct call must decide alike."""
    assert (Helper().make_bool(sent) is True) is expected, (
        f"create_only={sent!r} decided differently from create_only={expected!r}. The remote "
        f"controller then runs a full image clone instead of the record-only create."
    )


def test_a_replicated_create_only_clone_creates_the_record_and_stops(tmp_path):
    """Drive the real method with what replication actually delivers: the text 'True'.

    Deliberately no `queue` table. create_only means "make the record, take the image by
    sync" and must return before anything is queued -- so a test that reaches the queue has
    caught the bug, and cannot reach the ProcessPoolExecutor two lines further on that would
    run a real image clone.
    """
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from base.osimage import OSImage

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'osimage.db')
    database.local_thread.connection = None
    try:
        Database().create('osimage', DBStructure().get_database_table_structure('osimage'))
        Database().insert('osimage', Helper().make_rows({'name': 'image1'}))
        request_data = {'config': {'osimage': {'image1': {'newosimage': 'image2'}}}}

        status, response = OSImage().clone_osimage('image1', 'True', request_data)

        assert status is True, (
            f"a replicated create_only clone did not stop at the record: {response!r}. It fell "
            f"through to the queue, which on a real controller starts a full image clone -- the "
            f"exact fallback TRIX-1814 removed."
        )
        assert Database().get_record(table='osimage', where='name = "image2"'), (
            "create_only returned success without creating the record it exists to create"
        )
    finally:
        constant.CONSTANT['DATABASE']['DATABASE'] = original
        database.local_thread.connection = None


def test_a_payload_shaped_param_does_not_read_as_create_only():
    """An older peer sends no param, so its payload lands in the create_only slot.

    That is a real rolling-upgrade shape. It must not be mistaken for a request to create the
    record only -- falling through to the full clone is the older, safe behaviour.
    """
    payload = {'config': {'osimage': {'image1': {'newosimage': 'image2'}}}}
    assert Helper().make_bool(payload) is not True
