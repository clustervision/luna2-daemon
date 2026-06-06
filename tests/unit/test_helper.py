#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for utils.helper.Helper.

The bulk of the coverage is data-driven: every entry in cases/helper_cases.py
is run through test_helper_case below. Add a function under test by editing
that table -- see tests/README.md. The remaining tests cover behaviour that a
simple input/output table cannot express (non-deterministic output, mutation,
stateful objects).
"""

import pytest

from cases.helper_cases import CASES


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_helper_case(helper, case):
    func = getattr(helper, case["func"])
    args = case.get("args", [])
    kwargs = case.get("kwargs", {})
    if "raises" in case:
        with pytest.raises(case["raises"]):
            func(*args, **kwargs)
    else:
        assert func(*args, **kwargs) == case["expected"]


def test_encrypt_decrypt_roundtrip(helper):
    """Ciphertext is opaque and differs from the plaintext, but decrypts back."""
    secret = "super-secret-value"
    token = helper.encrypt_string(secret)
    assert token != secret
    assert helper.decrypt_string(token) == secret


def test_decrypt_legacy_value_is_untouched(helper):
    """Non-token (legacy/plain) input must come back unchanged, never raise."""
    assert helper.decrypt_string("not-a-fernet-token") == "not-a-fernet-token"


def test_encrypt_empty_returns_input(helper):
    assert helper.encrypt_string("") == ""
    assert helper.encrypt_string(None) is None


def test_chunks_splits_evenly_and_remainder(helper):
    assert list(helper.chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_pipeline_node_lifecycle(helper):
    """Pipeline is a small thread-safe holder; verify its add/get/has contract."""
    pipeline = helper.Pipeline()
    assert pipeline.has_nodes() is False
    pipeline.add_nodes({"node001": {"state": "boot"}})
    assert pipeline.has_nodes() is True
    name, payload = pipeline.get_node()
    assert name == "node001"
    assert payload == {"state": "boot"}
    assert pipeline.has_nodes() is False
