#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Cancelling a create that a builder took.

A create handed to a builder has no pack worker. cancel_create asks the create plugin, which knows
the builder; the _cancel route asks it once cancel_pack found nothing to stop, and says what it
always said when neither holds anything. The builder ends the stream of its build, so nothing here
writes to it.
"""

import json

import pytest
from jwt import encode

from cases.route_requirements_cases import app as routes_app
from utils.helper import Helper


@pytest.fixture
def db(sqlite_db):
    """The schema-complete database with one image row."""
    from utils.database import Database
    Database().insert('osimage', Helper().make_rows({'name': 'imgB', 'distribution': 'redhat',
                                                      'osrelease': '9', 'path': '/trinity/images/imgB'}))
    return Database()


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


def _cancel(name):
    """GET /config/osimage/<name>/_cancel as an admin: the code and the message."""
    from common.constant import CONSTANT
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    response = routes_app().test_client().get(f'/config/osimage/{name}/_cancel',
                                              headers={'x-access-tokens': token})
    return response.status_code, json.loads(response.data)['message']


def test_a_build_the_builder_holds_is_cancelled_through_the_create_plugin(db, monkeypatch):
    """The create plugin is asked, with the image's own distribution and release."""
    plugin = _builder((True, 'cancelled the build of osimage imgB'))
    asked = _plugin(monkeypatch, plugin)
    assert _base_osimage().cancel_create('imgB') == (True, 'cancelled the build of osimage imgB')
    assert plugin.asked == ['imgB']
    assert asked == [('osimage/operations/create', ['imgB', 'redhat', '9'])]


@pytest.mark.parametrize('image, levels', [
    ({}, ['imgN', 'redhat', '']),
    ({'distribution': 'RedHat', 'osrelease': '9'}, ['imgN', 'redhat', '9']),
], ids=['no distribution or release', 'mixed-case distribution'])
def test_the_create_plugin_is_resolved_as_create_osimage_resolves_it(db, monkeypatch, image, levels):
    """Cancel must reach the plugin that took the build, so it resolves exactly as create does."""
    db.insert('osimage', Helper().make_rows({'name': 'imgN', 'path': '/trinity/images/imgN', **image}))
    asked = _plugin(monkeypatch, _builder((True, 'cancelled')))
    assert _base_osimage().cancel_create('imgN')[0] is True
    assert asked == [('osimage/operations/create', levels)]


def test_a_builder_that_holds_no_build_says_so(db, monkeypatch):
    _plugin(monkeypatch, _builder((False, 'the builder holds no build of osimage imgB')))
    assert _base_osimage().cancel_create('imgB') == (False, 'the builder holds no build of osimage imgB')


def test_a_create_plugin_without_cancel_holds_no_build(db, monkeypatch):
    """Sites keep their own copies of the create plugin, and one written before cancel existed must still load."""
    _plugin(monkeypatch, type('Old', (), {}))
    assert _base_osimage().cancel_create('imgB') == (False, 'no builder holds a build of osimage imgB')


def test_an_image_luna_does_not_hold_is_not_asked_of_any_builder(db, monkeypatch):
    plugin = _builder((True, 'cancelled'))
    _plugin(monkeypatch, plugin)
    assert _base_osimage().cancel_create('nope') == (False, 'no builder holds a build of osimage nope')
    assert plugin.asked == []


def test_the_cancel_route_stops_a_build_the_builder_holds_when_there_is_no_pack(db, monkeypatch):
    plugin = _builder((True, 'cancelled the build of osimage imgB'))
    _plugin(monkeypatch, plugin)
    assert _cancel('imgB') == (200, 'cancelled the build of osimage imgB')
    assert plugin.asked == ['imgB']


def test_a_pack_worker_is_cancelled_by_luna_and_the_builder_is_not_asked(db, monkeypatch):
    """A pack in progress is Luna's own: the builder is asked only when there is none."""
    db.insert('queue', Helper().make_rows({'subsystem': 'osimage', 'status': 'in progress', 'request_id': 'P',
                                           'task': 'pack_osimage', 'param': 'imgB', 'noeof': 0,
                                           'created': 'NOW', 'owner_pid': 999999, 'owner_started': '1'}))
    plugin = _builder((True, 'cancelled'))
    _plugin(monkeypatch, plugin)
    code, message = _cancel('imgB')
    assert code == 200 and message.startswith('cancelled pack for osimage imgB')
    assert plugin.asked == []


def test_a_builder_that_holds_no_build_leaves_the_old_answer(db, monkeypatch):
    _plugin(monkeypatch, _builder((False, 'the builder holds no build of osimage imgB')))
    assert _cancel('imgB') == (404, 'no active pack found for osimage imgB')


def test_a_create_plugin_without_cancel_leaves_the_old_answer(db, monkeypatch):
    _plugin(monkeypatch, type('Old', (), {}))
    assert _cancel('imgB') == (404, 'no active pack found for osimage imgB')


def test_a_pack_that_could_not_be_stopped_keeps_its_own_answer(db, monkeypatch):
    """A found pack whose cancel failed is still the answer; the builder holding nothing does not hide it."""
    from base.osimage import OSImage
    from utils.osimage import OsImage
    monkeypatch.setattr(OSImage, 'CANCEL_GRACE_SECONDS', 0, raising=False)
    monkeypatch.setattr(Helper, 'safe_kill_worker', lambda self, pid, started, sig=None: True)
    monkeypatch.setattr(Helper, 'pid_alive', lambda self, pid, started=None: True)
    monkeypatch.setattr(OsImage, 'cleanup_image_mounts', lambda self, name: (False, '/trinity/images/imgB/sys'))
    db.insert('queue', Helper().make_rows({'subsystem': 'osimage', 'status': 'in progress', 'request_id': 'K',
                                           'task': 'pack_osimage', 'param': 'imgB', 'noeof': 0,
                                           'created': 'NOW', 'owner_pid': 4242, 'owner_started': '1'}))
    _plugin(monkeypatch, _builder((False, 'the builder holds no build of osimage imgB')))
    code, message = _cancel('imgB')
    assert code == 404 and 'mount cleanup failed' in message


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
