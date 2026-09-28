# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TRIX-2178: the journal thread does not run on an unknown identity.

The controller finds itself by matching a local address against its controller row. Started
before its address was up, it found nothing, and the journal went on as 'None': it skipped
every pull and every entry meant for it, and then set itself in sync. These pin that the thread
waits for the address instead, says so while it waits, and is never in sync without an identity.
"""

import threading

import pytest


class FakeHA():
    """Answers get_me from a shared sequence, one entry per HA() built, as find_me would."""
    answers = []
    insync = []

    def __init__(self):
        self.me = FakeHA.answers.pop(0) if FakeHA.answers else None

    def get_me(self):
        return self.me

    def get_shadow(self):
        return False

    def get_hastate(self):
        return True

    def set_insync(self, state):
        FakeHA.insync.append((self.me, state))


class Logger():
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def info(self, message):
        pass


class Built(Exception):
    """Raised by the fake journal: the thread got as far as building it, which is all we need."""


@pytest.fixture
def housekeeper(monkeypatch):
    import utils.housekeeper as module
    FakeHA.answers, FakeHA.insync = [], []
    built = []

    def journal(me=None):
        built.append(me)
        raise Built()

    monkeypatch.setattr(module, 'HA', FakeHA)
    monkeypatch.setattr(module, 'Journal', journal)
    monkeypatch.setattr(module, 'Monitor',
                        lambda: type('M', (), {'update_itemstatus': lambda *a, **k: None})())
    monkeypatch.setattr(module, 'sleep', lambda seconds: None)
    monkeypatch.setattr(module.Helper, 'local_addresses',
                        lambda self: [('ipv4', 'eth0', '192.0.2.10')])
    keeper = module.Housekeeper.__new__(module.Housekeeper)
    keeper.logger = Logger()
    keeper.built = built
    return keeper


def test_the_identity_is_resolved_again_until_an_address_matches(housekeeper):
    FakeHA.answers = [None, None, 'controller1']
    housekeeper.journal_mother(threading.Event())
    assert housekeeper.built == ['controller1'], 'the journal runs as the controller it found'
    waiting = [e for e in housekeeper.logger.errors if 'belongs to a controller' in e]
    assert len(waiting) == 1, 'said once at the start, not every five seconds'
    assert '192.0.2.10' in waiting[0], 'names the addresses it does have'
    assert 'I am controller1, known after waiting 10 seconds for my address' in housekeeper.logger.warnings
    assert FakeHA.insync == [(None, False)], 'set out of sync before the wait, and never in sync without an identity'


def test_the_journal_does_not_run_without_an_identity(housekeeper):
    """The field case: the address never comes up before the daemon stops. Nothing is built as
    'None', and the controller is never set in sync."""
    event = threading.Event()
    event.set()
    housekeeper.journal_mother(event)
    assert housekeeper.built == [], f'the journal was built for {housekeeper.built}'
    assert FakeHA.insync == [(None, False)]
