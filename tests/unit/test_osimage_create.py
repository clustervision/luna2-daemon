#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2355: the queued create stage of luna osimage create.

The create plugin is a replaceable file, so its answer is the only thing the worker can
act on. It says three things now, not two, and the third decides whether Luna packs the
image itself or leaves that to the builder that took the job. Packing an image that was
never built is silent corruption reported as success, so anything the worker does not
recognise reads as a hand-off instead.

Also pins that the operator's stream is never left without an ending: a build nobody
accepts fails in words, and a pack the dedup window swallowed says where its progress is.
"""

import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREATE_PLUGINS = os.path.join(HERE, 'daemon', 'plugins', 'osimage', 'operations', 'create')


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables this path touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'create.db')
    database.local_thread.connection = None
    for table in ['queue', 'status', 'osimage']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


class Recorder():
    """A logger that keeps what it was told, so a warning can be read without a log level."""

    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(str(message))

    def info(self, message):
        pass

    debug = info
    error = info


def _image(db, name='compute', **fields):
    """One osimage row with a path set, so no filesystem plugin is needed to find it."""
    from utils.helper import Helper
    row = {'name': name, 'path': f'/trinity/images/{name}', 'distribution': 'redhat',
           'osrelease': '9', 'architecture': 'x86'}
    row.update(fields)
    return db.insert('osimage', Helper().make_rows(row))


def _task(db, request_id='R1', param='compute', task='create_osimage', **fields):
    """The queue row the worker is handed, as create_image() writes it: noeof set."""
    from utils.helper import Helper
    row = {'subsystem': 'osimage', 'status': 'in progress', 'request_id': request_id,
           'task': task, 'param': param, 'noeof': 1, 'created': 'NOW'}
    row.update(fields)
    return db.insert('queue', Helper().make_rows(row))


def _worker(monkeypatch, returns):
    """
    An OsImage with just a logger and a stubbed plugin loader, so the real worker runs
    without a daemon configuration, against a create plugin that answers `returns`.
    """
    from utils.helper import Helper
    from utils.osimage import OsImage

    class Fake():
        calls = []

        def create(self, **kwargs):
            Fake.calls.append(kwargs)
            return returns

    monkeypatch.setattr(Helper, 'plugin_load', lambda self, *args, **kwargs: Fake)
    worker = OsImage.__new__(OsImage)
    worker.logger = Recorder()
    worker.osimage_plugins = {}
    worker.plugin = Fake
    return worker


def _messages(db, request_id):
    return [row['message'] for row in
            (db.get_record(table='status', where=f"request_id='{request_id}'") or [])]


# --------------------------------------------------------------- the widened return

def test_a_built_image_is_packed_by_luna(db, monkeypatch):
    """
    'built' means the content is on disk and nothing else will ever pack it, so the worker
    queues the pack chain itself - on the operator's own request_id, so the pack's output
    lands on the stream they are already reading.
    """
    _image(db)
    taskid = _task(db, request_id='Rbuilt')
    worker = _worker(monkeypatch, (True, 'content built', 'built'))

    assert worker.create_osimage(taskid, 'Rbuilt') is True
    packs = db.get_record(table='queue', where="task='pack_n_build_osimage'") or []
    assert len(packs) == 1, 'a built image must be packed by Luna, nobody else will'
    assert packs[0]['request_id'] == 'Rbuilt', 'the pack must run on the operator stream'
    assert packs[0]['param'] == 'compute'


def test_a_handed_off_build_is_not_packed_by_luna(db, monkeypatch):
    """
    'accepted' means the builder has the job and calls the pack route itself when it is
    done. Chaining here would tar an image that has not been built yet - and the pack
    succeeds, writes the EOF and reports success, so the operator is told it worked.
    """
    _image(db)
    taskid = _task(db, request_id='Racc')
    worker = _worker(monkeypatch, (True, 'the builder accepted the build', 'accepted'))

    assert worker.create_osimage(taskid, 'Racc') is True
    assert not db.get_record(table='queue', where="task='pack_n_build_osimage'"), \
        'an image that is still being built must not be packed'
    assert any('builder' in message for message in _messages(db, 'Racc')), \
        'the operator must be told what the stream is now waiting for'


def test_a_two_value_plugin_still_works(db, monkeypatch):
    """
    Sites keep their own copies of these files, so a plugin that predates build_state has
    to keep working: it is unpacked tolerantly and read as a hand-off, loudly.
    """
    _image(db)
    taskid = _task(db, request_id='Rold')
    worker = _worker(monkeypatch, (True, 'content built'))

    assert worker.create_osimage(taskid, 'Rold') is True, \
        'a two-value plugin must not raise in core'
    assert not db.get_record(table='queue', where="task='pack_n_build_osimage'"), \
        'an absent build_state falls to the safe side, which queues no pack'
    assert any('no build_state' in warning for warning in worker.logger.warnings), \
        'an unlogged fallback cannot be told from a bug'


def test_an_unknown_build_state_is_treated_as_a_hand_off(db, monkeypatch):
    """A typo in a site's file lands on the recoverable side, and says so."""
    _image(db)
    taskid = _task(db, request_id='Rtypo')
    worker = _worker(monkeypatch, (True, 'content built', 'build'))

    assert worker.create_osimage(taskid, 'Rtypo') is True
    assert not db.get_record(table='queue', where="task='pack_n_build_osimage'"), \
        "an unrecognised build_state must not be read as 'built'"
    assert any("'build'" in warning for warning in worker.logger.warnings)


def test_core_calls_the_plugin_by_keyword_with_what_the_record_holds(db, monkeypatch):
    """A keyword a site's copy does not accept is a TypeError, so the names are the contract."""
    _image(db, architecture='arm64')
    taskid = _task(db, request_id='Rkw')
    worker = _worker(monkeypatch, (True, 'accepted', 'accepted'))

    worker.create_osimage(taskid, 'Rkw')
    assert worker.plugin.calls, 'the plugin was never called at all'
    call = worker.plugin.calls[-1]
    assert call == {'name': 'compute', 'architecture': 'arm64', 'distribution': 'redhat',
                    'osrelease': '9', 'path': '/trinity/images/compute', 'request_id': 'Rkw'}


# ------------------------------------------------------------- endings of the stream

def test_a_refused_build_fails_rather_than_leaving_the_operator_polling(db, monkeypatch):
    """
    There is no timeout in the operator's poll, so a plugin that could not place the build
    must end as a failure - the mother writes the EOF on a False return.
    """
    _image(db)
    taskid = _task(db, request_id='Rno')
    worker = _worker(monkeypatch, (False, 'no builder took the build', 'accepted'))

    assert worker.create_osimage(taskid, 'Rno') is False
    rows = db.get_record(table='status', where="request_id='Rno'") or []
    assert any('no builder took the build' in row['message'] for row in rows)
    assert any(str(row['status']) == '500' for row in rows), \
        'a refusal must be a non-200 line, or the CLI exits 0 on it'


def test_a_deduped_pack_chain_says_where_it_went_and_ends_the_stream(db, monkeypatch):
    """
    The queue collapses an identical pack chain queued within fifteen minutes and hands back
    the first one's request_id - so this stream is never written to again. Without this the
    operator polls for ever on a pack that is running under another id.
    """
    _image(db)
    _task(db, request_id='Rother', task='pack_n_build_osimage')
    taskid = _task(db, request_id='Rdedup')
    worker = _worker(monkeypatch, (True, 'content built', 'built'))

    assert worker.create_osimage(taskid, 'Rdedup') is True
    messages = _messages(db, 'Rdedup')
    assert any('Rother' in message for message in messages), \
        'the operator must be told which stream carries the progress'
    assert 'EOF' in messages, 'a stream nothing will write to again must be ended'


def test_a_create_for_an_image_that_is_gone_ends_cleanly(db, monkeypatch):
    """
    Deleting an osimage does not remove a create queued against it, so the worker's first
    act is the record check: it reports the miss and returns, and the mother clears the row.
    """
    taskid = _task(db, request_id='Rgone')
    worker = _worker(monkeypatch, (True, 'content built', 'built'))

    assert worker.create_osimage(taskid, 'Rgone') is False
    rows = db.get_record(table='status', where="request_id='Rgone'") or []
    assert any('does not exist' in row['message'] for row in rows)
    assert any(str(row['status']) == '404' for row in rows)
    assert not db.get_record(table='queue', where="task='pack_n_build_osimage'"), \
        'nothing is packed for an image that is not there'


# ------------------------------------------------------------- the plugin contract

def test_every_create_plugin_meets_the_contract(monkeypatch):
    """
    Derived, so the next plugin in this directory is covered without anyone remembering this
    file: a plugin that reaches into base/ cannot be replaced safely, a keyword without a
    default is a TypeError in a site's copy, and an answer of another shape strands the
    worker that reads it.
    """
    import importlib
    import inspect
    import plugins.addons.trixd as addon
    from utils.helper import Helper

    monkeypatch.setattr(addon, 'submit', lambda path=None, payload=None: None)
    monkeypatch.setattr(Helper, 'runcommand', lambda self, *args, **kwargs: ([b''], 1))
    names = sorted(name for name in os.listdir(CREATE_PLUGINS)
                   if name.endswith('.py') and not name.startswith('__'))
    assert names, 'no create plugin in the tree at all'

    for name in names:
        source = open(os.path.join(CREATE_PLUGINS, name), encoding='utf-8').read()
        assert not re.search(r'^\s*(from|import)\s+base[\s.]', source, re.M), \
            f'{name} imports from base/, which a replaceable file must not depend on'
        module = importlib.import_module(f'plugins.osimage.operations.create.{name[:-3]}')
        monkeypatch.setattr(module, 'trixd_submit', lambda **kwargs: None, raising=False)
        plugin = module.Plugin()
        assert callable(getattr(plugin, 'create', None)), f'{name} has no create()'
        for parameter in inspect.signature(plugin.create).parameters.values():
            assert parameter.default is not inspect.Parameter.empty, \
                f'{name}: create() has no default for {parameter.name}'
        returned = plugin.create(name='compute', architecture='x86', distribution='redhat',
                                 osrelease='9', path='/trinity/images/compute',
                                 request_id='contract')
        assert isinstance(returned, tuple) and len(returned) in (2, 3), \
            f'{name}: create() must return (status, message) or (status, message, build_state)'
        assert returned[1], f'{name}: create() returned no message to show the operator'
        if len(returned) == 3:
            assert returned[2] in ('built', 'accepted'), \
                f'{name}: create() returned an unknown build_state {returned[2]}'


def test_the_default_plugin_refuses_in_words_when_no_builder_answers(monkeypatch):
    """
    trixd is what builds an image, and a controller may not have it. The refusal has to
    name what is missing: it is the only thing the operator will see.
    """
    import plugins.osimage.operations.create.default as plugin_module

    monkeypatch.setattr(plugin_module, 'trixd_submit', lambda **kwargs: None)
    status, message, build_state = plugin_module.Plugin().create(
        name='compute', architecture='x86', distribution='redhat', osrelease='9',
        path='/trinity/images/compute', request_id='R')

    assert status is False
    assert 'trix-daemon' in message and 'compute' in message
    assert build_state == 'accepted'


def test_the_default_plugin_hands_the_builder_the_record_and_the_stream(monkeypatch):
    """The image name is the only correlation key there is, and the stream id is Luna's."""
    import plugins.osimage.operations.create.default as plugin_module
    sent = {}

    def fake_submit(path=None, payload=None):
        sent.update(path=path, payload=payload)
        return {'accepted': True}

    monkeypatch.setattr(plugin_module, 'trixd_submit', fake_submit)
    status, _message, build_state = plugin_module.Plugin().create(
        name='compute', architecture='arm64', distribution='redhat', osrelease='9',
        path='/trinity/images/compute', request_id='R7')

    assert status is True
    assert build_state == 'accepted', 'our builder packs the image itself; Luna must not'
    assert sent['payload'] == {'image': 'compute', 'architecture': 'arm64',
                               'distribution': 'redhat', 'osrelease': '9',
                               'path': '/trinity/images/compute', 'request_id': 'R7'}


# ----------------------------------------------------------------------- the route

def test_the_route_answers_with_the_request_id_in_its_body(sqlite_db, monkeypatch):
    """
    The operator follows the build by the id in this body, and the HTTP code follows the
    wording of the message: one saying 'updated' answers 204, which carries no body and
    drops the id. Code and body are pinned together for that reason.
    """
    import json
    from jwt import encode
    from common.constant import CONSTANT
    import routes.config_osimage as route
    from cases.route_requirements_cases import app as routes_app

    monkeypatch.setattr(route.HA, 'get_hastate', lambda self: False)
    monkeypatch.setattr(route.OSImage, 'create_image', lambda self, name=None:
                        (True, f'osimage creation for {name} queued', 'rid-9'))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    answer = client.get('/config/osimage/img/_create', headers={'x-access-tokens': token})

    body = json.loads(answer.data)
    assert answer.status_code == 200, answer.data
    assert body.get('request_id') == 'rid-9', f'the body must carry the stream id: {body}'


def test_the_loader_resolves_the_create_plugin():
    """
    Every test above stubs the loader, which leaves one thing unproven: that the directory
    is reachable at all. A create plugin nobody can load is a create that always fails.
    """
    from utils.plugin_manager import PluginManager

    resolved = PluginManager().load_from_path(
        startpath=os.path.join(HERE, 'daemon', 'plugins', 'osimage'),
        root='osimage/operations/create', levelone=['compute', 'redhat', '9'])

    assert resolved is not None, 'the loader cannot reach a create plugin at all'
    assert callable(getattr(resolved(), 'create', None)), 'what it loaded has no create()'
