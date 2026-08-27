#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: what a real board publishes, and what that breaks.

The staging and grab logic was written against a fake BMC that behaves the way
the DMTF schema says a BMC behaves. The first real hardware disagreed with it in
two ways that mattered, and both are pinned here against a captured registry
rather than against an argument:

  the registry flags are ABSENT, not false. Of IsSystemUniqueProperty, Immutable
  and WriteOnly, not one appears on a single entry of this board's 104. Only
  ReadOnly does. The exclude list is therefore the primary filter and not a
  belt-and-braces one - and the exclude list, being name based, matched nothing
  at all while an attribute called FBO204 sat there holding the machine's MAC.

  the allowable reset types are published only by @Redfish.ActionInfo. Reading
  only the inline annotation makes such a board look like one that publishes
  nothing, and it is then sent a guess.

The fixtures are a real GIGABYTE R181-Z91-00 (AMI) as captured, with the MAC
addresses replaced. Nothing else about them is edited - the point of a capture is
that it is not tidied into agreeing with us.
"""

import json
import os

import pytest

from utils.bios import Bios as BiosPlanner, DEFAULT_EXCLUDE, UNPORTABLE

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def load(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as handle:
        return json.load(handle)


@pytest.fixture(name='registry')
def registry_fixture():
    return load('gigabyte-bios-registry.json')


@pytest.fixture(name='attributes')
def attributes_fixture():
    return load('gigabyte-bios.json')['Attributes']


# --- what the board actually says -------------------------------------------

def test_the_registry_flags_we_filter_on_are_absent_not_false(registry):
    """
    Not one of the three flags that answer "may this be copied" is set, and two
    of them do not appear on any entry at all. This is the reason the value check
    and the exclude list exist; if a board ever does set them this test says so by
    failing, which is the good kind of failure.
    """
    entries = BiosPlanner().attributes(registry=registry)
    assert len(entries) == 104
    present = {flag: sum(1 for entry in entries.values() if flag in entry)
               for flag, _ in UNPORTABLE}
    assert present['IsSystemUniqueProperty'] == 0, (
        'the whole grab design assumed this flag might carry the filter; on the '
        'first real board it is not present on a single attribute'
    )
    assert present['Immutable'] == 0
    assert present['WriteOnly'] == 0
    assert present['ReadOnly'] == 104, 'the one flag that is real'


def test_the_seeded_exclude_list_matches_nothing_on_this_board(registry, attributes):
    """
    Every pattern in the seeded list is a name, and this board's names are codes.
    The list is not wrong - it is simply inert here, which is exactly why it
    cannot be the only thing standing between one machine's identity and another.
    """
    planner = BiosPlanner()
    _, dropped = planner.portable(registry=registry, attributes=attributes,
                                  exclude=list(DEFAULT_EXCLUDE))
    assert not [why for why in dropped.values() if why.startswith('excluded by')]


# --- the leak, and the fix that closes it -----------------------------------

def test_a_boot_entry_holding_a_mac_is_not_carried_to_another_machine(
        registry, attributes):
    """
    FBO204 is writable, described by the registry, named nothing in particular,
    and its value is this machine's MAC. Nothing but the value itself says so.
    """
    assert 'AA:BB:CC:DD:EE:FF' in attributes['FBO204']
    kept, dropped = BiosPlanner().portable(registry=registry,
                                           attributes=attributes,
                                           exclude=list(DEFAULT_EXCLUDE))
    assert 'FBO204' not in kept, (
        'this is the whole finding: no registry flag and no name pattern stops '
        'one nodeMAC being pushed into another node boot order'
    )
    assert dropped['FBO204'] == 'the value carries a MAC address'


def test_the_rest_of_the_board_still_comes_across(registry, attributes):
    """
    A filter that drops the leak and takes half the configuration with it has
    swapped one silent failure for another. Only the four the registry objects to
    and the one that carries a MAC may go.
    """
    kept, dropped = BiosPlanner().portable(registry=registry,
                                           attributes=attributes,
                                           exclude=list(DEFAULT_EXCLUDE))
    assert len(kept) == 101
    assert sorted(dropped) == ['FBO204', 'MAPIDS', 'REDF005', 'REDF006', 'SETUP006']
    assert dropped['REDF005'] == 'read-only'
    assert dropped['MAPIDS'] == 'not described by the attribute registry'


@pytest.mark.parametrize('value,shape', [
    ('Network:UEFI: PXE IP4 Intel(R) Network B4:2E:99:BA:D5:A5', 'a MAC address'),
    ('B4-2E-99-BA-D5-A5', 'a MAC address'),
    ('20:00:00:25:b5:00:00:1f', 'a world wide name'),
    ('4C4C4544-0037-3010-8054-B7C04F464331', 'a UUID'),
])
def test_the_shapes_that_are_identity_wherever_they_appear(value, shape):
    assert BiosPlanner().identity(value=value) == shape


@pytest.mark.parametrize('value', [
    'UEFI', 'Enabled', 'Auto', '1 Step', 'F25', '2.15.1', 'Hard Disk',
    '0x0002', '115200', 'AA:BB', 'ff', '06', 'Intel(R) Xeon(R) Gold 6248R',
])
def test_ordinary_settings_are_not_mistaken_for_identity(value):
    """
    The other half of the bargain. Dropping a legitimate attribute shrinks a
    configuration just as silently as carrying a MAC pollutes one, so the shapes
    are deliberately narrow rather than clever.
    """
    assert BiosPlanner().identity(value=value) is None


def test_every_value_this_board_publishes_is_judged_the_same_way(
        registry, attributes):
    """
    Across all 106, two carry identity and 104 do not. A pattern that had grown
    too eager would show up here as a third.

    The two are worth telling apart. SETUP006 holds the whole boot order as one
    string and would have been dropped anyway for not being in the registry;
    FBO204 is described, writable and unremarkable, and the value is the only
    thing about it that objects. Only one of the two needed this check - which is
    the argument for having it, not against.
    """
    planner = BiosPlanner()
    carriers = sorted(name for name, value in attributes.items()
                      if planner.identity(value=value))
    assert carriers == ['FBO204', 'SETUP006']
    assert len(attributes) == 106


# --- the display name, which is what a pattern can actually be written against

def test_a_pattern_matches_the_display_name_as_well_as_the_name(registry, attributes):
    """
    An operator reading this board sees "Boot Option #4", never FBO204. A list
    they cannot write a working pattern for is a list that does not work.
    """
    planner = BiosPlanner()
    assert planner.excluded(name='FBO204', patterns=['*boot option*'],
                            entry={'DisplayName': 'Boot Option #4'}) == '*boot option*'
    assert planner.excluded(name='FBO204', patterns=['*boot option*']) is None
    kept, dropped = planner.portable(registry=registry, attributes=attributes,
                                     exclude=['*Boot Option*'])
    assert 'FBO101' in dropped and 'FBO204' in dropped
    assert dropped['FBO101'] == 'excluded by *Boot Option*'
    assert 'FBO001' in kept, 'the boot MODE is not a boot option and must stay'


def test_the_seeded_list_is_not_widened_to_this_board(registry, attributes):
    """
    '*Boot Option*' would close this leak and take eight legitimate boot-order
    preferences with it, on the strength of one vendor's English. The value check
    takes the one that leaks. This test exists so that widening the seeded list
    has to be a decision rather than a drift.
    """
    assert not [p for p in DEFAULT_EXCLUDE if 'boot' in p.lower()]
    kept, _ = BiosPlanner().portable(registry=registry, attributes=attributes,
                                     exclude=list(DEFAULT_EXCLUDE))
    assert 'FBO101' in kept and 'FBO102' in kept


# --- staging, against what the board really published ------------------------

def test_the_dependency_cascade_is_real_and_only_ever_greys_or_hides(registry):
    planner = BiosPlanner()
    dependencies = planner.dependencies(registry=registry)
    assert len(dependencies) == 51
    properties = {entry['Dependency'].get('MapToProperty') for entry in dependencies}
    assert properties == {'GrayOut', 'Hidden'}, (
        'both are already in BLOCKING; a third would mean the planner is '
        'ignoring something the board is telling it'
    )


def test_two_stages_come_out_of_the_board_not_out_of_a_vendor_recipe(
        registry, attributes):
    """
    The legacy boot order is greyed out while the board is in UEFI mode, so it
    takes a reboot between setting the mode and setting the order. Nothing here
    knows what GIGABYTE is - it is read off the registry the board served.
    """
    status, stages = BiosPlanner().plan(
        registry=registry, current=attributes,
        desired={'FBO001': 'LEGACY', 'FBO101': 'Network', 'FBO102': 'Hard Disk'})
    assert status is True
    assert stages == [{'FBO001': 'LEGACY'},
                      {'FBO101': 'Network', 'FBO102': 'Hard Disk'}]


def test_it_refuses_what_the_board_says_cannot_be_reached(registry, attributes):
    """You cannot set a legacy boot order on a machine that is in UEFI mode."""
    status, reason = BiosPlanner().plan(registry=registry, current=attributes,
                                        desired={'FBO101': 'Network'})
    assert status is False
    assert 'FBO001' in reason


def test_a_gate_and_what_it_gates_both_land_before_the_gate_shuts(
        registry, attributes):
    """FBO201 is hidden once the board is in LEGACY mode, so it goes first."""
    status, stages = BiosPlanner().plan(
        registry=registry, current=attributes,
        desired={'FBO001': 'LEGACY', 'FBO201': 'Network'})
    assert status is True
    assert stages == [{'FBO001': 'LEGACY', 'FBO201': 'Network'}]
