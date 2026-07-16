#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1937 unit tests for helpers that answered a different question than their caller asked.

A shared helper is used everywhere, so where it is subtly wrong it is wrong everywhere at
once and silently. The bug lives at the mismatch between what the helper actually tests
and what a caller believes it tests -- which is why these tests are written from the
caller's expectation, not from the implementation.

check_jinja promised "True or False For Errors" and caught only OSError, so the jinja
syntax error it exists to find escaped instead of returning False. Templates are the
documented customisation surface, and the raise landed in the housekeeper, where it
blocked every task queued behind it.

check_ip is deliberately tolerant: it accepts a CIDR and a comma-separated list and returns
the first host part. That is correct for the network and nameserver fields it was written
for, and wrong for anything that means "one bare address" -- which is what validate_route
believed it meant.
"""

import ipaddress

import pytest

from base.route import Route
from utils.helper import Helper


# ---------------------------------------------------------------- check_jinja

def test_check_jinja_returns_false_for_a_syntax_error(tmp_path):
    """The one thing its name promises. It used to raise instead, and take the queue with it."""
    broken = tmp_path / 'broken.j2'
    broken.write_text('{% for node in nodes %}{{ node }}')      # never closed
    try:
        result = Helper().check_jinja(str(broken))
    except Exception as exp:
        pytest.fail(
            f"check_jinja raised {type(exp).__name__} instead of returning False. It is called "
            f"from the housekeeper's task loop, where a raise blocks every task behind it: "
            f"dhcp and dns restarts, osimage unpack, provisioning. {exp}"
        )
    assert result is False, "a template with a syntax error must not report as valid"


def test_check_jinja_returns_false_for_a_missing_file(tmp_path):
    """The case it always handled -- kept so widening the catch did not lose it."""
    assert Helper().check_jinja(str(tmp_path / 'nope.j2')) is False


def test_check_jinja_accepts_a_valid_template(tmp_path):
    """And the guard must not cost the helper its purpose."""
    good = tmp_path / 'good.j2'
    good.write_text('hello {{ name }}{% for x in y %}{{ x }}{% endfor %}')
    assert Helper().check_jinja(str(good)) is True


# ---------------------------------------------------------------- check_ip's real contract
# Pinned because callers keep reading it as "is this one address". It is not, deliberately.

@pytest.mark.parametrize('value,expected_truthy', [
    ('10.141.0.1', True),
    ('10.141.0.1/24', True),        # a CIDR is accepted and the prefix stripped -- by design
    ('10.141.0.1,10.141.0.2', True),  # a list is accepted -- by design, for nameserver_ip
    ('bogus', False),
])
def test_check_ip_is_tolerant_and_that_is_deliberate(value, expected_truthy):
    """Documents what check_ip actually answers, so the next caller does not assume otherwise."""
    assert bool(Helper().check_ip(value)) is expected_truthy, (
        f"check_ip({value!r}) changed behaviour. Callers depend on the tolerance: base/network.py "
        f"passes a CIDR for 'network', and nameserver_ip is legitimately a comma-separated list. "
        f"A caller wanting one bare address must use ipaddress.ip_address instead."
    )


# ---------------------------------------------------------------- validate_route's next-hop

@pytest.mark.parametrize('gateway', [
    '10.141.0.1/24',           # a prefix on a next-hop -- the natural slip, since destination IS a CIDR
    '10.141.0.1,10.141.0.2',   # a list where one address is meant
    'bogus',
])
def test_validate_route_rejects_a_next_hop_that_is_not_one_address(db, gateway):
    """It must answer 400 with a message, not raise ValueError into a 500."""
    try:
        status, message = Route().validate_route('192.168.50.0/24', gateway, '', None)
    except ValueError as exp:
        pytest.fail(
            f"validate_route raised ValueError for gateway={gateway!r} instead of rejecting it. "
            f"Uncaught in the route, this is an opaque HTTP 500 where the code means to return "
            f"a 400 saying the next-hop is invalid. {exp}"
        )
    assert status is False and 'next-hop' in str(message), (
        f"gateway={gateway!r} was accepted as a valid next-hop: {message}"
    )


@pytest.mark.parametrize('destination,gateway', [
    ('192.168.50.0/24', '10.141.0.1'),
    ('fd00:beef::/64', 'fd00::1'),
])
def test_validate_route_still_accepts_a_real_next_hop(db, destination, gateway):
    """The guard must not cost the field its purpose, in either family."""
    status, message = Route().validate_route(destination, gateway, '', None)
    assert status is not False or 'next-hop' not in str(message), (
        f"a valid next-hop {gateway!r} for {destination!r} was rejected: {message}"
    )


def test_validate_route_still_catches_a_family_mismatch(db):
    """The check this line existed for in the first place."""
    status, message = Route().validate_route('192.168.50.0/24', 'fd00::1', '', None)
    assert status is False and 'does not match' in str(message), (
        f"an IPv6 next-hop was accepted for an IPv4 destination: {message}"
    )
