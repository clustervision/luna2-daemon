#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: when a staged BIOS apply stops trying, and whether it may start.

Two decisions, both pure functions of what the machine said, and both required to
be deterministic: the same inputs give the same answer and the same number of
attempts, on a fast machine and a slow one alike.

Giving up has two shapes and they are not interchangeable.

A clear, direct refusal ends it at once. Retrying a refusal reboots the machine
to be refused again, and the reason is already in hand to report. The refusal can
arrive two ways - the write fails, or the write succeeds and the settings object
reports the payload as rejected - and a check that reads only the HTTP status
misses the second entirely.

No error and no effect is the other, and it is the one nobody predicts: the PATCH
is accepted, the machine reboots, and the attribute is simply not there. Nothing
reports it. The only way to know is to read back and compare, and the only sane
answer is a bounded count and then a stop that says how many attempts were spent.
"""

import pytest

from utils.bios import Bios, MAX_ATTEMPTS

WANTED = {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled'}
APPLIED = {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled', 'Other': 'x'}
HALF = {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Disabled'}


# --- everything landed -------------------------------------------------------

def test_a_stage_that_took_is_done():
    outcome, reason = Bios().verdict(wanted=WANTED, attributes=APPLIED)
    assert outcome == 'done'
    assert reason == 'applied'


def test_extra_attributes_on_the_machine_do_not_matter():
    """A machine has hundreds of attributes; a stage asked for two."""
    outcome, _ = Bios().verdict(wanted=WANTED, attributes=dict(APPLIED, Extra='y'))
    assert outcome == 'done'


# --- a clear, direct refusal ends it immediately ------------------------------

def test_a_failed_write_gives_up_at_once_however_many_attempts_remain():
    """
    Retrying a refusal costs a reboot and produces the same refusal. The bounded
    retry is for the silent case, not this one.
    """
    outcome, reason = Bios().verdict(wanted=WANTED, attributes={},
                                     error='400: value not supported', attempts=0)
    assert outcome == 'failed'
    assert 'value not supported' in reason


def test_a_rejection_in_the_settings_object_counts_as_a_refusal():
    """
    The write can succeed and the machine still say no. Reading only the HTTP
    status would call this a silent non-application and burn three reboots on it.
    """
    messages = [{'MessageId': 'Base.1.0.PropertyNotWritable',
                 'Message': 'BootMode is not writable in the current state',
                 'Severity': 'Critical', 'Resolution': 'Disable Secure Boot first'}]
    outcome, reason = Bios().verdict(wanted=WANTED, attributes={}, messages=messages)
    assert outcome == 'failed'
    assert 'not writable' in reason
    assert 'Disable Secure Boot first' in reason, 'the machine said how to fix it'


@pytest.mark.parametrize('severity', ['Critical', 'critical', 'Warning', 'WARNING'])
def test_severity_is_matched_whatever_case_the_vendor_used(severity):
    messages = [{'Message': 'refused', 'MessageSeverity': severity}]
    assert Bios().verdict(wanted=WANTED, attributes={}, messages=messages)[0] == 'failed'


def test_an_informational_message_is_not_a_refusal():
    """
    A settings object routinely carries OK-severity notes. Reading one as a
    rejection would abandon a stage that was about to succeed.
    """
    messages = [{'Message': 'Settings will be applied on next reset', 'Severity': 'OK'}]
    outcome, _ = Bios().verdict(wanted=WANTED, attributes=APPLIED, messages=messages)
    assert outcome == 'done'


# --- accepted, and silently not applied --------------------------------------

def test_no_error_and_no_effect_retries_while_attempts_remain():
    """
    'attempts' counts what was spent BEFORE this one - the executor increments it
    after judging - so the attempt just made is that plus one. Numbered from the
    raw counter an operator watched 0, 1, 2 go past and then read 'after 3
    attempts', which is three writes and three reboots described as starting at
    nothing.
    """
    outcome, reason = Bios().verdict(wanted=WANTED, attributes=HALF, attempts=0)
    assert outcome == 'retry'
    assert 'SriovGlobalEnable' in reason
    assert "attempt 1 of 3" in reason, 'the first attempt is the first, not the zeroth'

    _, second = Bios().verdict(wanted=WANTED, attributes=HALF, attempts=1)
    assert "attempt 2 of 3" in second


def test_it_gives_up_at_the_limit_and_says_how_many_it_spent():
    outcome, reason = Bios().verdict(wanted=WANTED, attributes=HALF,
                                     attempts=MAX_ATTEMPTS)
    assert outcome == 'failed'
    assert 'never took after 3 attempt(s)' in reason
    assert 'no error from the machine' in reason, (
        'the operator has to know the machine never complained - that is the '
        'whole character of this failure'
    )


def test_an_absent_attribute_counts_as_not_applied():
    """
    Vendors differ on whether a pending area lists everything or only what
    changed, so absent is not evidence of applied.
    """
    outcome, reason = Bios().verdict(wanted=WANTED, attributes={'BootMode': 'Uefi'},
                                     attempts=MAX_ATTEMPTS)
    assert outcome == 'failed'
    assert 'SriovGlobalEnable' in reason


def test_the_decision_is_deterministic():
    """
    The requirement, asserted rather than assumed. Same inputs, same answer,
    every time - nothing here may depend on a clock or on how slow a machine is.
    """
    calls = [Bios().verdict(wanted=WANTED, attributes=HALF, attempts=2) for _ in range(20)]
    assert len(set(calls)) == 1


def test_the_attempt_ladder_is_exactly_the_limit_then_stop():
    """
    Walk it end to end: retry up to the limit, fail on it, and never once more.
    A count that is off by one either wastes a reboot or gives up early, and
    neither is visible from a single call.
    """
    outcomes = [Bios().verdict(wanted=WANTED, attributes=HALF, attempts=n)[0]
                for n in range(MAX_ATTEMPTS + 2)]
    assert outcomes == ['retry'] * MAX_ATTEMPTS + ['failed', 'failed']


def test_an_empty_stage_is_success_not_a_failed_attempt():
    """
    plan() drops attributes already at the value asked for, so an empty stage
    means there is nothing left to do. Counting it as an attempt would spend the
    budget on work that was already finished.
    """
    outcome, _ = Bios().verdict(wanted={}, attributes={}, attempts=MAX_ATTEMPTS)
    assert outcome == 'done'


# --- may this configuration be pushed here at all ----------------------------

CONFIG = {'manufacturer': 'Contoso', 'model': 'PowerThing R750', 'biosversion': '2.15.1'}


def test_the_same_machine_is_always_allowed():
    assert Bios().compatible(config=CONFIG, target=dict(CONFIG)) == (True, None)


@pytest.mark.parametrize('policy', ['strict', 'warn', 'ignore'])
def test_a_different_model_is_refused_under_every_policy(policy):
    """
    Not negotiable. BIOS settings are only meaningful on the hardware that
    published them, so no policy may wave this through.
    """
    target = dict(CONFIG, model='PowerThing R650')
    status, reason = Bios().compatible(config=CONFIG, target=target, policy=policy)
    assert status is False
    assert 'model differs' in reason


@pytest.mark.parametrize('policy', ['strict', 'warn', 'ignore'])
def test_a_different_manufacturer_is_refused_under_every_policy(policy):
    target = dict(CONFIG, manufacturer='Fabrikam')
    assert Bios().compatible(config=CONFIG, target=target, policy=policy)[0] is False


def test_the_bios_version_is_the_policy_and_strict_refuses():
    target = dict(CONFIG, biosversion='2.19.0')
    status, reason = Bios().compatible(config=CONFIG, target=target, policy='strict')
    assert status is False
    assert '2.15.1' in reason and '2.19.0' in reason


def test_warn_proceeds_and_says_what_differed():
    """
    Proceeding silently would be worse than refusing: the operator needs to know
    a firmware difference was crossed, even though it was allowed.
    """
    target = dict(CONFIG, biosversion='2.19.0')
    status, reason = Bios().compatible(config=CONFIG, target=target, policy='warn')
    assert status is True
    assert reason and 'BIOS version differs' in reason


def test_ignore_does_not_look():
    target = dict(CONFIG, biosversion='2.19.0')
    assert Bios().compatible(config=CONFIG, target=target, policy='ignore') == (True, None)


def test_an_unknown_version_is_a_difference_not_a_match():
    """
    Absent must not read as equal. A machine that does not report its BIOS
    version is a machine we know less about, not one we know agrees.
    """
    target = dict(CONFIG, biosversion='')
    assert Bios().compatible(config=CONFIG, target=target, policy='strict')[0] is False
    status, reason = Bios().compatible(config=CONFIG, target=target, policy='warn')
    assert status is True and 'not known' in reason


def test_an_unknown_model_is_refused_rather_than_assumed_to_match():
    assert Bios().compatible(config=CONFIG, target=dict(CONFIG, model=''))[0] is False


def test_the_board_comparison_ignores_case_and_padding_only():
    """
    Vendors are inconsistent about case and trailing spaces in these strings.
    They are not inconsistent about which model it is, so nothing more is
    normalised - reducing 'R750' and 'R650' to a common form would be a bug.
    """
    assert Bios().compatible(config=CONFIG,
                             target=dict(CONFIG, model=' powerthing r750 '))[0] is True
    assert Bios().compatible(config=CONFIG,
                             target=dict(CONFIG, model='PowerThing R650'))[0] is False


def test_an_unknown_policy_word_behaves_as_warn():
    """
    The policy arrives from luna.ini or a command line, so it can be anything.
    Defaulting to the middle is right: a typo must not silently disable the
    check, and must not refuse every push either.
    """
    target = dict(CONFIG, biosversion='2.19.0')
    status, reason = Bios().compatible(config=CONFIG, target=target, policy='nonsense')
    assert status is True and reason
