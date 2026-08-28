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
Every background worker the daemon defines is actually started.

A worker that nothing submits looks finished: it is written, it is tested, and it
never runs. The firmware sweeper was in exactly that state - the code, the tests and
the table all present, and no line in luna.py handing it to an executor - so the work
it drains would have been recorded by an operator and then sat there with nothing
saying why.

Derived rather than listed. A background worker is recognisable from its signature:
it takes the shutdown event and nothing else, because that is what a thread submitted
at startup and returning at shutdown looks like. Workers spawned per request take
their work as arguments instead, so they are not caught by this. Adding one more
example row would have fixed the sweeper and left the next one to be remembered.
"""

import inspect
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LUNA = os.path.join(REPO, 'daemon', 'luna.py')

# where the daemon's long-running workers live
MODULES = ['utils.housekeeper', 'utils.plugin_sync', 'utils.profile_sync',
           'utils.bios_push', 'utils.firmware_push']


def background_workers():
    """Every method that takes the shutdown event and nothing else."""
    import importlib
    found = []
    for modulename in MODULES:
        module = importlib.import_module(modulename)
        for classname, klass in vars(module).items():
            if not inspect.isclass(klass) or klass.__module__ != modulename:
                continue
            for methodname, method in vars(klass).items():
                if not inspect.isfunction(method):
                    continue
                parameters = list(inspect.signature(method).parameters)
                if parameters[1:] == ['event']:
                    found.append((classname, methodname))
    return found


def test_the_workers_are_found_at_all():
    """
    The list this test asserts against has to be non-empty, or it asserts nothing.
    """
    workers = background_workers()
    assert len(workers) >= 9, f'only found {workers}'


@pytest.mark.parametrize('classname,methodname', background_workers())
def test_every_background_worker_is_submitted(classname, methodname):
    with open(LUNA, 'r', encoding='utf-8') as handle:
        source = handle.read()
    assert re.search(rf'{classname}\(\)\.{methodname}\b', source), (
        f'{classname}.{methodname} takes the shutdown event, so it is a background '
        f'worker, and nothing in luna.py submits it')
