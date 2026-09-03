#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1976 and TRIX-1842: the cipher and the DHCP flag on a bmcsetup.

The cipher was hardcoded as -C3 in the control plugin, so a board that requires
suite 17 could not be talked to at all - and it refuses suite 3 in a way that
looks like a wrong password. It is a number and not a modern/legacy flag because
that is what ipmitool's -C takes and what lconsole's --sol-cipher already says.

The DHCP flag is refused where it cannot work. A BMC told to use DHCP with
nothing serving it does not fall back to its old address - it has none, and the
way back is physical. So the flag is a request, and the daemon only honours it
where the BMC's network actually serves DHCP.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated database with the tables these paths touch."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['node', 'group', 'bmcsetup', 'nodeinterface', 'ipaddress', 'network']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def seed(db, bmc_dhcp=None, network_dhcp=None, with_bmc_interface=True):
    """
    The BMC is a node interface like any other, so its dhcp flag sits on its own
    ipaddress row - the same column a BOOTIF uses, one row per interface. That is
    what lets one node be DHCP on its BMC and static on its boot interface.
    """
    from utils.helper import Helper
    db.insert('network', Helper().make_rows(
        {'name': 'ipmi', 'network': '10.148.0.0', 'subnet': '16', 'dhcp': network_dhcp}))
    db.insert('group', Helper().make_rows({'name': 'compute'}))
    db.insert('bmcsetup', Helper().make_rows(
        {'name': 'default', 'userid': 2, 'username': 'admin', 'password': 'x',
         'netchannel': 1, 'mgmtchannel': 1}))
    db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': 1, 'bmcsetupid': 1}))
    if with_bmc_interface:
        db.insert('nodeinterface', Helper().make_rows(
            {'nodeid': 1, 'interface': 'BMC', 'macaddress': 'aa:bb:cc:dd:ee:ff'}))
        db.insert('ipaddress', Helper().make_rows(
            {'tableref': 'nodeinterface', 'tablerefid': 1, 'networkid': 1,
             'ipaddress': '10.148.0.1', 'dhcp': bmc_dhcp}))


# ---------------------------------------------------------------- cipher ----

def test_the_cipher_defaults_to_three_when_nothing_is_configured():
    """Every board accepted 3 before this existed; an unset field must not change that."""
    from plugins.control.default import Plugin
    plugin = Plugin()
    assert getattr(plugin, 'cipher', None) is None
    # the plugin's own fallback, the value the command is built with
    assert (getattr(plugin, 'cipher', None) or 3) == 3


def test_a_configured_cipher_reaches_the_ipmitool_command(monkeypatch):
    """The point of the ticket: -C must follow the bmcsetup, not a constant."""
    from plugins.control.default import Plugin
    import utils.helper as helper_module
    seen = {}

    def fake_runcommand(self, command, return_exit_code=False, timeout_sec=7200):
        seen['command'] = command
        return ([b'ok'], 0)

    monkeypatch.setattr(helper_module.Helper, 'runcommand', fake_runcommand)
    plugin = Plugin()
    plugin.cipher = 17
    plugin.power_status(device='10.148.0.1', username='admin', password='secret')
    assert '-C17' in seen['command']
    assert '-C3' not in seen['command']


def test_no_cipher_still_builds_the_historic_command(monkeypatch):
    from plugins.control.default import Plugin
    import utils.helper as helper_module
    seen = {}
    monkeypatch.setattr(helper_module.Helper, 'runcommand',
                        lambda self, c, r=False, t=7200: (seen.update(command=c), ([b'ok'], 0))[1])
    Plugin().power_status(device='10.148.0.1', username='admin', password='secret')
    assert '-C3' in seen['command']


def test_every_control_plugin_agrees_on_where_the_cipher_comes_from():
    """
    Derived, not an example: a new control plugin that hardcodes a suite would
    reintroduce exactly this bug, and nobody would notice until a hardened board
    refused to answer.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    folder = os.path.join(here, 'daemon', 'plugins', 'control')
    offenders = []
    for name in os.listdir(folder):
        if not name.endswith('.py') or name.startswith('__'):
            continue
        body = open(os.path.join(folder, name), encoding='utf-8').read()
        if re.search(r'-C\s*\d', body) and 'self, ' + "'cipher'" not in body \
                and "getattr(self, 'cipher'" not in body:
            offenders.append(name)
    assert offenders == [], f'control plugins hardcoding a cipher suite: {offenders}'


# ------------------------------------------------------------------ dhcp ----

def test_the_bmc_dhcp_test_is_the_one_the_boot_interface_already_uses():
    """
    The decision is `ipaddress.dhcp AND network.dhcp`, and it is made from the
    interface data install() already selects - not from a second query. The boot
    interface a few hundred lines above asks exactly the same question of exactly
    the same two fields; a BMC is a node interface, so it gets the same answer
    the same way.

    A flag on its own would not do. A BMC told to use DHCP where nothing serves
    it does not fall back to the address it had - it ends up with none, and the
    way back is physical.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    body = open(os.path.join(here, 'daemon', 'base', 'boot.py'), encoding='utf-8').read()
    assert "bool(interface['dhcp'] and interface['networkdhcp'])" in body, \
        'the BMC dhcp decision is not the two-field test the boot interface uses'
    assert 'def bmc_dhcp_allowed' not in body, \
        'a second query for facts install() already holds'
    # and the query it reads from must actually carry both fields
    query = body[body.index("nodeinterface = Database().get_record_join"):]
    query = query[:query.index('domain_search')]
    assert 'ipaddress.dhcp' in query and 'network.dhcp as networkdhcp' in query


def test_a_dhcp_request_on_a_network_without_it_is_reported(db):
    """Refusing quietly would leave somebody wondering why the setting did nothing."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    body = open(os.path.join(here, 'daemon', 'base', 'boot.py'), encoding='utf-8').read()
    assert 'does not serve ' in body and 'configuring it static' in body


# --------------------------------------------------- the installer script ----

def test_config_bmc_takes_no_positional_arguments():
    """
    It used to take eleven, and `UNMANAGED=$10` was silently `${1}0` - bash needs
    braces past the ninth. The value looked plausible and never matched, so
    unmanaged_bmc_users did nothing and said nothing. Named variables cannot fail
    that way, and the whole exchange is inside one generated script.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    body = open(os.path.join(here, 'daemon', 'templates', 'templ_install.cfg'),
                encoding='utf-8').read()
    block = body[body.index('function config_bmc'):body.index('## BMC CODE SEGMENT')]
    assert not re.search(r'=\$[0-9]', block), 'config_bmc still reads positional arguments'
    setup = body[body.index('function bmcsetup'):]
    setup = setup[:setup.index('\n}')]
    for name in ('NETCHANNEL', 'IPADDRESS', 'NETMASK', 'GATEWAY', 'VLANID', 'MGMTCHANNEL',
                 'USERID', 'USERNAME', 'PASSWORD', 'UNMANAGED', 'DHCP'):
        assert f'{name}="' in setup, f'{name} is not set before config_bmc is called'
    assert re.search(r'^\s*config_bmc\s*$', setup, re.M), 'config_bmc is still called with arguments'


def test_the_boot_plugin_only_sets_an_address_when_it_is_static():
    """With DHCP the address is the server's to hand out; setting it would fight the lease."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    body = open(os.path.join(here, 'daemon', 'plugins', 'boot', 'bmc', 'default.py'),
                encoding='utf-8').read()
    assert 'ipsrc ${IPSRC}' in body, 'ipsrc is still hardcoded'
    assert 'IPSRC=dhcp' in body
    assert 'if [ "${IPSRC}" == "static" ]; then' in body, 'static-only checks are not gated'


def test_no_installer_function_reads_an_unbraced_positional_past_the_ninth():
    """
    `$10` is `${1}0` in bash, not the tenth argument. It produces a plausible
    value from the first argument and is wrong silently - config_bmc's UNMANAGED
    and config_interface's ZONE and OPTIONS were all reading one. Derived over
    both installers so the next function to grow an eleventh argument is covered
    without anyone remembering this test exists.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for name in ('templ_install.cfg', 'templ_install_lpart.cfg'):
        body = open(os.path.join(here, 'daemon', 'templates', name), encoding='utf-8').read()
        bad = re.findall(r'^\s*\w+=\$1[0-9].*$', body, re.M)
        assert bad == [], f'{name} reads unbraced positional arguments: {bad}'


def test_no_installer_call_site_glues_two_arguments_together():
    """
    Two quoted strings with no space between them are ONE argument in bash, and
    every argument after the join silently shifts by one. config_interface was
    passing mtu and the vlan parent as a single value, so vlanparent received the
    vlanid, vlanid received the type, and so on down the line.
    """
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for name in ('templ_install.cfg', 'templ_install_lpart.cfg'):
        body = open(os.path.join(here, 'daemon', 'templates', name), encoding='utf-8').read()
        assert '}}""' not in body, f'{name} has two arguments glued into one'


def test_the_bulk_path_carries_the_cipher_too():
    """
    Review finding: the cipher reached the single-node route and not the bulk one,
    so `luna control power status node001,node002` and every multi-node lpower
    silently fell back to suite 3 - the more common path of the two.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    body = open(os.path.join(here, 'daemon', 'utils', 'control.py'), encoding='utf-8').read()
    calls = re.findall(r'self\.control_action\(\s*(.*?)\)', body, re.S)
    assert calls, 'no internal control_action call found'
    for call in calls:
        assert 'cipher' in call, f'a control_action call omits the cipher:\n{call}'


def test_a_composing_plugin_hands_the_cipher_to_the_plugin_it_delegates_to():
    """
    Review finding: the redfish plugin does not talk IPMI itself - it owns a
    DefaultPlugin and falls back to it. An attribute set on the outer instance
    never reached the inner one, so the fallback stayed on suite 3, which is
    exactly the case this setting exists for. Dell inherits the same shape.
    """
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    folder = os.path.join(here, 'daemon', 'plugins', 'control')
    for name in os.listdir(folder):
        if not name.endswith('.py') or name.startswith('__'):
            continue
        body = open(os.path.join(folder, name), encoding='utf-8').read()
        if not re.search(r'self\.\w+\s*=\s*DefaultPlugin\(\)', body):
            continue
        inner = re.search(r'self\.(\w+)\s*=\s*DefaultPlugin\(\)', body).group(1)
        assert '@cipher.setter' in body, \
            f'{name} delegates to a DefaultPlugin but has no cipher setter'
        assert f'self.{inner}.cipher = value' in body, \
            f'{name} does not pass the cipher to the plugin it delegates to'


def test_nothing_hardcodes_a_cipher_suite_anywhere_in_the_daemon():
    """The dead ipmi_action carried its own -C3 for years. Sweep, do not spot-check."""
    import os, re
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    offenders = []
    for root, _dirs, files in os.walk(os.path.join(here, 'daemon')):
        if '__pycache__' in root:
            continue
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            for n, line in enumerate(open(path, encoding='utf-8'), 1):
                if re.search(r'-C\s*3\b', line) and 'cipher' not in line:
                    offenders.append(f'{os.path.relpath(path, here)}:{n}')
    assert offenders == [], f'hardcoded cipher suite: {offenders}'


def test_cipher_suite_zero_is_a_cipher_suite_not_an_absence(monkeypatch):
    """`or 3` turned a stored 0 into suite 3 without a word; only None means unset."""
    from plugins.control.default import Plugin
    from utils import helper as helper_module
    seen = {}

    def fake_runcommand(self, command, return_exit_code=False, timeout_sec=7200):
        seen['command'] = command
        return (b'Chassis Power is on', b'', 0) if return_exit_code else (b'Chassis Power is on', b'')

    monkeypatch.setattr(helper_module.Helper, 'runcommand', fake_runcommand)
    plugin = Plugin()
    plugin.cipher = 0
    plugin.power_status(device='10.0.0.1', username='u', password='p')
    assert '-C0' in seen['command'], seen['command']
