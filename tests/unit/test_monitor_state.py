#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
Unit tests for Monitor.installer_state — the node provisioning-state -> label mapper.

Covers the new post-install 'booted' state (TRIX-1221) alongside the existing
install.* states, so a regression in the mapping is caught without a live daemon.
utils/monitor has no imports, so this exercises the real code directly.
"""

import os
import sys

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
sys.path.insert(0, DAEMON)

from utils.monitor import Monitor


def test_booted_is_post_install_label():
    # 'booted' is reported by the real OS, so it gets its own label + 200, NOT the
    # "Luna installer:" prefix used for in-installer states.
    assert Monitor().installer_state("booted") == ("Booted", 200)


def test_install_states_still_map():
    m = Monitor()
    assert m.installer_state("install.success") == ("Luna installer: success", 200)
    assert m.installer_state("install.roles") == ("Luna installer: roles", 200)
    assert m.installer_state("install.error") == ("Luna installer: error", 500)


def test_unknown_state_passes_through():
    # Unknown states are returned verbatim with the default status.
    assert Monitor().installer_state("something.else") == ("something.else", 404)


if __name__ == "__main__":
    test_booted_is_post_install_label()
    test_install_states_still_map()
    test_unknown_state_passes_through()
    print("OK: monitor state mapping")
