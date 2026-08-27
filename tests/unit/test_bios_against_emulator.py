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

It stages: a PATCH to the settings object lands in a pending area and is applied
on reset, which is the property a staged apply turns on and the reason this is
worth more than a fixture. That is on sushy-tools' master and not in 2.2.0 - see
tests/emulator/README.md, which is also why these want it installed from source.

**It still does not replace tests/unit/test_bios_push.py.** That fake can also
silently drop an attribute it accepted, which is the failure MAX_ATTEMPTS exists
for and the one nobody predicts. No emulator models a board quietly ignoring you.

Skipped unless an emulator is reachable, so the suite stays hermetic. To run it:

    python3 -m venv ~/sushy-emu-venv
    ~/sushy-emu-venv/bin/pip install \
        'sushy-tools @ git+https://opendev.org/openstack/sushy-tools'
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


def test_a_registry_named_in_one_field_and_published_under_another(redfish):
    """
    The case that found a bug in us rather than in anything else.

    This service's BIOS resource names 'BiosAttributeRegistryP89.v1_0_0'; its
    collection entry for that same registry says 'BiosAttributeRegistry.v1_0_0'
    and 'BiosAttributeRegistry1.0'; only the registry document itself agrees with
    the BIOS resource. We matched a single field and refused a registry that is
    published and findable - sushy, the reference client, indexes all of them.

    Both real boards we have seen say the same thing in all three fields, so
    nothing but a service this untidy would have shown it.
    """
    _, _, bios = BiosPush().bios_resource(redfish=redfish)
    assert bios['AttributeRegistry'] == 'BiosAttributeRegistryP89.v1_0_0'
    status, registry = BaseBios().registry(redfish=redfish, bios=bios)
    assert status is True, registry
    assert registry['Id'] == bios['AttributeRegistry']
    assert registry['RegistryEntries']['Attributes']


def test_a_write_is_staged_and_not_applied_until_a_reset(redfish):
    """
    The property the whole feature turns on, against an implementation that is
    not ours: the settings object holds it, the current attributes do not move,
    and the reset is what applies it.
    """
    _, _, before = BiosPush().bios_resource(redfish=redfish)
    settings = BiosPush().settings_path(bios=before)
    was = before['Attributes']['BootMode']
    assert was != 'Legacy', 'the test would prove nothing from this starting point'

    status, _, _ = redfish.call(method='PATCH', path=settings,
                                payload={'Attributes': {'BootMode': 'Legacy'}})
    assert status

    _, _, during = BiosPush().bios_resource(redfish=redfish)
    assert during['Attributes']['BootMode'] == was, 'applied without a reset'
    _, pending = redfish.get(path=settings)
    assert pending['Attributes']['BootMode'] == 'Legacy', 'not staged either'
    assert Planner().unapplied(wanted={'BootMode': 'Legacy'},
                               attributes=during['Attributes'])

    status, reason = BiosPush().reset(redfish=redfish)
    assert status, reason
    _, _, after = BiosPush().bios_resource(redfish=redfish)
    assert after['Attributes']['BootMode'] == 'Legacy'
    assert Planner().unapplied(wanted={'BootMode': 'Legacy'},
                               attributes=after['Attributes']) == {}


def test_a_reset_really_goes_out(redfish):
    status, reason = BiosPush().reset(redfish=redfish)
    assert status, reason
    assert reason == 'GracefulRestart'
