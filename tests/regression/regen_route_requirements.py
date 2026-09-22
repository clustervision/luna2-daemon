#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Regenerate the route_requirements.json golden from the current routes and grammar.

Run this ONLY after adding or changing a route, a declaration on its decorator, or the
grammar on purpose, then read the diff before committing. Every changed line is a claim
about what that route requires of which object -- an unexplained change is a regression,
not a file to refresh.

    python tests/regression/regen_route_requirements.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
sys.path.insert(0, os.path.join(ROOT, 'daemon'))

import conftest  # noqa: E402,F401  installs the configuration stub the daemon imports
from cases.route_requirements_cases import build_requirement_map  # noqa: E402

GOLDEN = os.path.join(ROOT, 'tests', 'regression', 'golden', 'route_requirements.json')


def main():
    current = build_requirement_map()
    with open(GOLDEN, 'w', encoding='utf-8') as handle:
        json.dump(current, handle, indent=1, sort_keys=True)
        handle.write('\n')
    kinds = {}
    for value in current.values():
        kinds[value.get('kind', 'error')] = kinds.get(value.get('kind', 'error'), 0) + 1
    print(f'wrote {GOLDEN}: {len(current)} routes, {dict(sorted(kinds.items()))}')


if __name__ == '__main__':
    main()
