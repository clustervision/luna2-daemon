#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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

"""
Unit tests guarding the install_mode field: its accepted values and its default.

install_mode selects the install pipeline. `legacy` means the classic
templ_install.cfg installer; every other value is an advanced-partitioner mode.
Two properties matter and neither is enforced by anything else:

1. The DEFAULT MUST BE `legacy`. It is what a node resolves to when it has never
   set the field -- which is every node that predates it. Defaulting to any other
   value silently moves the whole installed base onto a different install
   pipeline, and `auto` in particular means memory-root (tmpfs) when no
   disklayout is set: an existing node would come up diskless. The default is the
   entire backwards-compatibility guarantee for this field, so it is pinned here.

2. node.py and group.py MUST ACCEPT THE SAME SET. The field cascades group -> node,
   so a value one accepts and the other rejects is a value that can be set on a
   group and never on a node, or vice versa. The lists are inline in both files
   (matching how ipxe_kernel is validated), which is exactly the parallel-list
   shape this repo keeps drifting on -- so the guard is a test rather than
   vigilance.

Both are read from the source with ast, in the style of test_journal_dispatch.py:
the declarative reality is what the code actually contains, not what a constant
elsewhere claims.
"""

import ast
import os

import pytest

DAEMON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon'
)

# The seven modes the advanced partitioner defines. `legacy` is the classic
# installer; the other six are lpart modes.
DOCUMENTED_MODES = {'auto', 'sync', 'full', 'local', 'memboot', 'sanitize', 'legacy'}

# 'memboot' appears in no other list in the daemon, so it identifies the
# install_mode enum without depending on where in the file it sits.
MARKER = 'memboot'

SOURCES = ['base/node.py', 'base/group.py']


def _tree(relpath):
    with open(os.path.join(DAEMON, relpath), 'r', encoding='utf-8') as handle:
        return ast.parse(handle.read())


def _accepted_modes(relpath):
    """Every list literal in the file that looks like the install_mode enum."""
    found = []
    for node in ast.walk(_tree(relpath)):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            continue
        values = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if MARKER in values:
            found.append(set(values))
    return found


def _defaults(relpath):
    """Every `'install_mode': <literal>` entry in a dict literal in the file."""
    found = []
    for node in ast.walk(_tree(relpath)):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == 'install_mode'
                and isinstance(value, ast.Constant)
            ):
                found.append(value.value)
    return found


@pytest.mark.parametrize('relpath', SOURCES)
def test_install_mode_default_is_legacy(relpath):
    """An unset install_mode must resolve to the classic installer, not an lpart mode."""
    defaults = _defaults(relpath)
    assert defaults, f'{relpath} declares no install_mode default'
    for value in defaults:
        assert value == 'legacy', (
            f"{relpath} defaults install_mode to {value!r}. It must be 'legacy': this default is "
            f'what every node that predates the field resolves to, and any other value moves the '
            f'installed base onto the advanced-partitioner pipeline without anyone asking for it.'
        )


@pytest.mark.parametrize('relpath', SOURCES)
def test_install_mode_validated_against_the_documented_modes(relpath):
    """Each file must validate install_mode, and against exactly the seven modes."""
    accepted = _accepted_modes(relpath)
    assert accepted, (
        f'{relpath} does not validate install_mode. Without it any string that is not '
        f"'legacy' selects an advanced-partitioner mode, so a typo silently changes the "
        f'install pipeline.'
    )
    for modes in accepted:
        assert modes == DOCUMENTED_MODES, (
            f'{relpath} accepts {sorted(modes)}, expected {sorted(DOCUMENTED_MODES)}'
        )


def test_node_and_group_accept_the_same_modes():
    """The lists are inline in both files; this is what keeps them from drifting apart."""
    node_modes = _accepted_modes('base/node.py')
    group_modes = _accepted_modes('base/group.py')
    assert node_modes and group_modes, 'both node.py and group.py must validate install_mode'
    assert node_modes[0] == group_modes[0], (
        f'node.py accepts {sorted(node_modes[0])} but group.py accepts {sorted(group_modes[0])}. '
        f'install_mode cascades group -> node, so the two must agree.'
    )
