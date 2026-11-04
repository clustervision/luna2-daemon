#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Cancelling a create that a builder took.

A create handed to a builder has no pack worker, so cancel_pack finds nothing to stop. It then asks
the create plugin, which knows the builder, and says what it always said when the plugin cannot.
The builder ends the stream of its build, so nothing here writes to it.
"""

import pytest

from utils.helper import Helper


@pytest.fixture
def db(tmp_path):
    """A fresh SQLite database with the queue, status and osimage tables, and one image row."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'cancel.db')
    database.local_thread.connection = None
    for table in ['queue', 'status', 'osimage']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('osimage', Helper().make_rows({'name': 'imgB', 'distribution': 'redhat',
                                                      'osrelease': '9', 'path': '/trinity/images/imgB'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _base_osimage():
    from base.osimage import OSImage
    from utils.log import Log
    oi = OSImage.__new__(OSImage)
    oi.logger = Log.get_logger()
    oi.osimage_plugins = {}
    return oi


def _plugin(monkeypatch, plugin_class):
    """The create plugin the image resolves to, and the levels it was asked for."""
    asked = []

    def load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name=None):
        asked.append((root, levelone))
        return plugin_class

    monkeypatch.setattr(Helper, 'plugin_load', load)
    return asked


def _builder(answers):
    """A create plugin whose cancel answers as given and records the names it was asked about."""
    asked = []

    class Plugin:
        def cancel(self, name=None):
            asked.append(name)
            return answers

    Plugin.asked = asked
    return Plugin


def test_a_build_the_builder_holds_is_cancelled_through_the_create_plugin(db, monkeypatch):
    """With no pack worker the create plugin is asked, with the image's own distribution and release."""
    plugin = _builder((True, 'cancelled the build of osimage imgB'))
    asked = _plugin(monkeypatch, plugin)
    assert _base_osimage().cancel_pack('imgB') == (True, 'cancelled the build of osimage imgB')
    assert plugin.asked == ['imgB']
    assert asked == [('osimage/operations/create', ['imgB', 'redhat', '9'])]


def test_a_builder_that_holds_no_build_leaves_the_old_answer(db, monkeypatch):
    _plugin(monkeypatch, _builder((False, 'the builder holds no build of osimage imgB')))
    assert _base_osimage().cancel_pack('imgB') == (False, 'no active pack found for osimage imgB')


def test_a_create_plugin_without_cancel_leaves_the_old_answer(db, monkeypatch):
    """Sites keep their own copies of the create plugin, and one written before cancel existed must still load."""
    _plugin(monkeypatch, type('Old', (), {}))
    assert _base_osimage().cancel_pack('imgB') == (False, 'no active pack found for osimage imgB')


def test_an_image_luna_does_not_hold_is_not_asked_of_any_builder(db, monkeypatch):
    plugin = _builder((True, 'cancelled'))
    _plugin(monkeypatch, plugin)
    assert _base_osimage().cancel_pack('nope')[0] is False
    assert plugin.asked == []


def test_a_pack_worker_is_cancelled_by_luna_and_the_builder_is_not_asked(db, monkeypatch):
    """A pack in progress is Luna's own: the builder is asked only when there is none."""
    db.insert('queue', Helper().make_rows({'subsystem': 'osimage', 'status': 'in progress', 'request_id': 'P',
                                           'task': 'pack_osimage', 'param': 'imgB', 'noeof': 0,
                                           'created': 'NOW', 'owner_pid': 999999, 'owner_started': '1'}))
    plugin = _builder((True, 'cancelled'))
    _plugin(monkeypatch, plugin)
    ok, message = _base_osimage().cancel_pack('imgB')
    assert ok is True and message.startswith('cancelled pack for osimage imgB')
    assert plugin.asked == []


@pytest.fixture
def create_plugin(monkeypatch):
    """The default create plugin with the trixd addon's submit replaced, and the paths it was given."""
    from plugins.osimage.operations.create import default

    sent = []

    def use(answer, present=True):
        def submit(path=None, payload=None):
            sent.append((path, payload))
            return answer

        monkeypatch.setattr(default, 'trixd_submit', submit if present else None)
        return default.Plugin(), sent

    return use


def test_the_default_plugin_asks_trixd_to_cancel_the_build_by_name(create_plugin):
    plugin, sent = create_plugin({'name': 'imgB', 'state': 'cancelled'})
    assert plugin.cancel(name='imgB') == (True, 'cancelled the build of osimage imgB')
    assert [path for path, _ in sent] == ['/osimage/imgB/actions/cancel']


def test_the_default_plugin_says_so_when_trixd_holds_no_such_build(create_plugin):
    """The addon answers None for any refusal: trixd's 404 for no build, its 409 for one that ended."""
    plugin, _ = create_plugin(None)
    assert plugin.cancel(name='imgB') == (False, 'the builder holds no build of osimage imgB')


def test_the_default_plugin_says_so_when_there_is_no_trixd_addon(create_plugin):
    plugin, sent = create_plugin({}, present=False)
    assert plugin.cancel(name='imgB') == (False, 'no builder for osimage imgB')
    assert sent == []
