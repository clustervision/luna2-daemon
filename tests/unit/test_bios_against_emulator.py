#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: our Redfish client against somebody else's Redfish service.

Every other test here runs against a fake we wrote, and a fake we wrote can only
ever agree with what we believe Redfish does. This one talks over real HTTP to
sushy-tools' emulator - the same emulator Ironic's CI runs against - so the
routes, the @Redfish.Settings annotation, the settings object pointer, the JSON
shapes and the error bodies are all somebody else's reading of the specification
rather than ours.

**It does not replace tests/unit/test_bios_push.py, and it proves less than that
file does about the feature itself.** sushy-tools models no pending area: its
BIOS PATCH route writes into the same store its BIOS GET route reads, so a write
takes effect with no reset at all. Staging is the property this whole feature
turns on, so the fake in test_bios_push.py - which stages, applies on reset, and
can silently drop an attribute - remains the one that tests the behaviour. This
file tests the plumbing underneath it.

Skipped unless an emulator is reachable, so the suite stays hermetic. To run it:

    python3 -m venv ~/sushy-emu-venv
    ~/sushy-emu-venv/bin/pip install sushy-tools
    ~/sushy-emu-venv/bin/python tests/emulator/launch.py

Point it elsewhere with LUNA_REDFISH_EMULATOR=host:port.
"""

import os
import socket

import pytest

from base.bios import Bios as BaseBios
from utils.bios import Bios as Planner
from utils.bios_push import BiosPush
from utils.redfish import Redfish

EMULATOR = os.environ.get('LUNA_REDFISH_EMULATOR', '127.0.0.1:8000')
HOST, _, PORT = EMULATOR.partition(':')
PORT = int(PORT or 80)
SYSTEM = os.environ.get('LUNA_REDFISH_EMULATOR_SYSTEM',
                        '27946b59-9e44-4fa7-8e91-f3527a1ef094')


def reachable():
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not reachable(), reason=f'no Redfish emulator on {EMULATOR}')


@pytest.fixture(name='redfish')
def redfish_fixture():
    """A client, and a machine put back the way it was found afterwards."""
    client = Redfish(device=HOST, username='', password='',
                     scheme='http', port=PORT, verify=False)
    yield client
    client.call(method='POST',
                path=f'/redfish/v1/Systems/{SYSTEM}/BIOS/Actions/Bios.ResetBios')


# --- the plumbing, against an implementation we did not write ---------------

def test_our_client_reads_an_independent_service(redfish):
    status, path, system = redfish.system()
    assert status, system
    assert system.get('PowerState')
    assert (system.get('Bios') or {}).get('@odata.id')


def test_the_reset_type_is_negotiated_over_the_wire(redfish):
    """
    A board that does offer GracefulRestart, which neither real machine we have
    access to does - so the preference order is only exercised here.
    """
    _, _, system = redfish.system()
    wanted, target, allowed = BiosPush().reset_type(system=system, redfish=redfish)
    assert 'GracefulRestart' in allowed
    assert wanted == 'GracefulRestart'
    assert target


def test_the_settings_object_is_discovered_not_guessed(redfish):
    status, _, bios = BiosPush().bios_resource(redfish=redfish)
    assert status, bios
    assert BiosPush().settings_path(bios=bios) == \
        f'/redfish/v1/Systems/{SYSTEM}/BIOS/Settings'


def test_a_machine_naming_a_registry_it_does_not_publish_is_refused(redfish):
    """
    Not a contrived case: this emulator's BIOS resource names
    'BiosAttributeRegistryP89.v1_0_0' while its registry collection publishes
    'BiosAttributeRegistry.v1_0_0'. Guessing the path from the name would have
    produced a confident wrong answer; resolving through the collection produces
    a refusal, which is correct - a configuration we cannot filter is one we
    would push identity values out of.
    """
    _, _, bios = BiosPush().bios_resource(redfish=redfish)
    status, reason = BaseBios().registry(redfish=redfish, bios=bios)
    assert status is False
    assert 'not published by this machine' in reason


def test_a_write_and_a_read_back_over_real_http(redfish):
    status, _, bios = BiosPush().bios_resource(redfish=redfish)
    settings = BiosPush().settings_path(bios=bios)
    assert bios['Attributes']['QuietBoot'] == 'Enabled'

    status, _, _ = redfish.call(method='PATCH', path=settings,
                                payload={'Attributes': {'QuietBoot': 'Disabled'}})
    assert status

    _, _, after = BiosPush().bios_resource(redfish=redfish)
    assert Planner().unapplied(wanted={'QuietBoot': 'Disabled'},
                               attributes=after['Attributes']) == {}


def test_this_emulator_does_not_stage_and_that_is_why_the_fake_stays(redfish):
    """
    Pinned deliberately. If sushy-tools ever grows a pending area this test
    fails, and that is worth knowing - it would make the emulator able to test
    the part of the feature it currently cannot.
    """
    _, _, bios = BiosPush().bios_resource(redfish=redfish)
    settings = BiosPush().settings_path(bios=bios)
    redfish.call(method='PATCH', path=settings,
                 payload={'Attributes': {'ProcVirtualization': 'Disabled'}})
    _, _, after = BiosPush().bios_resource(redfish=redfish)
    assert after['Attributes']['ProcVirtualization'] == 'Disabled', (
        'applied with no reset at all - sushy-tools writes the settings object '
        'straight into the current attributes, so staging is untestable here'
    )


def test_a_reset_really_goes_out(redfish):
    status, reason = BiosPush().reset(redfish=redfish)
    assert status, reason
    assert reason == 'GracefulRestart'
