#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1955: the boot-time BMC plugins for vendors other than Dell.

Two vendors need a tool of their own before ipmitool can work at all, and for the
same reason: an XClarity Controller ships with IPMI-over-LAN switched off, and so
does iLO. A fresh machine of either kind cannot be reached over the network by
ipmitool until something in band turns that on - OneCLI and hponcfg respectively.

The properties worth holding are about shape rather than about any one command,
because none of it can be run here: there is no XCC and no iLO on a test box. What
can be checked is that a vendor plugin only ever adds to the generic flow, never
replaces or removes it, and that it degrades to exactly today's behaviour on a
machine where the vendor tool is absent.
"""

import ast
import importlib
import os
import re

import pytest

BMC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'daemon', 'plugins', 'boot', 'bmc')

# every vendor file that composes onto default.py, and what it is
COMPOSED = {
    'lenovo': 'onecli',
    'hpe': 'hponcfg',
    'hp': 'hponcfg',
    'hewlett': 'hponcfg',
    'ibm': 'onecli',
}
ALIASES = {'hp': 'hpe', 'hewlett': 'hpe', 'ibm': 'lenovo'}


def shipped():
    return sorted(name[:-3] for name in os.listdir(BMC)
                  if name.endswith('.py') and not name.startswith('_'))


def plugin(name):
    return importlib.import_module(f'plugins.boot.bmc.{name}').Plugin()


def source(name):
    with open(os.path.join(BMC, f'{name}.py'), 'r', encoding='utf-8') as handle:
        return handle.read()


# --- the contract the README calls mandatory --------------------------------

@pytest.mark.parametrize('name', shipped())
def test_every_plugin_exposes_a_config_segment(name):
    """
    The README says one variable is mandatory. A plugin without it raises inside
    base/boot.py while a node is being provisioned, which is the worst place to
    find out.
    """
    config = plugin(name).config
    assert isinstance(config, str) and config.strip(), f'{name}.py has no usable config'


# --- a vendor plugin adds, it does not replace ------------------------------

@pytest.mark.parametrize('name', sorted(COMPOSED))
def test_a_vendor_plugin_contains_the_generic_flow_verbatim(name):
    """
    The point of composing rather than copying. A vendor file that restates the
    generic bootstrap owns a private fork of it, and the two drift: a fix lands in
    one and the node runs the other. Containing it verbatim means a change to
    default.py reaches every vendor at once.
    """
    assert plugin('default').config in plugin(name).config


@pytest.mark.parametrize('name', sorted(COMPOSED))
def test_the_vendor_block_runs_before_the_generic_flow(name):
    """
    Order is the whole point, not a detail. The generic flow talks to the BMC over
    IPMI, and on both of these vendors IPMI-over-LAN is off until the vendor tool
    turns it on. Putting the vendor block second would make it useless.
    """
    config = plugin(name).config
    assert config.index(COMPOSED[name]) < config.index(plugin('default').config)


@pytest.mark.parametrize('name,parent', sorted(ALIASES.items()))
def test_an_alias_is_the_same_plugin_as_the_vendor_it_names(name, parent):
    """
    A board reports what it reports: 'HP' on older HPE machines, and an x86 'IBM'
    is Lenovo hardware since 2014. These exist so the search path lands somewhere
    rather than falling through to default, and they must not drift from the file
    they alias.
    """
    assert plugin(name).config == plugin(parent).config


# --- degrading to exactly today's behaviour ---------------------------------

@pytest.mark.parametrize('name', sorted(COMPOSED))
def test_the_vendor_tool_is_optional(name):
    """
    A machine without the vendor tool must behave exactly as it does today. The
    block is wrapped in a command -v test, so on an image that does not carry the
    tool nothing in it runs at all.
    """
    config = plugin(name).config
    assert f'command -v {COMPOSED[name]}' in config


@pytest.mark.parametrize('name', sorted(COMPOSED))
def test_every_vendor_step_can_fail_without_taking_the_install_with_it(name):
    """
    Each step either clears the readiness flag or is swallowed, so a tool that is
    present but cannot talk to the BMC leaves the generic flow to run rather than
    aborting a provisioning run. A vendor plugin may add behaviour; it may never
    remove any.
    """
    config = plugin(name).config
    block = config[:config.index(plugin('default').config)]
    ready = re.findall(r'(\w+_READY)=0', block)
    assert ready, f'{name}: no readiness flag is ever cleared, so nothing degrades'
    for line in block.splitlines():
        stripped = line.strip()
        # an echo or a comment may name the tool without invoking it
        if stripped.startswith(('echo', '#')):
            continue
        if not stripped.startswith(COMPOSED[name]) and f' {COMPOSED[name]} ' not in stripped:
            continue
        assert ('||' in stripped or '2>&1' in stripped or stripped.startswith('if ')), (
            f'{name}: an unguarded vendor command could abort the install: {stripped}'
        )


# --- what we deliberately did not copy from the site script -----------------

@pytest.mark.parametrize('name', shipped())
def test_no_plugin_hardcodes_a_credential(name):
    """
    Credentials come from bmcsetup. The one exception is a vendor's PUBLISHED
    factory default, used only to get past a forced first-login change before the
    real password is set - that is documented where it appears, and it is not a
    secret.
    """
    text = source(name)
    literals = re.findall(r'--newpwd\s+["\']?([A-Za-z0-9!@#$%^&*]{6,})', text)
    invented = [value for value in literals if not value.startswith('${')]
    assert not invented, f'{name}.py passes a literal password: {invented}'


@pytest.mark.parametrize('name', shipped())
def test_no_plugin_hardcodes_a_vendor_install_path(name):
    """
    dell.py finds racadm with command -v and nothing else, and these follow it. A
    hardcoded /opt/<vendor>/... path is the shape that arrives from somebody's
    site script: it is right on the machine it was written on and wrong on the
    next one, and it silently stops finding a tool that moved.
    """
    paths = re.findall(r'/opt/[a-z]+/[A-Za-z0-9_.-]+', source(name))
    assert not paths, f'{name}.py hardcodes a vendor install path: {sorted(set(paths))}'


@pytest.mark.parametrize('name', shipped())
def test_no_plugin_carries_site_policy(name):
    """
    A BMC plugin configures the BMC. NTP servers, DNS servers, a timezone, a boot
    order and a password policy are all things a site decides and Luna configures
    elsewhere - they came with the script this was drawn from and were left there.
    """
    # the segment, not the module: a docstring that records what was deliberately
    # left out has to be able to name it
    text = plugin(name).config.lower()
    policy = [word for word in ('ntphost', 'dns_ip_address', 'timezone', 'bootorder',
                                'minpasswordlen', 'passwordreuse')
              if word in text]
    assert not policy, f'{name}.py carries site policy: {policy}'


# --- and the plugin is reachable at all -------------------------------------

def test_a_vendor_string_reaches_the_file_that_handles_it():
    """
    The whole reason these files can exist now. Until the search path carried the
    manufacturer, a vendor plugin loaded only for a site that happened to name a
    node after the vendor.
    """
    from utils.redfish import RedfishAccess

    access = RedfishAccess()
    for reported, expected in (('Lenovo', 'lenovo'), ('HPE', 'hpe'), ('HP', 'hp'),
                               ('Hewlett Packard Enterprise', 'hewlett'),
                               ('IBM', 'ibm'), ('Dell Inc.', 'dell')):
        token = access.token(reported)
        assert token == expected, f'{reported!r} -> {token!r}, expected {expected!r}'
        assert os.path.exists(os.path.join(BMC, f'{token}.py')), (
            f'{reported!r} normalises to {token!r} and no {token}.py exists'
        )
