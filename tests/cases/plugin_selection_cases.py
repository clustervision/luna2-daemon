#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Builds the plugin selection map: for every shipped plugin root, which module the daemon
resolves for each candidate shape its callers use.

Shared by the regression test and its regen script so both compute the map exactly once,
in one place -- two copies of this arithmetic is one more place for them to disagree.

Why it plants files rather than probing the tree as shipped: as shipped, every root holds
only default.py, so every shape resolves to default and the map is blind to the search order
entirely. That is not a hypothetical -- it is the state a controller is in, and it is why a
four-month-old selection bug produced no visible symptom. The order is only observable when
something more specific than default is present, so the map plants candidates at each level
and varies which levels exist.

Roots come from the shipped tree and shapes from the callers, so a new plugin root or a new
candidate level appears in the map without anyone adding it here.
"""

import json
import os
import shutil
import sys

NODE = 'probenode'
GROUP = 'probegroup'
DISTRO = 'probedistro'
RELEASE = '9'
OSIMAGE = 'probeimage'

# What a caller asks for. Named for the call sites that use each shape.
SHAPES = [
    ('node+group', [NODE, GROUP], None),                        # boot/bmc, control, hooks/control
    ('node+group+distro', [NODE, GROUP, DISTRO], None),         # boot/scripts
    ('node+distro+osimage+group', [NODE, DISTRO, OSIMAGE, GROUP], None),  # osgrab, ospush
    ('group-only', [GROUP], None),                              # a node with no node-level plugin
    ('distro+release', DISTRO, RELEASE),                        # boot/network, osimage image
    ('unknown', ['nosuchcandidate'], None),                     # nothing matches -> the fallback
]

# Which candidate files exist. Each variant answers "what happens when this level is absent?".
VARIANTS = {
    'all-levels': [f'{NODE}.py', f'{GROUP}.py', f'{DISTRO}.py', f'{DISTRO}{RELEASE}.py',
                   f'{OSIMAGE}.py'],
    'no-node': [f'{GROUP}.py', f'{DISTRO}.py', f'{DISTRO}{RELEASE}.py', f'{OSIMAGE}.py'],
    'group-only': [f'{GROUP}.py'],
    'distro-only': [f'{DISTRO}.py'],
    'as-shipped': [],
}


def shipped_roots(plugins_dir):
    """Every directory under the plugin tree that holds a plugin, as a 'boot/bmc' style root."""
    roots = []
    for where, _dirs, files in os.walk(plugins_dir):
        if '__pycache__' in where:
            continue
        if not any(name.endswith('.py') for name in files):
            continue
        roots.append(os.path.relpath(where, plugins_dir).replace(os.sep, '/'))
    return sorted(roots)


def _purge():
    """Drop imported plugin modules and the manager's caches between variants.

    The variants deliberately reuse module names with different content, and both the
    interpreter and PluginManager cache by name -- without this, variant two would be served
    variant one's classes.
    """
    from utils.plugin_manager import PluginManager
    import importlib
    for module_name in [one for one in sys.modules if one.split('.')[0] == 'plugins']:
        del sys.modules[module_name]
    PluginManager._class_cache.clear()
    PluginManager._module_state.clear()
    importlib.invalidate_caches()


def build_selection_map(plugins_dir, workdir):
    """Resolve every (variant, root, shape) against a copy of the shipped tree.

    The copy is what makes this honest: the tree the loader reads and the modules it imports
    are the same files, so a resolution cannot come from one and the import from the other.
    """
    from utils.helper import Helper

    plugins_dir = os.path.abspath(plugins_dir)
    roots = shipped_roots(plugins_dir)
    selection = {}

    for variant, planted in VARIANTS.items():
        overlay = os.path.join(workdir, variant)
        target = os.path.join(overlay, 'plugins')
        if os.path.isdir(overlay):
            shutil.rmtree(overlay)
        shutil.copytree(plugins_dir, target,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for root in roots:
            for filename in planted:
                path = os.path.join(target, root.replace('/', os.sep), filename)
                with open(path, 'w', encoding='utf-8') as handle:
                    handle.write("class Plugin():\n    pass\n")

        sys.path.insert(0, overlay)
        _purge()
        try:
            helper = Helper()
            for root in roots:
                top = os.path.join(target, root.split('/')[0])
                tree = helper.plugin_finder(top)
                for shape, levelone, leveltwo in SHAPES:
                    key = f'{variant} | {root} | {shape}'
                    try:
                        plugin = helper.plugin_load(tree, root, levelone, leveltwo)
                        selection[key] = plugin.__module__ if plugin is not None else None
                    except Exception as exp:                     # noqa: BLE001 - recorded, not raised
                        selection[key] = f'{type(exp).__name__}: {exp}'
        finally:
            sys.path.remove(overlay)
            _purge()

    return {'roots': roots, 'selection': selection}


def dumps(selection_map):
    """One stable JSON form, so the golden diffs line by line."""
    return json.dumps(selection_map, indent=1, sort_keys=True) + '\n'
