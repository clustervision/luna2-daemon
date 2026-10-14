#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
lpart's exit class decides whether a node retries or parks. The state the installer
reports has to say the same, or `luna node show` hides why a node stopped.

Runs the template's own lpart_phase against a stub lpart-node-installer, so the
mapping is checked as bash executes it, not as the template reads.
"""

import os
import re
import shutil
import subprocess

import pytest

TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates', 'templ_install_lpart.cfg')

# (lpart exit code, marker left in runtime/, state reported after install.lpart.part)
CASES = [
    (0, None, None),
    (0, 'sanitize.done', 'install.sanitized'),
    (1, None, 'install.error'),
    (2, None, 'install.refused'),
    (2, 'degraded.done', 'install.degraded'),
    (3, None, 'install.fatal'),
]


def _lpart_phase():
    """lpart_phase and the park codes it compares against, as the template has them."""
    with open(TEMPLATE, 'r', encoding='utf-8') as handle:
        body = handle.read()
    match = re.search(r'^function lpart_phase \{\n.*?^\}\n', body, re.M | re.S)
    assert match, 'lpart_phase is not where this test expects it'
    codes = re.findall(r'^LUNA_[A-Z]+_RC=[0-9]+$', body, re.M)
    assert len(codes) == 2, codes
    return '\n'.join(codes) + '\n' + match.group(0)


@pytest.mark.parametrize('code, marker, state', CASES)
def test_an_lpart_stop_reports_its_class(tmp_path, code, marker, state):
    if shutil.which('bash') is None:
        pytest.skip('bash not available')
    install = tmp_path / 'install_files'
    (install / 'runtime').mkdir(parents=True)
    if marker:
        (install / 'runtime' / marker).write_text('')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    stub = bindir / 'lpart-node-installer'
    stub.write_text(f'#!/bin/sh\nexit {code}\n')
    stub.chmod(0o755)
    states = tmp_path / 'states'
    script = ('update_status() { echo "$1" >> "$STATES"; }\nLPART_FALLBACK=0\n'
              + _lpart_phase().replace('/tmp/install_files', str(install))
              + 'lpart_phase part\n')
    run = subprocess.run(['bash', '-c', script], capture_output=True, timeout=30,
                         env={'PATH': f'{bindir}:/usr/bin:/bin', 'STATES': str(states)})
    reported = states.read_text().split() if states.exists() else []
    assert run.returncode == code, run.stderr.decode('utf-8', 'replace')
    assert reported == ['install.lpart.part'] + ([state] if state else []), reported
