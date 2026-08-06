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


def test_a_quoted_name_is_rejected_rather_than_cleaned_into_a_valid_one():
    """
    The regex has to see what the caller sent.

    filter_data returns a copy with the quotes taken out, but validate_name
    discards that return and calls the route with the original kwargs. So the
    value that gets approved and the value that reaches the query are not the
    same string, and the check is meaningless for exactly the character that
    matters: "osimage'--" cleans to "osimage--", which is a perfectly good
    strictname, while the original arrives at the where clause with its quote
    intact - closing the first condition and commenting the rest away.

    Observed live before this: /hash/osimage'--/<name> returned every row for
    the object type instead of the one asked for, because the name predicate
    had been commented out.
    """
    import common.validate_input as validate_input
    from common.validate_input import filter_data

    for payload in ("osimage'--", 'osimage"--', "compute' OR '1'='1", "node'"):
        validate_input.ERROR = None
        filter_data(payload, 'object_type')
        assert validate_input.ERROR, f"{payload!r} must be rejected, not cleaned into a valid name"

    validate_input.ERROR = None
    assert filter_data('osimage', 'object_type') == 'osimage'
    assert not validate_input.ERROR, "an ordinary value must still pass"


def test_cleaning_still_happens_for_fields_with_no_regex():
    """
    Only the check moved to the raw value; the sanitising is untouched. A field
    with no MATCH entry has no regex to fail, so it is cleaned and passed on
    exactly as before - which is what parse_item's callers rely on.
    """
    from common.validate_input import filter_data
    assert filter_data("it's fine", 'some_unregistered_field') == 'its fine'
