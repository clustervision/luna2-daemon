#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
Unit tests for Monitor.installer_state — the node provisioning-state -> label mapper.

Covers the new post-install 'install.booted' state (TRIX-1221) alongside the existing
install.* states, so a regression in the mapping is caught without a live daemon.
utils/monitor has no imports, so this exercises the real code directly.
"""

import os
import re
import sys

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
sys.path.insert(0, DAEMON)

POST_BOOT = os.path.join(DAEMON, 'templates', 'templ_post_boot.cfg')

from utils.monitor import Monitor


def _state_the_post_boot_script_reports():
    """The state the installed OS actually POSTs, read from the script that POSTs it."""
    with open(POST_BOOT, encoding='utf-8') as handle:
        match = re.search(r'"state":\s*"([^"]+)"', handle.read())
    assert match, 'the post-boot script no longer reports a state'
    return match.group(1)


def test_booted_is_a_recognised_state():
    # The post-boot service reports once the installed OS is actually up. Read the
    # state out of the template rather than repeating it here: the sender and the
    # mapper are two halves of one contract, and a literal in this file would let
    # either half be renamed while the test carried on passing.
    state = _state_the_post_boot_script_reports()
    label, status = Monitor().installer_state(state)
    assert (label, status) == ('Luna installer: booted', 200), (
        f'the post-boot script reports {state!r}, which the daemon maps to '
        f'{(label, status)}. A state the daemon does not know falls through to the '
        f'404 branch and is shown to the operator raw.'
    )


def test_install_states_still_map():
    m = Monitor()
    assert m.installer_state("install.booted") == ("Luna installer: booted", 200)
    assert m.installer_state("install.success") == ("Luna installer: success", 200)
    assert m.installer_state("install.roles") == ("Luna installer: roles", 200)
    assert m.installer_state("install.error") == ("Luna installer: error", 500)


def test_unknown_state_passes_through():
    # Unknown states are returned verbatim with the default status.
    assert Monitor().installer_state("something.else") == ("something.else", 404)


if __name__ == "__main__":
    test_booted_is_a_recognised_state()
    test_install_states_still_map()
    test_unknown_state_passes_through()
    print("OK: monitor state mapping")
