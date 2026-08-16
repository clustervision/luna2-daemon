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
    matters: "node'--" cleans to "node--", which is a perfectly good name,
    while the original arrives at the where clause with its quote intact -
    closing the first condition and commenting the rest away.

    Observed live on the route couple/decouple path before this: a name of
    "x'--" cleaned to a valid name, passed, and reached the query with its
    quote intact.
    """
    import common.validate_input as validate_input
    from common.validate_input import filter_data

    for payload in ("node'--", 'node"--', "compute' OR '1'='1", "node'"):
        validate_input.ERROR = None
        filter_data(payload, 'name')
        assert validate_input.ERROR, f"{payload!r} must be rejected, not cleaned into a valid name"

    validate_input.ERROR = None
    assert filter_data('node01', 'name') == 'node01'
    assert not validate_input.ERROR, "an ordinary value must still pass"


def test_cleaning_still_happens_for_fields_with_no_regex():
    """
    Only the check moved to the raw value; the sanitising is untouched. A field
    with no MATCH entry has no regex to fail, so it is cleaned and passed on
    exactly as before - which is what parse_item's callers rely on.
    """
    from common.validate_input import filter_data
    assert filter_data("it's fine", 'some_unregistered_field') == 'its fine'


# ---------------------------------------------------------------------------
# Registration-list guards.
#
# The input validator is keyed on the field name and on the route function
# name (MATCH, STRICT_NAMES). Both are hand-maintained lists paired with a
# declarative reality nothing enforces: a field a base class accepts, a route
# that puts a URL segment into a where clause. Forgetting the list is silent -
# the value passes unchecked. These tests derive the lists from the code and
# fail when they drift, so the miss is caught in CI rather than live.
#
# Each was written after finding a live drift: three rename fields absent from
# MATCH (one produced an unaddressable route; another a route name accepted via
# a where clause with no regex), and the route couple/decouple endpoints
# carrying @token_required but not @validate_name - probed live, a name of
# "x' OR '1'='1" changed the query's truth.
# ---------------------------------------------------------------------------

import ast
import os

DAEMON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')


def _rename_fields_accepted_by_base():
    """
    Every 'new<thing>name'-style key a base class reads from a request. These
    become an object's stored name, so each must be validated like the name it
    replaces. Derived by walking base/ for string subscripts of that shape.
    """
    found = {}
    base_dir = os.path.join(DAEMON_DIR, 'base')
    for name in os.listdir(base_dir):
        if not name.endswith('.py'):
            continue
        path = os.path.join(base_dir, name)
        with open(path, encoding='utf-8') as source:
            tree = ast.parse(source.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if value.startswith('new') and value.endswith('name') and value not in ('new', 'name'):
                    found.setdefault(value, name)
    return found


def test_every_base_rename_field_is_registered_in_MATCH():
    """A rename field absent from MATCH is stored with no regex and no length bound."""
    from common.validate_input import MATCH
    fields = _rename_fields_accepted_by_base()
    missing = {field: origin for field, origin in fields.items() if field not in MATCH}
    assert not missing, (
        "rename fields accepted by a base class but not in MATCH (stored unvalidated): "
        + ', '.join(f'{field} (base/{origin})' for field, origin in sorted(missing.items())))


def _routes_with_name_in_path():
    """
    Every route function whose URL carries a <string:...> segment, paired with
    the decorators applied to it. Those segments are interpolated into where
    clauses downstream, so each such function must carry @validate_name.
    """
    routes_dir = os.path.join(DAEMON_DIR, 'routes')
    functions = []
    for name in os.listdir(routes_dir):
        if not name.endswith('.py'):
            continue
        path = os.path.join(routes_dir, name)
        with open(path, encoding='utf-8') as source:
            tree = ast.parse(source.read(), filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = []
            has_string_path = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decorators.append(dec.attr)
                elif isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)
                    elif isinstance(dec.func, ast.Attribute):
                        decorators.append(dec.func.attr)
                    for arg in dec.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                                and '<string:' in arg.value:
                            has_string_path = True
            if has_string_path:
                functions.append((f'{name}:{node.name}', decorators))
    return functions


# Routes whose <string:...> segment does NOT reach a query, checked by hand and
# listed with the reason - the segment's fate, not "it looked fine". A route added
# here escapes the guard, so the reason has to be that the value genuinely cannot
# reach SQL, not that validating it is inconvenient.
PATH_SEGMENT_NOT_A_QUERY = {
    'config_rack.py:config_inventory_get_subset':
        "subset is only ever compared in Python (== 'configured'/'unconfigured'); "
        "it never reaches a query",
    'files.py:files_get':
        "filename is a filesystem path served on the tokenless early-boot path; it is "
        "not a SQL value, and File.get_file handles its own path containment. Its risk "
        "class is traversal, not injection - guard it there, not with a name regex",
}


def test_every_route_with_a_name_in_its_path_validates_it():
    """
    A URL name segment reaches a where clause. Without @validate_name it is
    unchecked - the couple/decouple SQL-injection hole. token_required proves
    who is calling, not what they sent, so it is not a substitute here.

    Broad by design: it flags every <string:...> segment and forces each that
    does not validate to be either fixed or named in PATH_SEGMENT_NOT_A_QUERY
    with the reason it cannot reach SQL. Narrowing the test to "only segments
    that reach a query" would hide the next one that quietly starts to.
    """
    offenders = [
        function for function, decorators in _routes_with_name_in_path()
        if 'validate_name' not in decorators and 'input_filter' not in decorators
        and function not in PATH_SEGMENT_NOT_A_QUERY
    ]
    assert not offenders, (
        "routes with a <string:...> path segment but neither @validate_name nor "
        "@input_filter (the segment reaches a query unvalidated): " + ', '.join(sorted(offenders)))
