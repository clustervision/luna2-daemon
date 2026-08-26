#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: working out how many reboots a BIOS change takes, and in what order.

Redfish stages BIOS attributes in a settings object and applies them on the next
reset. Some attributes cannot be written until another has already been applied,
so one payload is not always enough - the second half is refused until the first
half has been through a reboot.

The tempting answer is a per-model recipe. The machine already publishes the
relationship: the attribute registry's Dependencies say "if these attributes hold
these values, that attribute's ReadOnly / GrayOut / Hidden / Immutable becomes
this", which is exactly the cascade that forces the second payload. So the order
is derived, and these tests are about that derivation being faithful to the
schema rather than to any one vendor.

Everything here is a pure function of two documents. No BMC is involved, which is
the point - the ordering is the part that decides the architecture, and it can be
settled without hardware.
"""

import pytest

from utils.bios import Bios


def registry(dependencies=None):
    return {'RegistryEntries': {'Attributes': [], 'Dependencies': dependencies or []}}


def blocks(target, when_attribute, equals, prop='ReadOnly'):
    """A dependency that makes `target` unwritable while `when_attribute` == `equals`."""
    return {
        'DependencyFor': target,
        'Type': 'Map',
        'Dependency': {
            'MapFromAttribute': when_attribute,
            'MapToAttribute': target,
            'MapToProperty': prop,
            'MapToValue': True,
            'MapFrom': [{
                'MapFromAttribute': when_attribute,
                'MapFromProperty': 'CurrentValue',
                'MapFromCondition': 'EQU',
                'MapFromValue': equals,
            }],
        },
    }


# --- the simple cases, which are most machines ------------------------------

def test_a_machine_with_no_dependencies_takes_one_stage():
    """One PATCH, one reboot. This is what everything did before staging existed."""
    status, stages = Bios().plan(registry=registry(),
                                 desired={'BootMode': 'Uefi', 'Hyperthreading': 'Enabled'},
                                 current={'BootMode': 'Bios', 'Hyperthreading': 'Disabled'})
    assert status is True
    assert stages == [{'BootMode': 'Uefi', 'Hyperthreading': 'Enabled'}]


def test_a_machine_that_serves_no_registry_at_all_still_plans():
    """Plenty of BMCs publish no registry. That is a gap, not a reason to refuse."""
    status, stages = Bios().plan(registry=None, desired={'BootMode': 'Uefi'},
                                 current={'BootMode': 'Bios'})
    assert (status, stages) == (True, [{'BootMode': 'Uefi'}])


def test_nothing_to_do_is_no_stages_rather_than_an_empty_one():
    """A stage that changes nothing still costs a reboot, so it must not be planned."""
    status, stages = Bios().plan(registry=registry(), desired={'BootMode': 'Uefi'},
                                 current={'BootMode': 'Uefi'})
    assert (status, stages) == (True, [])


def test_attributes_already_at_the_wanted_value_are_dropped():
    status, stages = Bios().plan(
        registry=registry(),
        desired={'BootMode': 'Uefi', 'Hyperthreading': 'Enabled'},
        current={'BootMode': 'Uefi', 'Hyperthreading': 'Disabled'})
    assert stages == [{'Hyperthreading': 'Enabled'}]


# --- the case the whole thing exists for ------------------------------------

def test_an_attribute_blocked_by_another_lands_in_a_later_stage():
    """
    The cascade in its simplest form: fan speed cannot be set while fan control is
    on Auto. Both are asked for at once, and it takes two reboots - the first to
    put control into Manual, the second to set the speed that only then exists.
    """
    status, stages = Bios().plan(
        registry=registry([blocks('FanSpeed', 'FanControl', 'Auto')]),
        desired={'FanControl': 'Manual', 'FanSpeed': '80'},
        current={'FanControl': 'Auto', 'FanSpeed': '50'})
    assert status is True
    assert stages == [{'FanControl': 'Manual'}, {'FanSpeed': '80'}]


def test_a_chain_of_dependencies_becomes_a_chain_of_stages():
    """Three attributes, each unlocked by the one before, is three reboots."""
    status, stages = Bios().plan(
        registry=registry([blocks('B', 'A', 'off'), blocks('C', 'B', 'off')]),
        desired={'A': 'on', 'B': 'on', 'C': 'on'},
        current={'A': 'off', 'B': 'off', 'C': 'off'})
    assert status is True
    assert stages == [{'A': 'on'}, {'B': 'on'}, {'C': 'on'}]


def test_independent_attributes_share_a_stage_rather_than_taking_one_each():
    """
    Each stage is a reboot, so the plan writes everything the machine will accept
    at once. A planner that emitted one attribute per stage would be correct and
    would take four reboots where one does.
    """
    status, stages = Bios().plan(
        registry=registry([blocks('FanSpeed', 'FanControl', 'Auto')]),
        desired={'FanControl': 'Manual', 'FanSpeed': '80',
                 'BootMode': 'Uefi', 'Hyperthreading': 'Enabled'},
        current={'FanControl': 'Auto', 'FanSpeed': '50',
                 'BootMode': 'Bios', 'Hyperthreading': 'Disabled'})
    assert len(stages) == 2
    assert stages[0] == {'FanControl': 'Manual', 'BootMode': 'Uefi',
                         'Hyperthreading': 'Enabled'}
    assert stages[1] == {'FanSpeed': '80'}


def test_an_attribute_blocked_by_something_we_are_not_changing_is_refused():
    """
    Asking for a value the machine says cannot be reached from here. Sending it
    anyway buys a reboot and a rejection; saying so buys neither, and names what
    is in the way.
    """
    status, message = Bios().plan(
        registry=registry([blocks('FanSpeed', 'FanControl', 'Auto')]),
        desired={'FanSpeed': '80'},
        current={'FanControl': 'Auto', 'FanSpeed': '50'})
    assert status is False
    assert 'FanSpeed' in message and 'FanControl' in message


def test_a_dependency_that_does_not_currently_hold_blocks_nothing():
    """FanControl is already Manual, so the speed is writable straight away."""
    status, stages = Bios().plan(
        registry=registry([blocks('FanSpeed', 'FanControl', 'Auto')]),
        desired={'FanSpeed': '80'},
        current={'FanControl': 'Manual', 'FanSpeed': '50'})
    assert stages == [{'FanSpeed': '80'}]


# --- being faithful to the schema -------------------------------------------

@pytest.mark.parametrize('prop', ['ReadOnly', 'GrayOut', 'Hidden', 'Immutable'])
def test_every_property_that_stops_a_write_counts(prop):
    """All four keep an attribute from being set, and all four force a stage."""
    status, stages = Bios().plan(
        registry=registry([blocks('B', 'A', 'off', prop=prop)]),
        desired={'A': 'on', 'B': 'on'}, current={'A': 'off', 'B': 'off'})
    assert stages == [{'A': 'on'}, {'B': 'on'}]


def test_a_property_that_does_not_stop_a_write_is_ignored():
    """A dependency setting HelpText or DisplayOrder says nothing about writability."""
    status, stages = Bios().plan(
        registry=registry([blocks('B', 'A', 'off', prop='HelpText')]),
        desired={'A': 'on', 'B': 'on'}, current={'A': 'off', 'B': 'off'})
    assert stages == [{'A': 'on', 'B': 'on'}]


def test_a_dependency_that_turns_blocking_off_is_not_a_blocker():
    """
    MapToValue false is the machine saying an attribute BECOMES writable, which is
    the state this planner is trying to reach - not something to avoid.
    """
    entry = blocks('B', 'A', 'off')
    entry['Dependency']['MapToValue'] = False
    status, stages = Bios().plan(registry=registry([entry]),
                                 desired={'A': 'on', 'B': 'on'},
                                 current={'A': 'off', 'B': 'off'})
    assert stages == [{'A': 'on', 'B': 'on'}]


def test_a_registry_omitting_MapToAttribute_affects_what_it_is_declared_for():
    """Some registries leave it out; DependencyFor is then the affected attribute."""
    entry = blocks('B', 'A', 'off')
    del entry['Dependency']['MapToAttribute']
    status, stages = Bios().plan(registry=registry([entry]),
                                 desired={'A': 'on', 'B': 'on'},
                                 current={'A': 'off', 'B': 'off'})
    assert stages == [{'A': 'on'}, {'B': 'on'}]


@pytest.mark.parametrize('condition,have,want,expected', [
    ('EQU', 'Auto', 'Auto', True), ('EQU', 'Manual', 'Auto', False),
    ('NEQ', 'Manual', 'Auto', True), ('NEQ', 'Auto', 'Auto', False),
    ('GTR', 10, 5, True), ('GTR', 5, 10, False),
    ('GEQ', 5, 5, True), ('LSS', 1, 2, True), ('LEQ', 2, 2, True),
])
def test_every_comparison_the_schema_defines(condition, have, want, expected):
    assert Bios().compare(have, condition, want) is expected


def test_an_ordered_comparison_on_something_that_is_not_a_number_is_unknown():
    """Unknown, not False: False would read as 'the dependency does not apply'."""
    assert Bios().compare('Auto', 'GTR', 'Manual') is None


def test_multiple_conditions_are_joined_by_mapterms():
    """AND and OR fold left to right, as MapTerms describes."""
    bios = Bios()
    both = [{'MapFromAttribute': 'A', 'MapFromCondition': 'EQU', 'MapFromValue': 1},
            {'MapFromAttribute': 'B', 'MapFromCondition': 'EQU', 'MapFromValue': 2,
             'MapTerms': 'AND'}]
    either = [dict(both[0]), dict(both[1], MapTerms='OR')]
    assert bios.holds(both, {'A': 1, 'B': 2}) is True
    assert bios.holds(both, {'A': 1, 'B': 9}) is False
    assert bios.holds(either, {'A': 1, 'B': 9}) is True
    assert bios.holds(either, {'A': 8, 'B': 9}) is False


def test_a_condition_on_something_other_than_a_current_value_is_unknown():
    """
    A dependency keyed on another attribute's ReadOnly cannot be answered from the
    Bios resource. Unknown means the attribute is attempted and the machine gets
    to refuse it - which is better than never attempting it and deadlocking on a
    guess.
    """
    assert Bios().holds([{'MapFromAttribute': 'A', 'MapFromProperty': 'ReadOnly',
                          'MapFromCondition': 'EQU', 'MapFromValue': True}], {'A': 1}) is None


def test_a_condition_naming_an_attribute_this_machine_does_not_have_is_unknown():
    assert Bios().holds([{'MapFromAttribute': 'NotHere', 'MapFromCondition': 'EQU',
                          'MapFromValue': 1}], {'A': 1}) is None


def test_an_unevaluatable_dependency_does_not_block():
    """
    The machine is the authority. Attempting a write it refuses costs a reboot;
    refusing to attempt one it would have accepted costs the whole operation.
    """
    entry = blocks('B', 'A', 'off')
    entry['Dependency']['MapFrom'][0]['MapFromProperty'] = 'ReadOnly'
    status, stages = Bios().plan(registry=registry([entry]),
                                 desired={'A': 'on', 'B': 'on'},
                                 current={'A': 'off', 'B': 'off'})
    assert stages == [{'A': 'on', 'B': 'on'}]


# --- verifying afterwards ----------------------------------------------------

def test_an_attribute_the_machine_did_not_take_is_reported():
    """
    A BIOS accepts a payload and applies what it likes of it. The PATCH answered
    success long before, so the only way to know is to read back what it now holds.
    """
    missing = Bios().unapplied(wanted={'BootMode': 'Uefi', 'FanSpeed': '80'},
                               attributes={'BootMode': 'Uefi', 'FanSpeed': '50'})
    assert missing == {'FanSpeed': '50'}


def test_an_attribute_absent_from_the_reported_set_counts_as_unapplied():
    """
    Vendors differ on whether a pending area lists everything or only what changed,
    so absent is not evidence of applied. Treating it as applied is how a silently
    dropped setting is reported as a success.
    """
    assert Bios().unapplied(wanted={'FanSpeed': '80'}, attributes={}) == {'FanSpeed': None}


def test_everything_applied_is_reported_as_nothing_missing():
    assert Bios().unapplied(wanted={'BootMode': 'Uefi'},
                            attributes={'BootMode': 'Uefi', 'Other': 'x'}) == {}
