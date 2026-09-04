#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Every state an installer reports has to be one the daemon recognises.

Monitor.node_state is a hand-written list beside the install templates that do the
reporting. Two lists describing the same thing drift, and this one drifts silently:
an unlisted state is not rejected, it falls through installer_state() and is tagged
404 - neither ok nor failed - for as long as the node sits in it.

That has happened. lpart reports three phases of its own and none of them were in
the list, so a node installed by lpart was unrecognised for its entire install, and
the longest phase of the boot was the one nobody could see.

So the templates are the source of truth here and the list is checked against them,
rather than either being named twice.
"""

import os
import re

import pytest

from utils.monitor import Monitor

TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates')

# install.lpart.${LUNAPHASE} is built at run time from the phase the template asks
# lpart for, so the literal never appears. These are the phases it passes.
LPART_PHASES = ('pre', 'part', 'post')


def _reported_states():
    """Every state the install templates hand to update_status."""
    states = set()
    for name in sorted(os.listdir(TEMPLATES)):
        if not name.startswith('templ_install') and name != 'templ_post_boot.cfg':
            continue
        with open(os.path.join(TEMPLATES, name), 'r', encoding='utf-8') as handle:
            body = handle.read()
        for state in re.findall(r'"(install\.[A-Za-z_.${}]+)"', body):
            if '${LUNAPHASE}' in state:
                states.update(state.replace('${LUNAPHASE}', phase) for phase in LPART_PHASES)
            else:
                states.add(state)
    return states


def test_the_templates_report_something():
    """A regex that matches nothing would make every assertion below vacuous."""
    states = _reported_states()
    assert len(states) > 10, states
    assert 'install.unpack' in states
    assert 'install.lpart.part' in states


@pytest.mark.parametrize('state', sorted(_reported_states()))
def test_every_reported_state_is_known(state):
    """
    Unknown is not an error anyone sees - installer_state() returns the state with a
    404 and the node reads as neither installing nor failed.
    """
    known = set(Monitor().node_state[204]) | set(Monitor().node_state[500])
    if state == 'install.lpart_unavailable':
        pytest.skip('a warning the next step overwrites, deliberately not a state')
    assert state in known, f'{state} is reported by a template and unknown to the daemon'
