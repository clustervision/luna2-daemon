#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Regression baseline for plugin selection (TRIX-1957).

Pins which module the daemon resolves for every shipped plugin root, under every candidate
shape its callers use, with the candidate levels present and absent in turn. A change in any
of those answers fails the test.

The unit tests beside this one assert the rule; this asserts the whole surface. The bug it
was written for was not one root behaving oddly -- it was one line in the shared resolver
silently changing the answer for every root at once, in a way no single example test would
have shown.

Read the golden as claims about intended behaviour, not as recorded output: node beats group
beats distribution beats default, and default is the last resort rather than the first
answer. An unexplained move in it is a regression to investigate. To regenerate after an
intended change:

    python tests/regression/regen_plugin_selection.py
"""

import json
import os

import pytest

from cases.plugin_selection_cases import build_selection_map, shipped_roots

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden', 'plugin_selection.json')
PLUGINS = os.path.join(os.path.dirname(__file__), '..', '..', 'daemon', 'plugins')


@pytest.fixture(scope='module')
def golden():
    with open(GOLDEN, 'r', encoding='utf-8') as handle:
        return json.load(handle)


@pytest.fixture(scope='module')
def resolved(tmp_path_factory):
    return build_selection_map(PLUGINS, str(tmp_path_factory.mktemp('plugin_selection')))


@pytest.mark.regression
def test_every_shipped_root_is_in_the_golden(golden):
    """A new plugin root joins the baseline deliberately, not silently."""
    assert shipped_roots(os.path.abspath(PLUGINS)) == golden['roots'], (
        'the shipped plugin roots have changed. If that is intended, regenerate the golden '
        'with tests/regression/regen_plugin_selection.py and review the diff.'
    )


@pytest.mark.regression
def test_plugin_selection_matches_golden(resolved, golden):
    """The selection map, entry by entry, so a failure names the root and the shape."""
    moved = {key: (golden['selection'][key], value)
             for key, value in resolved['selection'].items()
             if golden['selection'].get(key) != value}
    added = sorted(set(resolved['selection']) - set(golden['selection']))
    missing = sorted(set(golden['selection']) - set(resolved['selection']))

    assert not moved, 'plugin selection changed:\n' + '\n'.join(
        f'  {key}\n      was: {was}\n      now: {now}' for key, (was, now) in sorted(moved.items()))
    assert not added, f'new resolutions not in the golden: {added}'
    assert not missing, f'resolutions in the golden that no longer happen: {missing}'


@pytest.mark.regression
def test_the_baseline_can_see_the_order_at_all(golden):
    """A golden built only from the shipped tree would be all defaults, and blind.

    Every root ships nothing but default.py, so with no candidate planted every shape
    resolves to default whatever the search order is -- which is exactly the state that let a
    selection bug sit in the trunk without a symptom. If this assertion ever fails, the
    baseline has stopped exercising the thing it exists to pin.
    """
    interesting = [value for key, value in golden['selection'].items()
                   if not key.startswith('as-shipped') and value and not value.endswith('.default')]
    assert len(interesting) > 100, (
        f'only {len(interesting)} non-default resolutions in the baseline; it is no longer '
        f'exercising the search order'
    )
