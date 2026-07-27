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
Client/daemon compatibility across versions.

A cluster is upgraded in pieces: the controller moves first, the osimages follow
whenever someone rebuilds them. So all four combinations are live in the field, and
three of them mix versions:

  old client + old daemon   the baseline
  old client + NEW daemon   an osimage nobody has rebuilt yet, booting off a 2.2
                            controller. Must install exactly as it did before.
  NEW client + old daemon   a rebuilt osimage booting off a controller still on 2.1.
                            Must install; the lpart tooling simply goes unused.
  NEW client + NEW daemon   the target.

The node's whole coupling to the daemon is two calls -- a token from /tpm/<node>, then
/boot/install/<node>, whose body it executes. So compatibility comes down to what that
rendered script contains, and these tests pin the properties that keep it safe:

  * the classic installer never mentions the install-model variables, so a 2.2 daemon
    passing three extra render variables cannot change a byte of what an old client
    receives;
  * an unset or 'legacy' install_mode keeps the classic installer, so an osimage that
    predates lpart is never handed an installer it cannot run;
  * when someone does point a pre-lpart osimage at the lpart installer, it fails loudly
    up front rather than part-way through partitioning a disk.
"""

import os
import re

import pytest

DAEMON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon'
)
TEMPLATES = os.path.join(DAEMON, 'templates')
CLASSIC = os.path.join(TEMPLATES, 'templ_install.cfg')
LPART = os.path.join(TEMPLATES, 'templ_install_lpart.cfg')
BOOT = os.path.join(DAEMON, 'base', 'boot.py')

INSTALL_MODEL_VARS = ['LUNA_INSTALL_MODE', 'LUNA_DISKLAYOUT_B64', 'LUNA_OSIMAGE_FILTER_B64']


def _read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


@pytest.mark.parametrize('variable', INSTALL_MODEL_VARS)
def test_classic_installer_never_mentions_the_install_model(variable):
    """
    OLD CLIENT + NEW DAEMON.

    The 2.2 boot route passes three extra variables to every install render. That is
    only harmless while the classic template never references them -- the moment one
    appears here, an osimage nobody has rebuilt starts receiving a different script
    from the same daemon.
    """
    assert variable not in _read(CLASSIC), (
        f'{variable} appears in the classic installer. An osimage that predates the '
        f'install-model would then get a different script from a 2.2 daemon than it '
        f'got from a 2.1 one, which is the compatibility guarantee this work rests on.'
    )


def test_classic_render_is_unaffected_by_the_extra_variables():
    """
    OLD CLIENT + NEW DAEMON, proven by rendering rather than by reading.

    Render the real classic template with the 2.1 variable set and with the 2.2 set,
    through the daemon's own b64decode filter, and require identical bytes.
    """
    from base64 import b64decode

    from jinja2 import Environment

    def _b64decode(value):
        try:
            decoded = b64decode(value)
        except Exception:                                   # noqa: BLE001 - mirrors the daemon
            return value
        try:
            return decoded.decode('ascii')
        except Exception:                                   # noqa: BLE001
            return decoded.decode('utf-8', 'replace')

    env = Environment()                                     # noqa: S701 - not HTML
    env.filters['b64decode'] = _b64decode
    template = env.from_string(_read(CLASSIC))

    old = dict(
        LUNA_CONTROLLER='10.0.0.1', LUNA_BEACON='10.0.0.1', LUNA_API_PORT='7050',
        LUNA_API_PROTOCOL='https', VERIFY_CERTIFICATE='False', WEBSERVER_PORT='7060',
        WEBSERVER_PROTOCOL='http', LUNA_LOGHOST='10.0.0.1', NODE_HOSTNAME='n1',
        NODE_NAME='n1', LUNA_GROUP='compute', LUNA_OSIMAGE='img',
        LUNA_DISTRIBUTION='redhat', LUNA_OSRELEASE='9', LUNA_SYSTEMROOT='sysroot',
        LUNA_IMAGEFILE='f.tar.bz2', LUNA_FILE='f.tar.bz2', LUNA_SELINUX_ENABLED='0',
        LUNA_SETUPBMC=False, LUNA_BMC={}, LUNA_ROLES='', LUNA_SCRIPTS='',
        LUNA_UNMANAGED_BMC_USERS='', LUNA_INTERFACES={}, LUNA_PRESCRIPT='',
        LUNA_PARTSCRIPT='', LUNA_POSTSCRIPT='', PROVISION_METHOD='torrent',
        PROVISION_FALLBACK='http', PROVISION_INTERFACE='BOOTIF',
    )
    # what a 2.2 daemon adds, including for a node someone has given lpart values
    new = dict(old, LUNA_INSTALL_MODE='full', LUNA_DISKLAYOUT_B64='eyJ2IjoyfQ==',
               LUNA_OSIMAGE_FILTER_B64='e30=')

    assert template.render(**old) == template.render(**new), (
        'the classic installer renders differently once the install-model variables are '
        'supplied, so a 2.2 daemon would hand an un-rebuilt osimage a script it has '
        'never seen.'
    )


def test_unset_install_mode_keeps_the_classic_installer():
    """
    OLD CLIENT + NEW DAEMON: nothing may opt a node in by omission.

    The switch must require a value that is set AND not 'legacy'. A bare
    `!= 'legacy'` test would route every node that never heard of the field, because
    the cascade default resolves rather than staying empty.
    """
    source = _read(BOOT)
    match = re.search(r'^\s*if not method and (.+?):\s*$', source, re.M)
    assert match, 'the lpart selection condition is not where this test expects it'
    condition = match.group(1)
    assert "data.get('install_mode')" in condition, (
        'the selection does not require install_mode to be set; an unset field must '
        'never select the lpart installer'
    )
    assert "!= 'legacy'" in condition, 'the selection no longer excludes legacy'


def test_lpart_installer_falls_back_when_the_osimage_cannot_run_it():
    """
    NEW DAEMON + OLD CLIENT, when someone opts a node in anyway.

    An osimage built before lpart has no lpart-node-installer. The installer decides
    this itself -- whether lpart is runnable is a property of the initramfs the node
    booted, which the daemon cannot see into -- reports it, and installs the classic
    way rather than looping on an error.

    The report is the part that matters: the node ends up with the layout partscript
    produced, NOT the lpart layout that was asked for, so the run must say so.
    """
    lpart = _read(LPART)
    assert 'command -v lpart-node-installer' in lpart, (
        'the lpart installer does not check that the osimage can actually run lpart'
    )
    guard = lpart.split('command -v lpart-node-installer')[1].split('LPART_FALLBACK=1')[0]
    assert 'install.lpart_unavailable' in guard, (
        'the fallback does not report a distinct status, so a node silently installed '
        'with the wrong disk layout looks identical to one that got what it asked for'
    )
    # The human-readable warning is echoed, not pushed through update_status: that field
    # is the node's *state* and the next step overwrites it, so a sentence does not belong
    # there. The echo lands on the install console and in the node's install log.
    echoed = '\n'.join(line for line in guard.splitlines() if line.strip().startswith('echo'))
    for phrase in ('FALLING BACK', 'NOT the', 'requested lpart layout',
                   'install_mode=legacy', 'lpart-node-installer'):
        assert phrase in echoed, f'the install output does not state: {phrase}'
    # ...and the state stays short, because a state is not a message
    states = re.findall(r'update_status "([^"]+)"', guard)
    assert states == ['install.lpart_unavailable'], (
        f'expected exactly one short state, got {states}. update_status sets the node '
        f'state and is overwritten by the next step; it is not a place for prose.'
    )
    assert 'lpart_phase' in lpart.split('command -v lpart-node-installer')[0][-500:], (
        'the capability check should sit inside lpart_phase, so every phase is covered'
    )


def test_lpart_is_never_reachable_without_the_daemon_choosing_it():
    """
    NEW CLIENT + OLD DAEMON.

    A 2.1 daemon renders the classic installer, which must contain no route into the
    lpart tooling -- otherwise a rebuilt osimage on an old controller could start a
    partitioning run nothing wrote inputs for.
    """
    classic = _read(CLASSIC)
    for token in ('lpart-node-installer', 'lpart_phase', 'lpart-phase'):
        assert token not in classic, (
            f'the classic installer references {token}. On a 2.1 controller that is the '
            f'only script a rebuilt osimage gets, and lpart would run with no '
            f'provisioning inputs written.'
        )
