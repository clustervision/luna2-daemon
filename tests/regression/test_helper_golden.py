#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression baseline for Helper network math.

Pins get_network / get_netmask / get_network_size and the IP-range helpers to a
stored golden file. A change in any of these outputs fails the test, flagging a
behavioural shift that must be acknowledged (and the golden regenerated on
purpose). To regenerate after an intended change:

    python tests/regression/regen_network_math.py
"""

import json
import os

import pytest

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "network_math.json")


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN, "r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.regression
def test_network_math_matches_golden(helper, golden):
    for entry in golden["networks"]:
        network = helper.get_network(entry["ipaddr"], entry["subnet"])
        assert network == entry["network"], entry["ipaddr"]
        assert helper.get_netmask(network) == entry["netmask"], entry["ipaddr"]
        assert helper.get_network_size(entry["ipaddr"], entry["subnet"]) == entry["size"], entry["ipaddr"]


@pytest.mark.regression
def test_ip_ranges_match_golden(helper, golden):
    for entry in golden["ranges"]:
        assert helper.get_ip_range_size(entry["start"], entry["end"]) == entry["size"], entry["start"]
        assert helper.get_ip_range_ips(entry["start"], entry["end"]) == entry["ips"], entry["start"]
