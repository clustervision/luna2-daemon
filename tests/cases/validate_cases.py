#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data-driven test cases for common.validate_input free functions.

These are module-level functions (not class methods), so each case names the
callable directly rather than by string. To add a function under test, append
a dict to CASES; tests/unit/test_validate_input.py runs every entry.

Each case is a dict with:
    id        required  unique, human-readable label
    func      required  the callable to invoke
    args      optional  list of positional arguments  (default: [])
    kwargs    optional  dict of keyword arguments      (default: {})
    expected  required  the value the call must return (unless 'raises')
    raises    optional  an exception type the call must raise

See tests/README.md for the full how-to.
"""

from common.validate_input import filter_data, check_structure

CASES = [
    # --- filter_data with no name: strip control chars and quotes only ---
    {"id": "filter-strip-single-quote", "func": filter_data, "args": ["hello'world"],
     "expected": "helloworld"},
    {"id": "filter-strip-double-quote", "func": filter_data, "args": ['a"b'],
     "expected": "ab"},
    {"id": "filter-strip-control-char", "func": filter_data, "args": ["a\x00b\x1fc"],
     "expected": "abc"},
    {"id": "filter-clean-unchanged", "func": filter_data, "args": ["plain-text_1.2"],
     "expected": "plain-text_1.2"},

    # --- filter_data with name='name': applies the 'name' rules (dots collapse) ---
    {"id": "filter-name-collapse-dots", "func": filter_data, "args": ["a..b", "name"],
     "expected": "a.b"},

    # --- check_structure: nested colon-path presence checks ---
    {"id": "structure-present", "func": check_structure,
     "args": [{"a": {"b": {"c": 1}}}, "a:b:c"], "expected": True},
    {"id": "structure-absent", "func": check_structure,
     "args": [{"a": {"b": 1}}, "a:b:c"], "expected": False},
    {"id": "structure-no-checks", "func": check_structure, "args": [{"a": 1}, None],
     "expected": True},
    {"id": "structure-list-of-checks", "func": check_structure,
     "args": [{"a": 1, "b": 2}, ["a", "b"]], "expected": True},
]
