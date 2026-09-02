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
KICKSTART = os.path.join(TEMPLATES, 'templ_install_kickstart.cfg')

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


def test_the_unpack_trap_is_legacy_only():
    """
    SIGUSR1 is Luna 1 heritage: a seeder once signalled the installer when the image had
    landed, and unpack_imagefile is the handler. Nothing raises it any more -- every
    provision plugin runs its fetch synchronously and returns an exit code, and lpart
    neither sends nor expects a signal (its only handling is SIGINT/SIGTERM in the TUI,
    to cancel). So the trap is vestigial.

    It stays in the classic template, because removing it would change the legacy
    installer for no reason. It does not go in the lpart template, because there is
    nothing there to want it: the fallback calls download_image and unpack_imagefile
    directly off LPART_FALLBACK, so the classic path runs without a signal.
    """
    lpart = _read(LPART)
    assert 'trap unpack_imagefile SIGUSR1' not in lpart, (
        'the lpart template arms the unpack trap. Nothing raises SIGUSR1 -- not the '
        'provision plugins, not lpart -- so the trap adds a second, signal-driven way '
        'into an extract that the fallback already calls directly.'
    )
    # what the fallback actually relies on: the flag, and the two explicit calls
    phase_body = _functions(lpart)['lpart_phase']
    assert 'LPART_FALLBACK=1' in phase_body, (
        'the fallback flag is not set in lpart_phase; the classic path is then unreachable'
    )
    for call in ('download_image', 'unpack_imagefile'):
        assert f'[ "$LPART_FALLBACK" = "1" ] && {call}' in lpart, (
            f'the fallback no longer calls {call}. Without it a node whose osimage '
            'predates lpart reports the fallback and then installs nothing.'
        )
    # and the classic template keeps its own top-level trap
    assert 'trap unpack_imagefile SIGUSR1' in _read(CLASSIC), (
        'the classic template lost its SIGUSR1 trap; that is a behaviour change to the '
        'legacy installer and not something this work should touch.'
    )


def test_lpart_falls_back_to_the_classic_fetch_only_behind_the_flag():
    """
    lpart-osimage-install owns download and extraction, so the lpart flow must not call
    the classic pair unconditionally -- only when lpart turned out to be unavailable and
    the installer chose the legacy path instead.
    """
    lpart = _read(LPART)
    tail = lpart.split('echo "Luna2: installer script"')[-1]
    for name in sorted(NOT_CALLED_UNDER_LPART):
        for line in tail.splitlines():
            if re.match(rf'^\s*{name}\b', line):
                raise AssertionError(
                    f'{name} is called unconditionally in the lpart flow; it must be '
                    f'guarded by the fallback flag, or lpart would fetch/extract twice.'
                )
        assert f'"$LPART_FALLBACK" = "1" ] && {name}' in tail, (
            f'{name} has no fallback-guarded call, so a node whose osimage cannot run '
            f'lpart would install with no image at all'
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


def test_install_context_carries_provision_fields():
    """lpart sources the download method (provision_method/fallback) and the
    provision interface from install-context.json rather than a daemon call, so the
    lpart template must materialise them there. Absent, a node that overrides the
    default provision_method would silently fall back to lpart's built-in default."""
    with open(LPART, encoding='utf-8') as handle:
        text = handle.read()
    for field, var in (
        ('provision_method', 'PROVISION_METHOD'),
        ('provision_fallback', 'PROVISION_FALLBACK'),
        ('provision_interface', 'PROVISION_INTERFACE'),
    ):
        needle = '"%s": "{{ %s }}"' % (field, var)
        assert needle in text, (
            f'templ_install_lpart.cfg install-context.json must write {field} '
            f'(expected {needle!r}); lpart reads it from that file.'
        )


def test_kickstart_exports_every_variable_the_classic_bmcsetup_sets():
    """
    The kickstart path runs the same spliced BMC plugin, but hands it its inputs
    as exports in %post rather than through bmcsetup. Two lists of the same
    variables drift: the classic template grew DHCP and the kickstart one did
    not, so the plugin read an empty string there and quietly configured static.
    Derived from the classic bmcsetup, so the next variable is covered too.
    """
    classic = _functions(_read(CLASSIC))['bmcsetup']
    names = re.findall(r'^\s*([A-Z]+)="\{\{', classic, re.M)
    assert names, 'bmcsetup no longer sets its variables inline'
    kickstart = _read(KICKSTART)
    block = kickstart[kickstart.index('{% if LUNA_SETUPBMC %}'):kickstart.index('## BMC CODE SEGMENT')]
    missing = [name for name in names if f'export {name}=' not in block]
    assert missing == [], f'kickstart %post does not export {missing} for the BMC plugin'
