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

# install_mode resolves node -> group -> cluster -> 'legacy', the same shape as
# provision_method. Only node and group carry the fallback dict; cluster is a
# source, not a resolver, so it validates but declares no default.
SOURCES = ['base/node.py', 'base/group.py']
VALIDATING_SOURCES = ['base/node.py', 'base/group.py', 'base/cluster.py']


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


@pytest.mark.parametrize('relpath', VALIDATING_SOURCES)
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


def test_every_level_accepts_the_same_modes():
    """The lists are inline in each file; this is what keeps them from drifting apart."""
    seen = {}
    for relpath in VALIDATING_SOURCES:
        modes = _accepted_modes(relpath)
        assert modes, f'{relpath} must validate install_mode'
        seen[relpath] = modes[0]
    distinct = {frozenset(m) for m in seen.values()}
    assert len(distinct) == 1, (
        f'the levels disagree on install_mode: '
        + '; '.join(f'{k} accepts {sorted(v)}' for k, v in seen.items())
        + '. install_mode cascades cluster -> group -> node, so all three must agree.'
    )


def test_install_mode_is_on_the_same_tables_as_provision_method():
    """
    Derived from the schema rather than listed here: install_mode is a cluster-wide
    setting in the same sense provision_method is, so it must exist on exactly the
    tables provision_method exists on. Enumerating the layout means a table added to
    one and not the other fails here instead of silently losing a cascade level.
    """
    layout = os.path.join(DAEMON, 'common', 'database_layout.py')
    with open(layout, 'r', encoding='utf-8') as handle:
        tree = ast.parse(handle.read())

    tables = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            name = getattr(target, 'id', '')
            if not name.startswith('DATABASE_LAYOUT_'):
                continue
            columns = set()
            for entry in ast.walk(node.value):
                if not isinstance(entry, ast.Dict):
                    continue
                for key, value in zip(entry.keys, entry.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == 'column'
                        and isinstance(value, ast.Constant)
                    ):
                        columns.add(value.value)
            tables[name[len('DATABASE_LAYOUT_'):]] = columns

    with_provision = {t for t, c in tables.items() if 'provision_method' in c}
    with_install = {t for t, c in tables.items() if 'install_mode' in c}
    assert with_provision, 'no table declares provision_method -- has the layout moved?'
    assert with_install == with_provision, (
        f'install_mode is on {sorted(with_install)} but provision_method is on '
        f'{sorted(with_provision)}. install_mode is a cluster-wide setting in the same sense, '
        f'so the two must sit on the same tables.'
    )
