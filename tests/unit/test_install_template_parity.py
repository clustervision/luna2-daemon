#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Parity between the two install templates.

There are two installers -- templ_install.cfg (classic) and templ_install_lpart.cfg
(advanced partitioner) -- and install_mode decides which a node gets. Two templates
means two copies of the same ~700 lines, and that is a drift trap: a fix lands in the
one the author was looking at, and the other flow silently keeps the bug. It is not
hypothetical. The campaign's own lpart template had already lost update_inventory
(the TRIX-1750 in-band hardware discovery) before it was ever merged, so lpart nodes
would have reported no inventory and nothing would have said so.

The lpart template is therefore DERIVED from the classic one: every shared function is
byte-identical by construction, and the flows differ only in the call list. These tests
hold that shape, so the next drift is a red build instead of a regression on whichever
installer nobody booted.

Divergence is allowed in exactly two places, both asserted below:
  * two functions that exist only in the lpart template
  * the main execution flow, where lpart owns partitioning and image extraction
"""

import os
import re

import pytest

TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates',
)
CLASSIC = os.path.join(TEMPLATES, 'templ_install.cfg')
LPART = os.path.join(TEMPLATES, 'templ_install_lpart.cfg')

# Only these may exist in the lpart template and not the classic one.
LPART_ONLY_FUNCTIONS = {'lpart_phase', 'write_provisioning_inputs'}

# lpart-osimage-install owns the download and the extraction, so the lpart flow does
# not call these. Their BODIES stay identical to the classic ones -- the divergence is
# the call, not the code, which is what keeps the parity check total.
NOT_CALLED_UNDER_LPART = {'download_image', 'unpack_imagefile'}


def _read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def _functions(text):
    """{name: body} for every top-level `function name {` ... `}` block."""
    out = {}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r'^function ([a-z_][a-z0-9_]*)\s*\{', line)
        if not match:
            continue
        body = []
        for following in lines[index + 1:]:
            if following == '}':
                break
            body.append(following)
        out[match.group(1)] = '\n'.join(body)
    return out


def _flow(text):
    """The bare call list at the end of the file: the installer's execution order."""
    tail = text.split('echo "Luna2: installer script"')[-1]
    calls = []
    for line in tail.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('echo'):
            continue
        if stripped.startswith('{%') or stripped.startswith('{{'):
            continue
        calls.append(stripped.split()[0])
    return calls


def test_lpart_template_exists():
    assert os.path.isfile(LPART), (
        'templ_install_lpart.cfg is missing. install_mode routes every non-legacy node '
        'to it, so without the file those nodes cannot install.'
    )


def test_no_classic_function_is_missing_from_lpart():
    """The failure that already happened once: a function dropped from the fork."""
    classic, lpart = _functions(_read(CLASSIC)), _functions(_read(LPART))
    missing = sorted(set(classic) - set(lpart))
    assert not missing, (
        f'the lpart template is missing {missing}, which the classic template defines. '
        f'A function dropped from one installer is a feature that silently stops working '
        f'on that flow only -- this is exactly how update_inventory was lost.'
    )


def test_lpart_adds_only_the_expected_functions():
    classic, lpart = _functions(_read(CLASSIC)), _functions(_read(LPART))
    extra = set(lpart) - set(classic)
    assert extra == LPART_ONLY_FUNCTIONS, (
        f'the lpart template defines {sorted(extra)} beyond the classic template; '
        f'expected exactly {sorted(LPART_ONLY_FUNCTIONS)}. Anything else belongs in both '
        f'templates or in neither.'
    )


def test_every_shared_function_is_byte_identical():
    """The whole point: the templates may differ in call order, never in code."""
    classic, lpart = _functions(_read(CLASSIC)), _functions(_read(LPART))
    drifted = [name for name in sorted(set(classic) & set(lpart))
               if classic[name] != lpart[name]]
    assert not drifted, (
        f'these functions have drifted between the two installers: {drifted}. '
        f'The lpart template is derived from the classic one; a shared function must be '
        f'changed in both, or the two flows quietly behave differently.'
    )


def test_lpart_does_not_call_what_it_does_not_own():
    """lpart-osimage-install does the download and extraction; the flow must not repeat it."""
    called = set(_flow(_read(LPART)))
    overlap = sorted(called & NOT_CALLED_UNDER_LPART)
    assert not overlap, (
        f'the lpart flow still calls {overlap}, which lpart-osimage-install owns. '
        f'Running both would fetch or extract the image twice.'
    )


def test_lpart_arms_no_trap_for_what_it_does_not_own():
    """
    Not calling a function is not the same as disarming it. unpack_imagefile is armed
    as a SIGUSR1 handler in the classic template, so under lpart a signal from the fetch
    client would still run a classic `tar -xf` into the systemroot -- the very work
    lpart-osimage-install owns. Keeping the body (for parity) means the trap must go.
    """
    lpart = _read(LPART)
    for name in sorted(NOT_CALLED_UNDER_LPART):
        assert f'trap {name} ' not in lpart, (
            f'the lpart template still arms a trap for {name}, which it does not own. '
            f'A signal would run the classic body behind lpart\'s back.'
        )
    # and the classic template must keep its trap -- removing it there is a real change
    assert 'trap unpack_imagefile SIGUSR1' in _read(CLASSIC), (
        'the classic template lost its SIGUSR1 trap; that is a behaviour change to the '
        'legacy installer and not something this work should touch.'
    )


@pytest.mark.parametrize('path,label', [(CLASSIC, 'classic'), (LPART, 'lpart')])
def test_both_flows_report_inventory(path, label):
    """update_inventory is the one the fork dropped -- pin it on both flows."""
    assert 'update_inventory' in _flow(_read(path)), (
        f'the {label} installer does not call update_inventory, so nodes installed this '
        f'way report no in-band hardware inventory.'
    )


def test_lpart_flow_runs_each_phase_after_the_operator_hook():
    """
    The operator's pre/part/post fields stay the operator's; the template invokes lpart
    itself. That ordering is the reason there is no dual-usage hazard to guard against.
    """
    flow = _flow(_read(LPART))
    for hook, phase in (('prescript', 'pre'), ('partscript', 'part'), ('postscript', 'post')):
        assert hook in flow, f'{hook} missing from the lpart flow'
        assert 'lpart_phase' in flow, 'the lpart flow never invokes lpart_phase'
        hook_at = flow.index(hook)
        phases = [i for i, call in enumerate(flow) if call == 'lpart_phase']
        assert any(i > hook_at for i in phases), (
            f'no lpart phase runs after {hook}; lpart must be invoked by the template, '
            f'not by putting a shim in the operator\'s {hook} field.'
        )
