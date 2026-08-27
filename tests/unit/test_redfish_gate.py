#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2027: no redfishsetup, no Redfish.

There used to be a third answer from for_node: no redfishsetup meant "carry on
with the bmcsetup credentials". It worked - IPMI and Redfish share one user store
on the BMC, so the IPMI account authenticates over Redfish - and that is exactly
what made it wrong. An administrator who deliberately assigned no redfishsetup
still got Redfish traffic, on credentials they had nominated for IPMI. The absence
of configuration did not mean the absence of Redfish, so there was no way to say
"do not touch this over Redfish" short of unplugging the BMC.

Capability is the gate now, and it needs no flag to express. What it does need is
a test, because the old behaviour was not covered by one: removing the fallback
left the whole suite green, which is how a silent behaviour change gets shipped.

The protocol fallback is a different mechanism and is untouched: control still
tries Redfish and then ipmitool. That one is the feature.
"""

import pytest

from base.nodeinventory import NodeInventory
from utils.database import Database
from utils.helper import Helper
from utils.redfish import RedfishAccess


@pytest.fixture(name='node')
def node_fixture(sqlite_db):
    """One node with a BMC address and a bmcsetup, and no redfishsetup."""
    Database().insert('group', [{"column": "name", "value": 'compute'},
                                {"column": "id", "value": 1}])
    Database().insert('node', [{"column": "name", "value": 'node001'},
                               {"column": "id", "value": 1},
                               {"column": "groupid", "value": 1}])
    Database().insert('bmcsetup', [{"column": "name", "value": 'default'},
                                   {"column": "id", "value": 1},
                                   {"column": "username", "value": 'admin'},
                                   {"column": "password", "value": 'secret'}])
    Database().update('node', Helper().make_rows({'bmcsetupid': 1}),
                      [{"column": "id", "value": 1}])
    Database().insert('nodeinterface', [{"column": "id", "value": 1},
                                        {"column": "nodeid", "value": 1},
                                        {"column": "interface", "value": 'BMC'}])
    Database().insert('ipaddress', [{"column": "id", "value": 1},
                                    {"column": "tableref", "value": 'nodeinterface'},
                                    {"column": "tablerefid", "value": 1},
                                    {"column": "ipaddress", "value": '10.148.0.1'}])
    return 'node001'


def add_redfishsetup(name='datacentre', role='ReadOnly'):
    Database().insert('redfishsetup', [{"column": "name", "value": name},
                                       {"column": "id", "value": 1},
                                       {"column": "scheme", "value": 'https'}])
    Database().insert('redfishaccount', [{"column": "id", "value": 1},
                                         {"column": "redfishsetupid", "value": 1},
                                         {"column": "name", "value": 'sweep'},
                                         {"column": "username", "value": 'sweep'},
                                         {"column": "password", "value": 'pw'},
                                         {"column": "role", "value": role}])
    Database().update('node', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "id", "value": 1}])


# --- the gate ---------------------------------------------------------------

def test_a_node_with_no_redfishsetup_is_refused(node):
    """
    The behaviour change, and the whole point of the ticket. This node has a BMC
    address and perfectly good bmcsetup credentials that would work over Redfish.
    It is still refused, because nobody said Redfish may be used here.
    """
    status, reason = RedfishAccess().for_node(nodename=node)
    assert status is False
    assert 'no redfishsetup' in reason


def test_the_refusal_reaches_the_caller_rather_than_a_credential(node):
    """bmc_for used to fall through to bmcsetup. It must not any more."""
    status, answer = NodeInventory().bmc_for(name=node)
    assert status is False
    assert 'redfishsetup' in answer
    assert 'admin' not in str(answer), 'the IPMI credentials must not be reached for'


def test_assigning_one_is_what_turns_it_on(node):
    add_redfishsetup()
    status, access = RedfishAccess().for_node(nodename=node)
    assert status is True
    assert access['username'] == 'sweep'


def test_the_bmcsetup_credentials_are_never_used_for_redfish(node):
    """
    They would work - one user store, two front ends - which is why this is
    asserted rather than assumed.
    """
    add_redfishsetup()
    _, access = NodeInventory().bmc_for(name=node)
    assert access['username'] == 'sweep'
    assert access['password'] == 'pw'


def test_a_setup_that_cannot_be_used_still_says_so_out_loud(node):
    """
    Assigned but empty is a misconfiguration, and it has always been reported per
    node rather than worked around. Removing the fallback must not turn this into
    the same answer as 'not configured' - they need different fixes.
    """
    Database().insert('redfishsetup', [{"column": "name", "value": 'broken'},
                                       {"column": "id", "value": 1}])
    Database().update('node', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "id", "value": 1}])
    status, reason = RedfishAccess().for_node(nodename=node)
    assert status is False
    assert 'no accounts' in reason
    assert 'no redfishsetup' not in reason


def test_a_group_assignment_counts_as_configured(node):
    """Selection is node then group, as it is for bmcsetup and osimage."""
    add_redfishsetup()
    Database().update('node', Helper().make_rows({'redfishsetupid': ''}),
                      [{"column": "id", "value": 1}])
    Database().update('group', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "id", "value": 1}])
    status, access = RedfishAccess().for_node(nodename=node)
    assert status is True and access['username'] == 'sweep'


# --- the flag, which is declared now and gates nothing yet -------------------

def test_setupredfish_exists_on_both_node_and_group():
    """
    Declared ahead of what it gates. TRIX-2001 is what creates role-scoped Redfish
    accounts, and until that lands there is nothing for this to switch off - but
    the column migrates itself, so having it present means the flag does not have
    to arrive in the same release as the behaviour.

    Absent reads as false, which is today's behaviour: Luna creates no Redfish
    accounts at all.
    """
    from common.database_layout import DATABASE_LAYOUT_node, DATABASE_LAYOUT_group

    for layout in (DATABASE_LAYOUT_node, DATABASE_LAYOUT_group):
        columns = [entry['column'] for entry in layout]
        assert 'setupredfish' in columns
        assert 'setupbmc' in columns, 'it sits beside the flag it splits, not instead of it'


# --- a setup that is deliberately read-only ---------------------------------

def test_a_read_only_setup_is_refused_a_write_rather_than_sent_one(node):
    """
    A redfishsetup need not hold an Administrator. If every account it holds is
    ReadOnly, that is the administrator saying so.

    It used to hand the ReadOnly account back for a write anyway: the write went
    out, the board refused it, and the operator got a permission error that nothing
    Luna had said would explain.
    """
    add_redfishsetup(role='ReadOnly')
    read = RedfishAccess().for_node(nodename=node, write=False)
    assert read[0] is True and read[1]['username'] == 'sweep'

    write = RedfishAccess().for_node(nodename=node, write=True)
    assert write[0] is False
    assert 'no account that may write' in write[1]


def test_it_does_not_reach_for_the_bmcsetup_credentials_instead(node):
    """
    They would work - the BMC keeps one user store behind both front ends, so the
    IPMI account is a Redfish Administrator. That is the reason not to use them: an
    administrator who configured only a ReadOnly account has said read-only, and
    using the IPMI administrator behind their back escalates past an explicit
    choice rather than around a missing one.

    Creating the Redfish accounts in the first place is the one place that
    credential is the right one, and that is a deliberate act gated by
    setupredfish - not a fallback (TRIX-2001).
    """
    add_redfishsetup(role='ReadOnly')
    status, answer = RedfishAccess().for_node(nodename=node, write=True)
    assert status is False
    assert 'admin' not in str(answer) and 'secret' not in str(answer)


def test_an_administrator_alongside_it_is_what_allows_the_write(node):
    add_redfishsetup(role='ReadOnly')
    Database().insert('redfishaccount', [{"column": "id", "value": 2},
                                         {"column": "redfishsetupid", "value": 1},
                                         {"column": "name", "value": 'admin'},
                                         {"column": "username", "value": 'rfadmin'},
                                         {"column": "password", "value": 'pw2'},
                                         {"column": "role", "value": 'Administrator'}])
    assert RedfishAccess().for_node(nodename=node, write=True)[1]['username'] == 'rfadmin'
    assert RedfishAccess().for_node(nodename=node, write=False)[1]['username'] == 'sweep', (
        'and the read still uses the weakest account that can do the job'
    )


def test_a_vendor_role_we_do_not_rank_is_unknown_not_refused(node):
    """
    Redfish allows OEM roles with arbitrary privilege sets, so a name we have never
    heard of might well be able to write. ReadOnly is the only predefined role that
    provably cannot - Login and ConfigureSelf and nothing else - so it is the only
    one that refuses here. Stranding a node on an unknown would be worse.
    """
    add_redfishsetup(role='OemPowerOnly')
    status, access = RedfishAccess().for_node(nodename=node, write=True)
    assert status is True and access['username'] == 'sweep'
