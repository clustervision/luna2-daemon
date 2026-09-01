#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2049: every control plugin waits on a BMC for the same length of time.

The single-node control routes talk to the BMC inline in the API request worker,
so this timeout is not merely how long we wait for one machine - it is how long
that worker is unavailable to everybody else. Measured on the test pair with six
workers: twelve concurrent stuck BMC calls took an unrelated /config/node from
0.02s to 17s, following

    probe wait ~= ceil(N / workers) x timeout - 3s

second for second. The number is therefore the size of the outage a dead BMC can
cause, which is why the plugins are held to one value rather than each carrying
its own. They used to disagree - 10s for ipmitool, 20s for the Redfish control
plugin - and nothing recorded why.

Deliberately NOT covered: utils/redfish.py's own default. That client is shared
with inventory, BIOS and firmware, which run off the request path and include
uploads that legitimately take minutes. Shortening it would change those, not
this defect.
"""

import re
from pathlib import Path

CONTROL_PLUGINS = Path(__file__).resolve().parents[2] / 'daemon' / 'plugins' / 'control'

# The blessed value. A change here is a change to how long a dead BMC can hold an
# API worker, so it should be a deliberate edit with a number behind it.
AGREED_TIMEOUT = 10


def bmc_timeouts():
    """Every BMC wait in every control plugin, found rather than listed."""
    found = {}
    for plugin in sorted(CONTROL_PLUGINS.glob('*.py')):
        text = plugin.read_text(encoding='utf-8')
        values = [int(v) for v in re.findall(r'\btimeout\s*=\s*(\d+)', text)]
        values += [int(v) for v in re.findall(r'runcommand\([^)]*?,\s*(\d+)\s*\)', text)]
        if values:
            found[plugin.name] = values
    return found


def test_the_control_plugins_are_actually_being_read():
    """
    Guard the guard. A regex that matches nothing makes every assertion below
    pass while proving nothing, which is how this class of test rots silently.
    """
    found = bmc_timeouts()
    assert found, f'no BMC timeout found in any plugin under {CONTROL_PLUGINS}'
    assert 'default.py' in found, 'the ipmitool plugin has no timeout the test can see'
    assert 'redfish.py' in found, 'the Redfish control plugin has no timeout the test can see'


def test_every_control_plugin_waits_the_same_length_of_time():
    """
    The class this closes: the next control plugin arriving with its own number.
    Every plugin in the directory is checked, not the two that happened to differ.
    """
    found = bmc_timeouts()
    disagreeing = {name: vals for name, vals in found.items()
                   if any(v != AGREED_TIMEOUT for v in vals)}
    assert not disagreeing, (
        f'a control plugin waits on a BMC for something other than {AGREED_TIMEOUT}s: '
        f'{disagreeing}. Every one of these runs inline in an API request worker, so '
        'the largest of them is how long one dead BMC can hold that worker.')
