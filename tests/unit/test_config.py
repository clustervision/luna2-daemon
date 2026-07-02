#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for utils.config.Config.

Data-driven from cases/config_cases.py -- add pure Config methods there. Only
the input/output methods are covered; the database/template-heavy methods are
out of scope for unit tests. See tests/README.md.
"""

import pytest

from cases.config_cases import CASES


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_config_case(config, case):
    func = getattr(config, case["func"])
    args = case.get("args", [])
    kwargs = case.get("kwargs", {})
    if "raises" in case:
        with pytest.raises(case["raises"]):
            func(*args, **kwargs)
    else:
        assert func(*args, **kwargs) == case["expected"]
