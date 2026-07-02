#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data-driven test cases for utils.config.Config methods.

Only the pure (input-in, value-out) methods belong here. Most of Config is
database/template integration and is out of scope for unit tests. To add a
pure Config method, append a dict to CASES -- tests/unit/test_config.py runs
every entry. See tests/README.md for the field reference.
"""

CASES = [
    # --- normalize_ipxe_kernel: case-folds, accepts default/alternative, else falls back ---
    {"id": "ipxe-norm-default", "func": "normalize_ipxe_kernel", "args": ["Default"],
     "expected": "default"},
    {"id": "ipxe-norm-alternative", "func": "normalize_ipxe_kernel", "args": ["ALTERNATIVE"],
     "expected": "alternative"},
    {"id": "ipxe-norm-whitespace", "func": "normalize_ipxe_kernel", "args": ["  default  "],
     "expected": "default"},
    {"id": "ipxe-norm-none", "func": "normalize_ipxe_kernel", "args": [None], "expected": None},
    {"id": "ipxe-norm-empty", "func": "normalize_ipxe_kernel", "args": [""], "expected": None},
    {"id": "ipxe-norm-unknown-falls-back", "func": "normalize_ipxe_kernel", "args": ["nonsense"],
     "expected": "default"},

    # --- ipxe_bootfiles: returns the architecture filenames for the selected kernel ---
    {"id": "ipxe-bootfiles-default", "func": "ipxe_bootfiles", "args": ["default"],
     "expected": {"class": "ipxe-kernel-default",
                  "x86_64": "luna_ipxe.efi", "arm64": "luna_ipxe_arm64.efi"}},
    {"id": "ipxe-bootfiles-alternative", "func": "ipxe_bootfiles", "args": ["alternative"],
     "expected": {"class": "ipxe-kernel-alternative",
                  "x86_64": "luna_snponly.efi", "arm64": "luna_snponly_arm64.efi"}},
    {"id": "ipxe-bootfiles-unknown-uses-default", "func": "ipxe_bootfiles", "args": ["bogus"],
     "expected": {"class": "ipxe-kernel-default",
                  "x86_64": "luna_ipxe.efi", "arm64": "luna_ipxe_arm64.efi"}},

    # --- dhcp_reservation_nextserver: look up next-server in normal then shared subnets ---
    {"id": "nextserver-in-subnets", "func": "dhcp_reservation_nextserver",
     "args": ["net1", {"net1": {"nextserver": "1.2.3.4", "nextport": "69"}}, {}],
     "expected": {"server": "1.2.3.4", "port": "69"}},
    {"id": "nextserver-in-shared", "func": "dhcp_reservation_nextserver",
     "args": ["net2", {}, {"share": {"net2": {"nextserver": "5.6.7.8", "nextport": "80"}}}],
     "expected": {"server": "5.6.7.8", "port": "80"}},
    {"id": "nextserver-missing", "func": "dhcp_reservation_nextserver",
     "args": ["absent", {}, {}], "expected": {"server": None, "port": None}},
]
