#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1957 plugin selection order.

Every plugin root documents its own search path in its README, and they agree on the shape:
the most specific name first, the least specific last, with default.py as the final fallback.
The group-name step sat between the two and never ran -- PluginManager offered
plugins.<root>.default as a candidate for *each* levelone, so the node-name pass resolved it
and returned before the group name was ever looked at.

That is invisible from a single-candidate call, which is why it survived: the network and
osimage roots pass one levelone and behave identically either way. It only shows where a
caller passes a list, and there the wrong plugin is not an error -- default.py exists and
works, so a site's group plugin is silently ignored.

The callers are discovered from the source here rather than listed, so a new one that passes
a list is covered the day it is written. That is the actual defect class: a plugin root whose
documented order has a step nobody exercises.
"""

import importlib
import os
import re
import sys

import pytest

from utils.plugin_manager import PluginManager

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))

# Helper().plugin_load(<tree>, '<root>', [<levelone>, ...]) -- the list form is the one that
# depends on the order under test. A single-string levelone cannot express a preference.
#
# The list is not always a literal at the call site. control builds its candidates in a
# helper, because they depend on the node's manufacturer and on whether its BMC is known
# to speak Redfish, so a name ending in "candidates" counts as the list form too. Matching
# any bare identifier would be wrong: osimage passes a single `distribution` variable, and
# that is one candidate, not a preference order.
MULTI_CANDIDATE_CALL = re.compile(
    r"plugin_load\(\s*[^,()]+,\s*f?['\"]([^'\"]+)['\"]\s*,\s*(?:\[|\w*candidates\b)",
    re.DOTALL,
)


def _multi_candidate_roots():
    """Plugin roots the daemon asks for with a list of candidate names."""
    roots = set()
    for where, _dirs, files in os.walk(DAEMON):
        if f'{os.sep}plugins' in where:
            continue
        for name in files:
            if not name.endswith('.py'):
                continue
            with open(os.path.join(where, name), encoding='utf-8') as handle:
                roots.update(MULTI_CANDIDATE_CALL.findall(handle.read()))
    return sorted(roots)


ROOTS = _multi_candidate_roots()


@pytest.fixture
def plugin_tree(tmp_path, monkeypatch):
    """Write plugin modules into a throwaway tree and hand back a loader for them.

    The daemon imports plugins as 'plugins.<root>.<name>', so the tree has to be reachable
    under that name: tmp_path goes on sys.path and the real daemon/plugins stays where it is.
    Both are namespace packages, so the temp copy wins for a module it defines and the real
    one still resolves for everything else.
    """
    def _purge():
        for module_name in [one for one in sys.modules if one.split('.')[0] == 'plugins']:
            del sys.modules[module_name]
        PluginManager._class_cache.clear()
        PluginManager._module_state.clear()
        importlib.invalidate_caches()

    monkeypatch.syspath_prepend(str(tmp_path))
    _purge()

    def build(root, files):
        """files: {'<stem>': '<marker>'} written as <root>/<stem>.py, '/' allowed in stem."""
        for stem, marker in files.items():
            path = tmp_path / 'plugins' / root / f'{stem}.py'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"class Plugin():\n    marker = '{marker}'\n")
        _purge()
        top = str(tmp_path / 'plugins' / root.split('/')[0])

        def load(levelone, leveltwo=None):
            plugin = PluginManager().load_from_path(
                startpath=top, root=root, levelone=levelone, leveltwo=leveltwo
            )
            return None if plugin is None else plugin.marker

        return load

    yield build
    _purge()


# ------------------------------------------------------- the documented order, per real root
# Parametrised over the roots the daemon actually calls with a list, so a new such caller is
# covered without anyone remembering to add it here.

@pytest.mark.parametrize('root', ROOTS)
def test_group_plugin_is_picked_when_no_node_plugin_exists(plugin_tree, root):
    """The bug: default.py resolved during the nodename pass and the group never came up."""
    load = plugin_tree(root, {'compute': 'group', 'default': 'default'})
    assert load(['node001', 'compute']) == 'group', (
        f"{root}: a group plugin must be chosen over default.py. A site that names a plugin "
        f"after its group gets default.py instead, and nothing reports it."
    )


@pytest.mark.parametrize('root', ROOTS)
def test_node_plugin_still_wins_over_the_group_plugin(plugin_tree, root):
    """The priority the fix must not invert."""
    load = plugin_tree(root, {'node001': 'node', 'compute': 'group', 'default': 'default'})
    assert load(['node001', 'compute']) == 'node'


@pytest.mark.parametrize('root', ROOTS)
def test_default_is_still_the_fallback(plugin_tree, root):
    """Removing the per-levelone default must not cost the root its actual fallback."""
    load = plugin_tree(root, {'default': 'default'})
    assert load(['node001', 'compute']) == 'default', (
        f"{root}: default.py is the documented last resort and every root ships one."
    )


def test_a_root_with_no_default_returns_nothing(plugin_tree):
    """No candidate and no default is None -- not an exception, and not a stale cache hit.

    Deliberately a root that does not exist under daemon/plugins: the temp tree shadows only
    the modules it writes, so asking this of a real root would find the shipped default.py.
    """
    load = plugin_tree('boot/absent', {'other': 'other'})
    assert load(['node001', 'compute']) is None


def test_every_candidate_is_tried_not_just_the_first_two(plugin_tree):
    """boot/scripts passes three names; the third has to be reachable too."""
    load = plugin_tree('boot/scripts', {'redhat': 'distribution', 'default': 'default'})
    assert load(['node001', 'compute', 'redhat']) == 'distribution'


# ------------------------------------------------------- the single-candidate roots
# boot/network and osimage/operations/image pass one levelone plus a leveltwo. Their order is
# resolved inside a single pass, so the fix cannot reach it -- pinned here because that is the
# claim being made, not because the code changed.

def test_network_prefers_distribution_and_osrelease_over_distribution(plugin_tree):
    """README order 1: plugins/boot/network/redhat9.py beats redhat.py."""
    load = plugin_tree('boot/network', {'redhat9': 'redhat9', 'redhat': 'redhat',
                                        'default': 'default'})
    assert load('redhat', '9') == 'redhat9'


def test_network_falls_back_to_the_distribution_directory_default(plugin_tree):
    """README order 2, directory form: plugins/boot/network/redhat/default.py."""
    load = plugin_tree('boot/network', {'redhat/default': 'redhat-dir', 'default': 'default'})
    assert load('redhat', '9') == 'redhat-dir'


def test_network_falls_back_to_the_distribution_plugin(plugin_tree):
    """README order 2, flat form: plugins/boot/network/redhat.py."""
    load = plugin_tree('boot/network', {'redhat': 'redhat', 'default': 'default'})
    assert load('redhat', '9') == 'redhat'


def test_network_falls_back_to_default(plugin_tree):
    """README order 3. The single-levelone path reaches default through load(), as before."""
    load = plugin_tree('boot/network', {'default': 'default'})
    assert load('ubuntu', '24.04') == 'default'


# ------------------------------------------------------- the scan itself

def test_the_call_site_scan_finds_the_known_callers():
    """A regex that silently matched nothing would make every test above vacuously pass."""
    assert 'boot/bmc' in ROOTS and 'boot/scripts' in ROOTS and 'control' in ROOTS, ROOTS
