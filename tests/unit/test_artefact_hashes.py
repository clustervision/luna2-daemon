#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The local artefact checksums, and the download that produces them.

Two properties are being pinned here, and they are not the same one.

The first is that a failed download publishes nothing. That is the defect this
work exists for: a pull that ran out of disk left a truncated file under the
served name and the controller went on serving it, so a node fetched a corrupt
image. What made it dangerous was not the failure - the failure was reported
correctly - but what the filesystem was left holding afterwards.

The second is that the hash store can never take the daemon down with it. One
caller is build_osimage, where a database hiccup must not turn a good image
build into a failure; the other is pull_image_files, which runs on the journal
path, where raising holds replication for every record behind it. A checksum is
optional metadata in both places, so every entry point returns rather than
raises, and 'no hash' means 'not verifiable' rather than 'error'.
"""

import os

import pytest

from utils.database import Database
from utils.dbstructure import DBStructure
from utils.hashes import Hashes


@pytest.fixture
def db(tmp_path):
    """A throwaway database carrying just the hash table."""
    import common.constant as constant
    from utils import database

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'hashes.db')
    database.local_thread.connection = None
    Database().create('hash', DBStructure().get_database_table_structure('hash'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def artefact(tmp_path):
    """A file standing in for a packed image."""
    path = tmp_path / 'compute-1234.tar.bz2'
    path.write_bytes(b'not really an image, but it has bytes' * 100)
    return str(path)


# ---------------------------------------------------------------- the table is registered

def test_hash_table_is_registered_everywhere_it_needs_to_be():
    """
    Adding a table means three lists, not one. The layout alone is not enough:
    DBStructure walks a hardcoded name list to decide what to create, and a
    separate if-chain maps the name to its layout. Miss the third and creation
    fails with a layout of None - which is how this was found.
    """
    structure = DBStructure()
    assert 'hash' in structure.tables, "the table is never created if it is not in DBStructure().tables"
    layout = structure.get_database_table_structure('hash')
    assert layout, "get_database_table_structure has no branch for 'hash', so creating it fails"
    columns = {entry['column'] for entry in layout}
    assert {'object', 'name', 'file', 'hashtype', 'hash', 'created'} <= columns


def test_hash_table_is_not_replicated_or_backed_up():
    """
    A row describes a file on THIS controller, so it legitimately differs between
    controllers - which is the entire point, since it is what lets a peer tell
    'my copy matches yours' from 'my copy is broken'. Hashing it for controller
    comparison would make two healthy controllers look permanently out of sync.
    """
    from utils.tables import Tables
    assert 'hash' not in Tables().tables


# ---------------------------------------------------------------- recording and lookup

def test_record_then_lookup_round_trips(db, artefact):
    recorded = Hashes().record('osimage', 'compute', os.path.basename(artefact), path=artefact)
    assert recorded
    assert Hashes().lookup('osimage', 'compute', os.path.basename(artefact)) == recorded


def test_recording_twice_updates_rather_than_duplicates(db, artefact):
    name = os.path.basename(artefact)
    Hashes().record('osimage', 'compute', name, path=artefact)
    Hashes().record('osimage', 'compute', name, path=artefact)
    rows = Database().get_record(table='hash', where=f"file='{name}'")
    assert len(rows) == 1, "a second recording must update the row, not add another"


def test_a_supplied_hash_is_used_without_reading_the_file(db):
    """
    The pull path already has the digest - the bytes went through it on the way in -
    so it hands the value over rather than reading gigabytes back off disk.
    """
    assert Hashes().record('osimage', 'compute', 'never-existed.tar.bz2',
                           hash_value='a' * 64) == 'a' * 64


# ---------------------------------------------------------------- it must never raise

def test_recording_without_a_path_or_a_value_returns_none(db):
    assert Hashes().record('osimage', 'compute', 'nothing-to-go-on') is None


def test_recording_a_missing_file_returns_none_rather_than_raising(db):
    """A vanished artefact is a normal race, not an error to propagate."""
    assert Hashes().record('osimage', 'compute', 'gone.tar.bz2',
                           path='/nonexistent/gone.tar.bz2') is None


def test_the_store_survives_its_table_disappearing(db, artefact):
    """
    record() runs on the journal path. If it raises there, replication stops for
    every record behind it - so a broken table has to degrade to 'no hash', not
    to an exception.
    """
    Database().delete_row('hash', [{"column": "object", "value": 'osimage'}])
    Database().get_record(table='hash')
    import utils.hashes as hashes_module
    original = hashes_module.Database
    class Exploding:
        def __getattr__(self, item):
            raise RuntimeError('database is having a bad day')
    hashes_module.Database = lambda: Exploding()
    try:
        assert Hashes().record('osimage', 'compute', 'x', hash_value='b' * 64) is None
        assert Hashes().lookup('osimage', 'compute', 'x') is None
        Hashes().forget_file('x')
    finally:
        hashes_module.Database = original


# ---------------------------------------------------------------- the row follows the file

def test_forget_file_removes_the_row(db, artefact):
    name = os.path.basename(artefact)
    Hashes().record('osimage', 'compute', name, path=artefact)
    Hashes().forget_file(name)
    assert Hashes().lookup('osimage', 'compute', name) is None


def test_forgetting_an_unknown_file_is_a_no_op(db):
    Hashes().forget_file('never-heard-of-it.tar.bz2')


def test_there_is_no_sweep_over_this_table():
    """
    A sweep decides what to delete from what is on disk at that moment, and an
    empty listing is indistinguishable from every artefact having been removed.
    A path that is unmounted, misconfigured or briefly unreadable would take the
    whole table with it - silently, because a missing row reads as 'not
    verifiable', which is a legitimate state. Downloads would quietly stop being
    verified, which is the defect this work exists to remove.

    These rows are long-lived: an image can sit unchanged for years. A stale one
    is inert - lookups are by object, name and file, and artefact names carry a
    timestamp, so a name never recurs and the row is never consulted again.
    Accumulating harmless bytes beats being able to delete good rows.

    forget_file is the whole cleanup story, and it is precise.
    """
    import inspect
    from utils.hashes import Hashes
    from utils.osimage import OsImage
    from utils.housekeeper import Housekeeper

    assert not hasattr(Hashes, 'prune'), \
        "no sweep over this table: an empty listing would delete every row"
    for owner, method in ((OsImage, 'cleanup_file'), (Housekeeper, 'cleanup_mother')):
        source = inspect.getsource(getattr(owner, method))
        assert 'prune' not in source, f"{owner.__name__}.{method} must not sweep the hash table"


def test_cleanup_is_targeted_at_the_file_being_removed(db, artefact):
    """
    The row goes when its file goes, and only that row. cleanup_file is the right
    hook because every artefact removal - image delete, tag delete, a repack
    superseding the previous generation - already passes through it, and its
    existing guards refuse while anything still refers to the file.
    """
    keep = 'compute-other-generation.tar.bz2'
    Hashes().record('osimage', 'compute', os.path.basename(artefact), path=artefact)
    Hashes().record('osimage', 'compute', keep, hash_value='c' * 64)

    Hashes().forget_file(os.path.basename(artefact))

    assert Hashes().lookup('osimage', 'compute', os.path.basename(artefact)) is None
    assert Hashes().lookup('osimage', 'compute', keep) == 'c' * 64, \
        "removing one artefact must not disturb another's row"


# ---------------------------------------------------------------- the download contract

def test_download_file_still_returns_two_values():
    """
    An earlier draft returned the digest as a third element so the caller got it
    for free. Every existing caller unpacks two - 'status,_ = download_file(...)' -
    and would have raised ValueError. The signature may gain a defaulted keyword;
    the return may not gain a member.
    """
    import inspect
    from utils.request import Request
    signature = inspect.signature(Request.download_file)
    assert 'expected_sha256' in signature.parameters
    assert signature.parameters['expected_sha256'].default is None, \
        "verification must be opt-in: an artefact packed before hashing existed has none"
    source = inspect.getsource(Request.download_file)
    for returned in ('return True, ', 'return False, '):
        for line in [l.strip() for l in source.splitlines() if l.strip().startswith(returned)]:
            assert line.count(',') == 1, f"download_file returns more than two values: {line}"


def test_download_writes_to_a_temporary_that_is_unique_per_attempt():
    """
    Two pulls of the same file inside one daemon share a pid, so a temporary named
    only after the process makes them write to the same file and trip over each
    other. The name has to distinguish attempts, not processes.
    """
    import inspect
    from utils.request import Request
    source = inspect.getsource(Request.download_file)
    assert '.part-' in source, "the download must not be written straight to the served name"
    assert 'uuid4' in source, "the temporary name must be unique per attempt, not per process"
    assert 'os.replace' in source, "the temporary must be renamed into place atomically"
    assert 'with session.get(' in source, \
        "a streamed response must be closed on every path, including the early return"
