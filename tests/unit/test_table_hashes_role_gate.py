#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2325: which controller may answer the table hashes, over the whole truth table of the
two HA flags, and that the refusal text the sweep matches on still matches.
"""

import pytest

# hastate, master, does it answer, what the case is
ROLES = [
    (False, False, True,  'HA disabled: there is no other controller to be the source'),
    (False, True,  True,  'HA disabled and flagged master: still the only controller'),
    (True,  False, False, 'HA enabled and not the master: the master is the source'),
    (True,  True,  True,  'HA enabled and the master'),
]


@pytest.fixture
def role(monkeypatch):
    """The two answers the gate reads, set the way the rest of the daemon's tests set them."""
    import base.tables as module

    def _set(hastate, master):
        monkeypatch.setattr(module.HA, 'get_hastate', lambda self: hastate)
        monkeypatch.setattr(module.HA, 'get_role', lambda self: master)
    return _set


@pytest.mark.parametrize('hastate, master, answers, case', ROLES)
def test_only_an_authoritative_controller_answers_the_hashes(sqlite_db, role, hastate, master, answers, case):
    from base.tables import Tables
    from utils.tables import Tables as UTables
    role(hastate, master)

    status, response = Tables().get_table_hashes()

    assert status is answers, case
    if answers:
        assert set(response['table']['hashes']) == set(UTables().tables), case
    else:
        assert response == 'not master', case


def test_the_sweep_skips_a_peer_that_refuses(sqlite_db, role, monkeypatch):
    """
    Pins the two halves of the refusal to each other: the text the gate returns is the text fed
    to the sweep, so rewording one without the other fails here rather than in a pair.
    """
    import base.tables as base_module
    import utils.tables as sweep_module

    role(hastate=True, master=False)
    _, refusal = base_module.Tables().get_table_hashes()

    monkeypatch.setattr(sweep_module.HA, 'get_sharedip', lambda self: False)
    monkeypatch.setattr(sweep_module.HA, 'get_shadow', lambda self: False)
    # which controller this one is comes from the argument, so the walk over the local
    # interfaces decides nothing here and would make the result depend on the box
    monkeypatch.setattr(sweep_module.Helper, 'local_addresses', lambda self: [])
    monkeypatch.setattr(sweep_module.Database, 'get_record_join', lambda self, *args, **kwargs: [
        {'hostname': 'controller1', 'beacon': 0, 'shadow': 0,
         'ipaddress': '10.141.255.254', 'ipaddress_ipv6': None, 'domain': 'cluster'},
        {'hostname': 'controller2', 'beacon': 0, 'shadow': 0,
         'ipaddress': '10.141.255.253', 'ipaddress_ipv6': None, 'domain': 'cluster'},
    ])
    asked = []

    def _answer(self, host, path):
        asked.append((host, path))
        return True, {'message': refusal}
    monkeypatch.setattr(sweep_module.Request, 'get_request', _answer)

    mismatch = sweep_module.Tables().verify_tablehashes_controllers(me='controller1', shadow=False)

    assert asked == [('controller2', '/table/hashes')], 'the peer has to have been asked at all'
    assert mismatch == [], 'a peer that says it is not the master is skipped, never imported from'
