#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-178 unit tests for the default Redfish interaction plugin.

The plugin is handed a client rather than building one, and that is exactly what
makes these tests possible: no BMC, no network, no database. A vendor plugin
written later is testable the same way, which is the point of the contract.
"""

import pytest

from plugins.redfish.default import Plugin


class FakeClient():
    """A stand-in for utils.redfish.Redfish that records what it was asked to do."""

    def __init__(self, resources=None, patch_result=None, post_result=None):
        self.resources = resources or {}
        self.patch_result = patch_result or (True, {})
        self.post_result = post_result or (True, {})
        self.patched = []
        self.posted = []

    def get(self, path=None, cache=False):
        if path in self.resources:
            return True, self.resources[path]
        return False, 'resource not found'

    def patch(self, path=None, payload=None):
        self.patched.append((path, payload))
        return self.patch_result

    def post(self, path=None, payload=None):
        self.posted.append((path, payload))
        return self.post_result


BIOS = '/redfish/v1/Systems/1/Bios'
STAGED = '/redfish/v1/Systems/1/Bios/Settings'


# --- refusing before touching the BMC ---------------------------------------

@pytest.mark.parametrize('uri,payload,expected', [
    (None, {'a': 1}, 'No Redfish uri given'),
    (BIOS, None, 'No content given to apply'),
])
def test_an_incomplete_setting_is_refused_without_a_call(uri, payload, expected):
    client = FakeClient()
    status, message = Plugin().setting(redfish=client, uri=uri, payload=payload)
    assert (status, message) == (False, expected)
    assert not client.patched


def test_a_uri_the_service_does_not_serve_names_itself():
    """
    The resource is read before it is written, so a wrong uri is reported as a
    wrong uri rather than as whatever a PATCH against it happens to return.
    """
    client = FakeClient()
    status, message = Plugin().setting(redfish=client, uri=BIOS, payload={'BootMode': 'Uefi'})
    assert status is False
    assert BIOS in message
    assert not client.patched


# --- the discovery-first behaviour ------------------------------------------

def test_a_staged_resource_is_written_where_the_service_says_it_must_be():
    """
    BIOS cannot be modified in place. The service says so itself, by carrying an
    @Redfish.Settings annotation naming a separate settings object -- so we follow
    the annotation rather than hardcoding a per-vendor path. Writing to the
    resource itself is accepted and silently ignored on some vendors, which is the
    worst of the available outcomes.
    """
    client = FakeClient(resources={BIOS: {
        '@Redfish.Settings': {
            'SettingsObject': {'@odata.id': STAGED},
            'SupportedApplyTimes': ['OnReset', 'Immediate'],
        }
    }})
    status, message = Plugin().setting(redfish=client, uri=BIOS, payload={'BootMode': 'Uefi'})
    assert status is True
    assert client.patched == [(STAGED, {'BootMode': 'Uefi'})]
    assert STAGED in message
    assert 'OnReset' in message


def test_a_plain_resource_is_written_in_place():
    client = FakeClient(resources={'/redfish/v1/Systems/1': {'AssetTag': 'old'}})
    status, message = Plugin().setting(
        redfish=client, uri='/redfish/v1/Systems/1', payload={'AssetTag': 'new'})
    assert status is True
    assert client.patched == [('/redfish/v1/Systems/1', {'AssetTag': 'new'})]
    assert 'applied on /redfish/v1/Systems/1' == message


def test_an_annotation_without_a_settings_object_is_not_followed():
    """A malformed annotation must not send the write to nowhere."""
    client = FakeClient(resources={BIOS: {'@Redfish.Settings': {'SupportedApplyTimes': ['OnReset']}}})
    Plugin().setting(redfish=client, uri=BIOS, payload={'BootMode': 'Uefi'})
    assert client.patched == [(BIOS, {'BootMode': 'Uefi'})]


def test_a_refused_write_reports_the_service_reason():
    client = FakeClient(resources={BIOS: {}},
                        patch_result=(False, 'BootMode is read only in the current state'))
    status, message = Plugin().setting(redfish=client, uri=BIOS, payload={'BootMode': 'Uefi'})
    assert status is False
    assert 'read only' in message and BIOS in message


# --- uploading --------------------------------------------------------------

def test_an_upload_posts_the_content_to_the_uri():
    client = FakeClient(post_result=(True, {}))
    status, message = Plugin().upload(
        redfish=client, uri='/redfish/v1/UpdateService', payload={'ImageURI': 'x'})
    assert status is True
    assert client.posted == [('/redfish/v1/UpdateService', {'ImageURI': 'x'})]
    assert 'uploaded on' in message


def test_work_the_service_accepted_but_has_not_finished_is_reported_as_a_task():
    """
    'Submitted, task <x>' is the truthful answer. Claiming it is done would be a
    lie, and waiting for it would hold a pipeline worker for the length of a
    firmware apply.
    """
    client = FakeClient(post_result=(True, {
        '@odata.type': '#Task.v1_4_3.Task',
        '@odata.id': '/redfish/v1/TaskService/Tasks/3',
    }))
    status, message = Plugin().upload(
        redfish=client, uri='/redfish/v1/UpdateService', payload={'ImageURI': 'x'})
    assert status is True
    assert '/redfish/v1/TaskService/Tasks/3' in message


def test_a_response_carrying_a_task_state_counts_as_a_task():
    client = FakeClient(post_result=(True, {'TaskState': 'Running',
                                            '@odata.id': '/redfish/v1/TaskService/Tasks/4'}))
    _, message = Plugin().upload(redfish=client, uri='/redfish/v1/x', payload={})
    assert 'Tasks/4' in message


@pytest.mark.parametrize('uri,payload,expected', [
    (None, {'a': 1}, 'No Redfish uri given'),
    ('/redfish/v1/x', None, 'No content given to upload'),
])
def test_an_incomplete_upload_is_refused_without_a_call(uri, payload, expected):
    client = FakeClient()
    status, message = Plugin().upload(redfish=client, uri=uri, payload=payload)
    assert (status, message) == (False, expected)
    assert not client.posted


def test_a_refused_upload_reports_the_service_reason():
    client = FakeClient(post_result=(False, 'image signature invalid'))
    status, message = Plugin().upload(redfish=client, uri='/redfish/v1/x', payload={})
    assert status is False and 'signature' in message


# --- probing ----------------------------------------------------------------

def test_probe_hands_back_what_the_bmc_holds():
    client = FakeClient(resources={'/redfish/v1/': {'RedfishVersion': '1.14.0'}})
    status, response = Plugin().probe(redfish=client, uri='/redfish/v1/')
    assert status is True and response['RedfishVersion'] == '1.14.0'


def test_probe_defaults_to_the_service_root():
    client = FakeClient(resources={'/redfish/v1/': {'RedfishVersion': '1.14.0'}})
    assert Plugin().probe(redfish=client)[0] is True


# --- the contract itself ----------------------------------------------------

def test_the_plugin_reaches_for_nothing_it_was_not_given():
    """
    A plugin is a published interface: sites replace these files, and their copies
    do not upgrade with us. Every daemon import in one is an internal we can no
    longer change. This plugin is a pure function of its arguments, and the test
    is here so it stays that way -- a vendor file added later is held to the same
    bar by the README beside it.
    """
    import ast
    import inspect

    import plugins.redfish.default as module

    tree = ast.parse(inspect.getsource(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
    assert not imported & {'base', 'utils', 'common'}, (
        f'the default redfish plugin imports daemon internals: {sorted(imported)}'
    )
