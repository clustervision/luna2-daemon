#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-178 unit tests for the redfish half of the control path.

Two things are pinned here. The boundary: content arrives base64 and is decoded
once, where a malformed file is refused once rather than against every BMC in the
hostlist. And the dispatch: the redfish actions reach the plugin family, and every
other control action is left exactly as it was.
"""

from base64 import b64encode
from json import dumps

import pytest

from base.control import Control


def request_body(action='setting', hostlist='node001', uri='/redfish/v1/Systems/1/Bios',
                 content=..., raw=None):
    """A control request in the shape the CLI sends."""
    if content is ...:
        content = b64encode(dumps({'BootMode': 'Uefi'}).encode()).decode()
    body = {'hostlist': hostlist}
    if uri is not None:
        body['uri'] = uri
    if content is not None:
        body['content'] = content
    if raw is not None:
        body.update(raw)
    return {'control': {'redfish': {action: body}}}


def payload_of(**kwargs):
    return Control().redfish_payload(request_body(**kwargs), 'redfish', kwargs.get('action', 'setting'))


# --- the happy boundary -----------------------------------------------------

def test_content_arrives_base64_and_reaches_the_plugin_as_a_dict():
    """
    filter_data strips every quote out of every string in a request body, so raw
    JSON would arrive silently mangled -- '{"BootMode": "Uefi"}' becomes
    '{BootMode: Uefi}'. Base64 is also what the neighbouring script fields already
    use, so callers meet one convention rather than a per-field guess.
    """
    status, payload = payload_of()
    assert status is True
    assert payload == {'uri': '/redfish/v1/Systems/1/Bios', 'content': {'BootMode': 'Uefi'}}


def test_a_quote_bearing_value_survives_the_round_trip():
    """The whole reason for the encoding: a value with quotes in it must arrive intact."""
    content = b64encode(dumps({'Name': 'he said "no"'}).encode()).decode()
    status, payload = payload_of(content=content)
    assert status is True
    assert payload['content']['Name'] == 'he said "no"'


# --- distinct, readable refusals --------------------------------------------

def test_a_missing_uri_says_so():
    status, message = payload_of(uri=None)
    assert status is False and 'uri' in message


def test_missing_content_says_so():
    status, message = payload_of(content=None)
    assert status is False and 'content' in message


def test_content_that_is_not_base64_is_named_as_such():
    status, message = payload_of(content='this is not base64 !!')
    assert status is False and 'base64' in message


def test_content_that_is_base64_but_not_json_is_named_as_such():
    """
    A distinct message from the base64 one. 'malformed file' covers both and tells
    the operator nothing about which half to go and look at.
    """
    status, message = payload_of(content=b64encode(b'BootMode = Uefi').decode())
    assert status is False and 'json' in message and 'base64' not in message


def test_a_malformed_file_is_refused_once_not_once_per_node():
    """
    The decode happens before any node is queued. A hostlist of four thousand nodes
    and a bad file is one refusal, not four thousand BMC connections that each fail
    the same way.
    """
    status, message = Control().bulk_action(
        request_body(hostlist='node[001-4000]', content='not base64 !!'))
    assert status is False and 'base64' in message


# --- leaving the other subsystems alone -------------------------------------

@pytest.mark.parametrize('subsystem,action', [
    ('power', 'on'), ('power', 'status'), ('sel', 'list'), ('chassis', 'identify'),
])
def test_the_other_control_subsystems_are_never_asked_for_a_payload(monkeypatch,
                                                                    subsystem, action):
    """
    power, sel and chassis go through the same bulk path, and none of them sends a
    uri or content. If the payload extraction ever stopped being conditional they
    would every one of them start failing for the lack of something they have never
    had -- which is how a new subsystem breaks three old ones.

    bulk_action goes on to want a database and a thread pool, which this suite has
    neither of. That does not matter: what is being asserted is what happened
    before it got there.
    """
    asked = []
    monkeypatch.setattr(Control, 'redfish_payload',
                        lambda self, *args, **kwargs: asked.append(args) or (True, {}))
    body = {'control': {subsystem: {action: {'hostlist': 'node001'}}}}
    try:
        Control().bulk_action(body)
    except Exception:
        pass
    assert not asked, f'{subsystem} {action} was asked for a redfish payload'


@pytest.mark.parametrize('command', ['redfish setting', 'redfish upload'])
def test_both_redfish_actions_are_dispatched_rather_than_unimplemented(command):
    """
    'Instruction not implemented' is what the whole ticket exists to remove. This
    reads the dispatch rather than calling it, because calling it needs a BMC.
    """
    import inspect

    from utils.control import Control as NodeControl

    source = inspect.getsource(NodeControl.control_action)
    assert f"case '{command}':" in source


def test_a_redfish_action_without_a_payload_is_refused_readably():
    """
    The single-node GET route carries no body, so it cannot supply a uri. It must
    say what to do instead of falling through to 'Instruction not implemented'.
    """
    from utils.control import Control as NodeControl

    status, message = NodeControl().redfish_interact(
        'setting', 'node001', 'compute', '192.0.2.10', 'u', 'p', None)
    assert status is False
    assert 'uri' in message and 'hostlist' in message
