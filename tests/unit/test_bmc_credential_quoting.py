#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
A BMC credential reaches the vendor tool intact, whatever characters it holds.

The plugins are bash spliced into the installer, and the daemon accepts any password
for a bmcsetup. An unquoted expansion splits a password with a space into two
arguments, and the HPE plugin writes the password into a RIBCL document, where a bare
& or < makes the XML invalid and iLO refuses it, leaving IPMI over LAN off. Both fail
silently from the controller's side: the install reports success either way.
"""

import os
import shlex
import subprocess
import xml.etree.ElementTree as ET

import pytest

from test_bmc_boot_plugin_flow import IPMITOOL, STATE, WANTED, _fake, plugin

PASSWORD = 'Qa 1955&x<y>z'

# logs every call one argument per tab, then behaves like the flow test's fake
ARGV_IPMITOOL = r'''#!/bin/bash
{ printf 'ipmitool'; for arg in "$@"; do printf '\t%s' "$arg"; done; echo; } >> "$SIM_ARGV"
exec "$SIM_REAL_IPMITOOL" "$@"
'''

# -w answers a readback with IPMI over LAN on; -f keeps the document it was given
HPONCFG = r'''#!/bin/bash
case "$1" in
  -w) printf '<RIBCL VERSION="2.0"><LOGIN><RIB_INFO><GET_GLOBAL_SETTINGS><IPMI_DCMI_OVER_LAN_ENABLED VALUE="Y"/></GET_GLOBAL_SETTINGS></RIB_INFO></LOGIN></RIBCL>\n' > "$2" ;;
  -f) cp "$2" "$SIM_RIBCL" ;;
esac
exit 0
'''


def run_plugin(tmp_path, name):
    bins = tmp_path / 'bin'
    bins.mkdir()
    _fake(bins / 'ipmitool', ARGV_IPMITOOL)
    _fake(tmp_path / 'ipmitool.real', IPMITOOL)
    _fake(bins / 'hponcfg', HPONCFG)
    state, log, argv, ribcl = (tmp_path / 'state', tmp_path / 'log', tmp_path / 'argv', tmp_path / 'ribcl.xml')
    state.write_text(STATE)
    log.write_text('')
    argv.write_text('')
    variables = ' '.join(f'{key}="{value}"' for key, value in WANTED.items())
    script = (
        'function config_bmc {\n' + plugin(name).config + '\n}\n'
        f'NETCHANNEL=1 MGMTCHANNEL=1 USERID=2 USERNAME=admin PASSWORD={shlex.quote(PASSWORD)} '
        f'UNMANAGED="" VLANID="" DHCP="False" {variables}\n'
        'modprobe() { :; }; sleep() { :; }; ls() { echo /dev/ipmi0; }\n'
        'config_bmc\n'
    )
    env = dict(os.environ, PATH=f'{bins}:{os.environ["PATH"]}', SIM_STATE=str(state), SIM_LOG=str(log),
               SIM_ARGV=str(argv), SIM_REAL_IPMITOOL=str(tmp_path / 'ipmitool.real'), SIM_RIBCL=str(ribcl),
               SIM_RAC_DIALECT='')
    subprocess.run(['bash', '-c', script], env=env, check=False, capture_output=True, timeout=60)
    return argv.read_text().splitlines(), ribcl


@pytest.mark.parametrize('name', ['default', 'dell', 'hpe', 'lenovo'])
def test_ipmitool_receives_the_password_as_one_argument(tmp_path, name):
    calls, _ = run_plugin(tmp_path, name)
    assert f'ipmitool\tuser\tset\tpassword\t2\t{PASSWORD}' in calls, calls


def test_the_ribcl_document_carries_the_password_as_valid_xml(tmp_path):
    _, ribcl = run_plugin(tmp_path, 'hpe')
    assert ribcl.exists(), 'hponcfg -f was never reached'
    login = ET.parse(ribcl).getroot().find('LOGIN')
    assert login.attrib['PASSWORD'] == PASSWORD
    assert login.attrib['USER_LOGIN'] == 'admin'
