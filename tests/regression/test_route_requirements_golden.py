"""
The requirement of every registered route, pinned. A new route, or a changed reading of
an old one, shows up here as a diff a reviewer has to bless: nothing about what a route
requires changes without a visible line.
"""
import json
import os

import pytest

from cases.route_requirements_cases import build_requirement_map

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden', 'route_requirements.json')


@pytest.fixture(scope='module')
def golden():
    with open(GOLDEN, 'r', encoding='utf-8') as handle:
        return json.load(handle)


@pytest.mark.regression
def test_route_requirements_match_golden(golden):
    """Entry by entry, so a failure names the route and what moved."""
    current = build_requirement_map()
    moved = {key: (golden[key], value) for key, value in current.items()
             if key in golden and golden[key] != value}
    added = sorted(set(current) - set(golden))
    missing = sorted(set(golden) - set(current))
    hint = ('If that is intended, regenerate the golden with '
            'tests/regression/regen_route_requirements.py and review the diff.')
    assert not moved, 'a route now requires something else:\n' + '\n'.join(
        f'  {key}\n      was: {was}\n      now: {now}' for key, (was, now) in sorted(moved.items())) + f'\n{hint}'
    assert not added, f'routes not in the golden: {added}\n{hint}'
    assert not missing, f'routes in the golden that no longer exist: {missing}\n{hint}'
