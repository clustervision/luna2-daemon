#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2276: what the config hooks stop doing once trixd has the change.

Where trixd took a rename or a delete it owns the hardware rule files under the
Prometheus rules directory - it carries them to the new name and retires them with a
copy - so the hook's own rename and rm are the fallback for a controller without trixd,
not something that runs as well and undoes it.
"""

import pytest

INI = """[API]
PROTOCOL = http
BIND = 127.0.0.1:8050
USERNAME = luna
PASSWORD = secret
"""


class Answer:
    """The parts of a requests response the addon reads."""
    status_code = 200
    text = ''

    @staticmethod
    def json():
        return {'token': 'a-token'}


@pytest.fixture
def trixd(tmp_path, monkeypatch):
    """A trixd that accepts everything and records each set, with no network behind it.

    Where trixd answers and the token it gave are both held in module globals for the
    life of the process, so they are reset here: one test must not answer for the next.
    """
    import plugins.addons.trixd as addon

    ini = tmp_path / 'trixd.ini'
    ini.write_text(INI)
    monkeypatch.setenv('TRIXD_INI', str(ini))
    monkeypatch.setattr(addon, '_resolved', None)
    monkeypatch.setattr(addon, '_token', None)

    posted = []

    class Requests:
        @staticmethod
        def post(url, json=None, **kwargs):
            if url.endswith('/system/bulk'):
                posted.append(json)
            return Answer()

    monkeypatch.setattr(addon, 'requests', Requests)
    return posted


@pytest.fixture
def rule_files(monkeypatch):
    """Records what the node hook shells out to run, and keeps it off the filesystem."""
    import plugins.hooks.config.node as hook

    ran = []

    class Finished:
        args = 'recorded'
        returncode = 0
        stderr = b''

    class Subprocess:
        PIPE = -1

        @staticmethod
        def run(command, **kwargs):
            ran.append(command)
            return Finished()

    monkeypatch.setattr(hook, 'subprocess', Subprocess)
    return ran


def test_a_rename_leaves_the_rule_files_to_trixd(trixd, rule_files):
    """Told, the hook does not touch the files trixd is about to carry itself."""
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().rename('node001', 'node002')
    assert len(trixd) == 1, 'the rename was not handed to trixd at all'
    assert rule_files == [], (
        f'trixd took the rename and the hook ran {rule_files} as well. Both move the '
        f'same files, and only trixd knows where it has already put them.'
    )
    assert status is True, message


def test_a_rename_renames_the_rule_files_itself_without_trixd(rule_files, monkeypatch):
    """No addon on this controller: exactly what ran before still runs."""
    import plugins.hooks.config.node as hook
    monkeypatch.setattr(hook, 'trixd_notify', None)
    status, message = hook.Plugin().rename('node001', 'node002')
    assert len(rule_files) == 1, (
        f'without trixd nothing carries the rule files but the hook, and it ran '
        f'{rule_files}'
    )
    assert '/usr/bin/rename' in rule_files[0][0]
    assert 'prometheus_server/rules' in rule_files[0][0]
    assert status is True, message


def test_a_delete_leaves_the_rule_files_to_trixd(trixd, rule_files):
    """The same for a delete: trixd retires them with a copy, the hook's rm does not."""
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().delete('node001')
    assert len(trixd) == 1, 'the delete was not handed to trixd at all'
    assert rule_files == [], (
        f'trixd took the delete and the hook ran {rule_files} as well, which removes '
        f'the files trixd keeps a copy of.'
    )
    assert status is True, message
