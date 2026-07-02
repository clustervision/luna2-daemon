#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for common.validate_input free functions.

Data-driven from cases/validate_cases.py -- add cases there. The extra test
below covers mutation behaviour (parse_item rewrites a nested structure in
place) that the value table cannot capture cleanly.
"""

import pytest

from cases.validate_cases import CASES


@pytest.fixture(autouse=True)
def validate_state():
    """
    filter_data/parse_item read module globals that the input_filter and
    validate_name decorators set at request time. Outside a request they are
    undefined, so we initialise them to the decorators' default (non-strict)
    state before each test -- exactly what a non-strict route would see.
    """
    import common.validate_input as validate_input
    validate_input.STRICT_NAME = False
    validate_input.STRICT_MATCH = None
    validate_input.ERROR = None
    validate_input.SKIP_LIST = []


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_validate_case(case):
    func = case["func"]
    args = case.get("args", [])
    kwargs = case.get("kwargs", {})
    if "raises" in case:
        with pytest.raises(case["raises"]):
            func(*args, **kwargs)
    else:
        assert func(*args, **kwargs) == case["expected"]


def test_parse_item_filters_nested_strings():
    """Quotes are stripped recursively through dicts and lists."""
    from common.validate_input import parse_item
    data = {"outer": ["a'b", {"inner": 'c"d'}]}
    result = parse_item(data)
    assert result["outer"][0] == "ab"
    assert result["outer"][1]["inner"] == "cd"
