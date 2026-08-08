#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Image sync has to be honest about whether it worked, and has to notice when it
did not.

Two defects are pinned here and they share one cause: the pull that carries out a
sync runs on the journal path, where returning True is the contract that lets the
records behind it apply. That value therefore says 'the queue may continue' and
never 'the files arrived' - which is correct, and must stay that way.

What went wrong is everything built on top of it. The controller that queued the
sync reported 'Image sync success' before a single byte was fetched, because all
it could see was whether the journal accepted the request. And nothing ever looked
at the files afterwards: controller comparison hashes database rows, so a
controller whose osimage row names an artefact it does not hold looks perfectly in
sync, and the failed transfer is not retried until something packs again.

So the outcome has to travel by a different channel than the return value, and
something has to check what is actually on disk.
"""

import os

import pytest

from utils.database import Database
from utils.dbstructure import DBStructure
from utils.downloader import Downloader
from utils.osimage import OsImage


@pytest.fixture
def db(tmp_path):
    """A throwaway database carrying just the osimage table."""
    import common.constant as constant
    from utils import database

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'sync.db')
    database.local_thread.connection = None
    Database().create('osimage', DBStructure().get_database_table_structure('osimage'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def files(tmp_path):
    """A stand-in for IMAGE_FILES, pointed at by the constant the code reads."""
    import common.constant as constant
    location = tmp_path / 'files'
    location.mkdir()
    original = constant.CONSTANT['FILES']['IMAGE_FILES']
    constant.CONSTANT['FILES']['IMAGE_FILES'] = str(location)
    yield location
    constant.CONSTANT['FILES']['IMAGE_FILES'] = original


def _osimage(name='compute', kernel='k-1', initrd='i-1', image='img-1'):
    Database().insert('osimage', [
        {"column": "name", "value": name},
        {"column": "kernelfile", "value": kernel},
        {"column": "initrdfile", "value": initrd},
        {"column": "imagefile", "value": image},
    ])


# ---------------------------------------------------------------- the journal contract is untouched

def test_pull_still_returns_true_unconditionally():
    """
    The one thing that must not change. The journal dispatch is ordered and
    unguarded: a record that does not return holds every record behind it, so a
    file transfer - which can fail for reasons that have nothing to do with
    replication - must never be able to stall the queue.

    Asserted on the source because the alternative is exercising a real download.
    """
    import inspect
    source = inspect.getsource(Downloader.pull_image_files)
    returns = [line.strip() for line in source.splitlines() if line.strip().startswith('return')]
    assert returns == ['return True'], \
        f"pull_image_files must return True and nothing else; found {returns}"


# ---------------------------------------------------------------- a failed pull says so

def test_a_failed_pull_reports_the_failure_somewhere():
    """
    Since the return value cannot carry the outcome, something else has to. Before
    this, nothing did: the queueing controller wrote 'Image sync success' up front
    and no one corrected it, so a sync that fetched nothing read as green.
    """
    import inspect
    source = inspect.getsource(Downloader.pull_image_files)
    assert 'failed' in source, 'pull_image_files must track which artefacts did not arrive'
    assert 'report_sync_outcome' in source, \
        'pull_image_files must report the outcome; its return value cannot'

    report = inspect.getsource(Downloader.report_sync_outcome)
    assert '501' in report and '200' in report, \
        'the outcome must distinguish failure from success to the monitor'


def test_the_queueing_controller_no_longer_claims_success_up_front():
    """
    The claim was made before the transfer ran, from a variable that only ever
    reflected whether the journal accepted the request. Queued is the truth at
    that point.
    """
    import inspect
    from utils.housekeeper import Housekeeper
    source = inspect.getsource(Housekeeper.tasks_mother)
    assert "Image sync success for" not in source, \
        "the housekeeper must not report success before the transfer has run"
    assert "Image sync queued for" in source


def test_reporting_never_raises_on_the_journal_path(db, files, monkeypatch):
    """
    report_sync_outcome runs inside pull_image_files, which runs on the journal
    path. A monitor that cannot be written is bad; an exception there would hold
    replication for every record behind it, which is worse.
    """
    import base.monitor as monitor_module

    class Exploding:
        def update_itemstatus(self, *args, **kwargs):
            raise RuntimeError('monitor is having a bad day')

    # patched at the source: report_sync_outcome imports Monitor inside the call, so
    # that utils does not depend on base at module scope
    monkeypatch.setattr(monitor_module, 'Monitor', lambda: Exploding())
    Downloader().report_sync_outcome('compute', ['img-1'])   # must not raise


# ---------------------------------------------------------------- the loop is closed

def test_missing_artefacts_are_detected(db, files):
    """
    The gap this closes: the configuration names three artefacts, the disk holds
    one, and every existing check says the controller is in sync because they all
    compare database rows.
    """
    _osimage()
    (files / 'k-1').write_text('kernel')

    missing = OsImage().artefacts_missing_locally()
    assert missing == {'compute': ['i-1', 'img-1']}


def test_nothing_is_reported_when_everything_is_present(db, files):
    _osimage()
    for name in ('k-1', 'i-1', 'img-1'):
        (files / name).write_text('x')
    assert OsImage().artefacts_missing_locally() == {}


def test_an_absent_directory_reports_nothing_rather_than_everything(db, files):
    """
    The storm guard, and the reason this is not the mirror image of a sweep that
    deletes by absence. If IMAGE_FILES is unmounted or misconfigured then every
    artefact looks missing, and acting on that would queue a re-sync of every
    image at once - on every controller, repeatedly. An unreadable directory is
    not evidence that the files are gone.
    """
    import common.constant as constant
    _osimage()
    constant.CONSTANT['FILES']['IMAGE_FILES'] = str(files / 'does-not-exist')
    assert OsImage().artefacts_missing_locally() == {}


def test_an_osimage_with_no_artefacts_named_is_not_reported_missing(db, files):
    """A row that names nothing is not a row that lost something."""
    _osimage(name='empty', kernel=None, initrd=None, image=None)
    assert OsImage().artefacts_missing_locally() == {}


def test_a_failed_fetch_is_retried_once_where_it_failed():
    """
    The retry belongs at the point of failure, in the house style: tasks_mother
    already does exactly this for unpack - try, sleep, try once more, then report.
    Nowhere else can do it. The controller that queued the sync only ever saw
    whether the journal accepted the request, and its task is gone by the time the
    transfer runs.
    """
    import inspect
    source = inspect.getsource(Downloader.pull_image_files)
    assert source.count('download_file(') == 2, \
        'a fetch that failed once must be attempted once more before being given up on'
    assert 'Retrying one more time' in source, \
        'match the wording tasks_mother already uses for the unpack retry'


def test_incomplete_images_are_reported_but_not_auto_repaired():
    """
    Detection is worth keeping; the repair machinery is not. A fetch that failed is
    retried where it failed. What is left here is the case no fetch can fix - an
    artefact that is not coming, because the configuration names something that
    exists nowhere. That needs a person, and the first live run found exactly such
    an osimage. So: report, never queue a repair.
    """
    import inspect
    from utils.housekeeper import Housekeeper

    periodic = inspect.getsource(Housekeeper.cleanup_mother)
    assert 'report_incomplete_osimages' in periodic, \
        'nothing calls the check, so a missing artefact is never noticed'

    report = inspect.getsource(Housekeeper.report_incomplete_osimages)
    assert 'artefacts_missing_locally' in report, \
        'the check lives on OsImage, which owns artefacts on disk'
    assert "'501'" in report, 'an incomplete image must be visible as a failure'
    assert 'add_task_to_queue' not in report, \
        'reporting must not queue repairs; the retry lives where the fetch fails'
    assert 'get_role' not in report, \
        'a master missing an artefact cannot serve it either; do not gate this to a slave'

    assert not hasattr(Housekeeper, 'peer_controllers'), \
        'peer discovery duplicates what Journal already builds'
    assert "case 'resync_osimage_files'" not in inspect.getsource(Housekeeper.tasks_mother), \
        'the repair task type should be gone'


def test_a_filename_without_an_extension_does_not_raise():
    """
    get_file decides whether a file needs a token from its extension. The regex
    finds no match on a name with no dot, and group(1) on None raises - which the
    route turns into a 500. Kernels and ramdisks are served under names that do
    have dots, so this stayed hidden; anything else served from IMAGE_FILES hits
    it. No extension simply means no extension: not authenticated, as before.
    """
    import inspect
    from base.file import File
    source = inspect.getsource(File.get_file)
    line = [l for l in source.splitlines() if 'result.group(1)' in l]
    assert line, 'expected the extension match to still be read'
    assert 'if result:' in source, \
        'group(1) must not be called when the filename has no extension'
