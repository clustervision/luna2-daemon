#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data-driven test cases for utils.helper.Helper methods.

To put another Helper method under test, append a dict to CASES. No test code
needs to change -- tests/unit/test_helper.py runs every entry here.

Each case is a dict with:
    id        required  unique, human-readable label shown in the test report
    func      required  name of the Helper method to call, as a string
    args      optional  list of positional arguments        (default: [])
    kwargs    optional  dict of keyword arguments            (default: {})
    expected  required  the value the method must return     (unless 'raises')
    raises    optional  an exception type the call must raise (use instead of
                        'expected' when the method is expected to throw)

Only use this table for methods whose result is a pure function of their
inputs. Methods needing a database, filesystem or other setup belong in a
dedicated test module with the appropriate fixture.

See tests/README.md for the full how-to.
"""

CASES = [
    # --- make_bool: string/int/bool truthy and falsy forms ---
    {"id": "make_bool-yes", "func": "make_bool", "args": ["yes"], "expected": True},
    {"id": "make_bool-True", "func": "make_bool", "args": ["True"], "expected": True},
    {"id": "make_bool-1-int", "func": "make_bool", "args": [1], "expected": True},
    {"id": "make_bool-no", "func": "make_bool", "args": ["no"], "expected": False},
    {"id": "make_bool-0-str", "func": "make_bool", "args": ["0"], "expected": False},
    {"id": "make_bool-passthrough-bool", "func": "make_bool", "args": [True], "expected": True},
    {"id": "make_bool-empty-is-none", "func": "make_bool", "args": [""],
     "kwargs": {"empty_is_none": True}, "expected": None},
    {"id": "make_bool-unknown-type", "func": "make_bool", "args": [["x"]], "expected": None},

    # --- bool_revert: only '0'/'1'/0/1 and bools are meaningful ---
    {"id": "bool_revert-True", "func": "bool_revert", "args": [True], "expected": "1"},
    {"id": "bool_revert-False", "func": "bool_revert", "args": [False], "expected": "0"},
    {"id": "bool_revert-str-1", "func": "bool_revert", "args": ["1"], "expected": True},
    {"id": "bool_revert-str-0", "func": "bool_revert", "args": ["0"], "expected": False},

    # --- bool_to_string ---
    {"id": "bool_to_string-True", "func": "bool_to_string", "args": [True], "expected": "1"},
    {"id": "bool_to_string-yes", "func": "bool_to_string", "args": ["yes"], "expected": "1"},
    {"id": "bool_to_string-no", "func": "bool_to_string", "args": ["no"], "expected": "0"},

    # --- check_ip: valid passes through, invalid is empty, None errors out ---
    {"id": "check_ip-valid", "func": "check_ip", "args": ["10.141.0.1"], "expected": "10.141.0.1"},
    {"id": "check_ip-list", "func": "check_ip", "args": ["10.141.0.1, 10.141.0.2"],
     "expected": "10.141.0.1,10.141.0.2"},
    {"id": "check_ip-invalid", "func": "check_ip", "args": ["not.an.ip"], "expected": ""},
    {"id": "check_ip-none", "func": "check_ip", "args": [None], "expected": None},

    # --- check_if_ipv6 ---
    {"id": "ipv6-true", "func": "check_if_ipv6", "args": ["fe80::1"], "expected": True},
    {"id": "ipv6-false", "func": "check_if_ipv6", "args": ["10.0.0.1"], "expected": False},

    # --- network math ---
    {"id": "get_network-cidr", "func": "get_network", "args": ["10.141.0.5", "255.255.255.0"],
     "expected": "10.141.0.0/24"},
    {"id": "get_network-none", "func": "get_network", "args": [None], "expected": None},
    {"id": "get_netmask-16", "func": "get_netmask", "args": ["10.141.0.0/16"],
     "expected": "255.255.0.0"},
    {"id": "get_network_details", "func": "get_network_details", "args": ["10.141.0.0/16"],
     "expected": {"network": "10.141.0.0", "subnet": "16"}},
    {"id": "get_network_size-24", "func": "get_network_size", "args": ["10.141.0.0", "24"],
     "expected": 254},
    {"id": "get_ip_range_size", "func": "get_ip_range_size", "args": ["10.141.0.1", "10.141.0.10"],
     "expected": 9},
    {"id": "get_ip_range_size-bad", "func": "get_ip_range_size", "args": ["x", "y"], "expected": 0},

    # --- list / dict helpers ---
    {"id": "dedupe", "func": "dedupe_adjacent", "args": [[1, 1, 2, 2, 3, 1]], "expected": [1, 2, 3]},
    {"id": "getlist", "func": "getlist", "args": [{"a": 1, "b": 2}], "expected": ["a", "b"]},
    {"id": "compare_list-subset", "func": "compare_list", "args": [["a"], ["a", "b"]], "expected": True},
    {"id": "compare_list-missing", "func": "compare_list", "args": [["c"], ["a", "b"]], "expected": False},
    {"id": "convert_list_to_dict", "func": "convert_list_to_dict",
     "args": [[{"name": "n1", "v": 1}], "name"], "expected": {"n1": {"name": "n1", "v": 1}}},

    # --- hostlist expansion ---
    {"id": "hostlist-range", "func": "get_hostlist", "args": ["node[001-003]"],
     "expected": ["node001", "node002", "node003"]},
    {"id": "hostlist-single", "func": "get_hostlist", "args": ["controller"],
     "expected": ["controller"]},
]
