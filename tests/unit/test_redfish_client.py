#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-178 unit tests for the shared Redfish client.

Every case here runs against a stand-in session rather than a BMC, which is the
whole reason the client exists as its own class: the discovery walk and the error
paths are the parts most likely to be wrong and the parts hardest to reach on real
hardware.
"""

from json import dumps, loads

import requests

import pytest

from utils.redfish import Redfish, RedfishAccess


class FakeResponse():
    """Just enough of a requests response for the client to read."""

    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self.payload = payload
        if text is None:
            text = dumps(payload) if payload is not None else ''
        self.text = text
        self.content = text.encode()

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self.payload is None:
            raise ValueError('not json')
        return self.payload


class FakeSession():
    """Records what was asked for and answers from a path -> response map."""

    def __init__(self, routes=None, raises=None):
        self.routes = routes or {}
        self.raises = raises
        self.calls = []
        self.headers = {}
        self.auth = None
        self.verify = None

    def request(self, method, url, data=None, headers=None, timeout=None):
        path = url.split('//', 1)[-1]
        path = path[path.index('/'):] if '/' in path else '/'
        self.calls.append({'method': method, 'url': url, 'path': path,
                           'data': data, 'headers': headers})
        if self.raises:
            raise self.raises
        answer = self.routes.get((method, path), self.routes.get(path))
        if answer is None:
            return FakeResponse(status_code=404, payload={'error': {'message': 'not found'}})
        return answer


def client(routes=None, raises=None, **kwargs):
    """A Redfish client whose transport is a FakeSession."""
    redfish = Redfish(device='192.0.2.10', username='u', password='p', **kwargs)
    redfish.session = FakeSession(routes=routes, raises=raises)
    return redfish


# --- addressing -------------------------------------------------------------

@pytest.mark.parametrize('device,port,expected', [
    ('192.0.2.10', None, '192.0.2.10'),
    ('192.0.2.10', 8443, '192.0.2.10:8443'),
    ('bmc.example.com', None, 'bmc.example.com'),
    ('2001:db8::1', None, '[2001:db8::1]'),
    ('2001:db8::1', 8443, '[2001:db8::1]:8443'),
    ('[2001:db8::1]', None, '[2001:db8::1]'),
])
def test_a_bmc_address_of_either_family_makes_a_usable_url(device, port, expected):
    """
    A BMC address can be IPv6, and a bare IPv6 address makes a URL unparsable --
    https://2001:db8::1/ reads its first colon as the port separator. Brackets are
    what the URL grammar requires, and nothing else in the client can recover from
    getting this wrong.
    """
    assert Redfish(device=device).netloc(device, port) == expected


# --- what an operator is told when a BMC refuses ----------------------------

@pytest.mark.parametrize('data,expected', [
    ({'error': {'@Message.ExtendedInfo': [{'Message': 'BootMode is read only'}]}},
     'BootMode is read only'),
    ({'@Message.ExtendedInfo': [{'MessageId': 'Base.1.0.PropertyNotWritable'}]},
     'Base.1.0.PropertyNotWritable'),
    ({'error': {'message': 'A general error has occurred'}},
     'A general error has occurred'),
    ('plain text refusal', 'plain text refusal'),
    ({}, 'Redfish HTTP 400'),
])
def test_the_reason_a_bmc_gives_is_what_gets_reported(data, expected):
    """
    Redfish puts the human-readable reason in the extended info, not in the status
    line. Without digging it out an operator only ever sees 'Redfish HTTP 400',
    which says nothing about which attribute the service refused or why.
    """
    assert Redfish(device='192.0.2.10').reason(data, 400) == expected


def test_an_unreachable_bmc_names_itself_in_the_failure():
    """A hostlist run reports per node, so the node's own address has to be in the message."""
    import requests
    redfish = client(raises=requests.exceptions.ConnectTimeout('timed out'))
    status, data = redfish.get(path='/redfish/v1/')
    assert status is False
    assert '192.0.2.10' in data


def test_a_refused_call_reports_the_service_reason_not_the_body():
    redfish = client(routes={
        '/redfish/v1/Systems/1': FakeResponse(
            status_code=400,
            payload={'error': {'@Message.ExtendedInfo': [{'Message': 'read only'}]}})
    })
    status, data = redfish.get(path='/redfish/v1/Systems/1')
    assert (status, data) == (False, 'read only')


def test_a_missing_device_is_refused_before_a_request_is_built():
    status, _, message = Redfish(device=None).call()
    assert status is False and 'No BMC address' in message


# --- discovery --------------------------------------------------------------

ROOT = FakeResponse(payload={
    'Systems': {'@odata.id': '/redfish/v1/Systems'},
    'Managers': {'@odata.id': '/redfish/v1/Managers'},
    'Chassis': {'@odata.id': '/redfish/v1/Chassis'},
})


def test_discovery_walks_root_to_collection_to_first_member():
    redfish = client(routes={
        '/redfish/v1/': ROOT,
        '/redfish/v1/Systems': FakeResponse(payload={
            'Members': [{'@odata.id': '/redfish/v1/Systems/1'}]}),
        '/redfish/v1/Systems/1': FakeResponse(payload={'PowerState': 'On'}),
    })
    status, path, data = redfish.system()
    assert status is True
    assert path == '/redfish/v1/Systems/1'
    assert data['PowerState'] == 'On'


def test_a_collection_missing_from_the_root_says_which_one():
    redfish = client(routes={'/redfish/v1/': FakeResponse(payload={})})
    status, message, _ = redfish.chassis()
    assert status is False and 'Chassis' in message


def test_an_empty_collection_is_not_a_silent_success():
    redfish = client(routes={
        '/redfish/v1/': ROOT,
        '/redfish/v1/Managers': FakeResponse(payload={'Members': []}),
    })
    status, message, _ = redfish.manager()
    assert status is False and 'No members' in message


def test_the_service_root_is_read_once_per_client():
    """
    dell.py re-fetched the root on every call, so power status cost three round
    trips where it should cost two. Invisible on four nodes; eight thousand wasted
    requests on a sweep of four thousand.
    """
    redfish = client(routes={
        '/redfish/v1/': ROOT,
        '/redfish/v1/Systems': FakeResponse(payload={
            'Members': [{'@odata.id': '/redfish/v1/Systems/1'}]}),
        '/redfish/v1/Systems/1': FakeResponse(payload={'PowerState': 'On'}),
    })
    redfish.system()
    redfish.system()
    roots = [call for call in redfish.session.calls if call['path'] == '/redfish/v1/']
    assert len(roots) == 1


# --- writing ----------------------------------------------------------------

def test_a_patch_returns_the_services_etag_as_if_match():
    """iDRAC and AMI refuse a PATCH that does not carry the ETag they published."""
    redfish = client(routes={
        ('GET', '/redfish/v1/Systems/1'): FakeResponse(payload={'@odata.etag': 'W/"abc"'}),
        ('PATCH', '/redfish/v1/Systems/1'): FakeResponse(status_code=204),
    })
    status, _ = redfish.patch(path='/redfish/v1/Systems/1', payload={'AssetTag': 'x'})
    patch_call = [c for c in redfish.session.calls if c['method'] == 'PATCH'][0]
    assert status is True
    assert patch_call['headers'] == {'If-Match': 'W/"abc"'}


def test_a_resource_without_an_etag_gets_no_if_match_header():
    """
    The header is omitted rather than invented. A service that then refuses the
    write is telling us something, and faking a value would hide it.
    """
    redfish = client(routes={
        ('GET', '/redfish/v1/Systems/1'): FakeResponse(payload={'AssetTag': 'x'}),
        ('PATCH', '/redfish/v1/Systems/1'): FakeResponse(status_code=204),
    })
    redfish.patch(path='/redfish/v1/Systems/1', payload={'AssetTag': 'y'})
    patch_call = [c for c in redfish.session.calls if c['method'] == 'PATCH'][0]
    assert patch_call['headers'] is None


def test_the_body_reaches_the_service_as_json():
    redfish = client(routes={('POST', '/redfish/v1/act'): FakeResponse(status_code=204)})
    redfish.post(path='/redfish/v1/act', payload={'ResetType': 'On'})
    assert loads(redfish.session.calls[0]['data']) == {'ResetType': 'On'}


# --- long running work ------------------------------------------------------

def test_a_finished_task_reports_completion():
    redfish = client(routes={'/redfish/v1/TaskService/Tasks/1':
                             FakeResponse(payload={'TaskState': 'Completed'})})
    assert redfish.poll_task(location='/redfish/v1/TaskService/Tasks/1')[0] is True


def test_a_failed_task_reports_the_service_reason():
    redfish = client(routes={'/redfish/v1/TaskService/Tasks/1': FakeResponse(payload={
        'TaskState': 'Exception',
        '@Message.ExtendedInfo': [{'Message': 'image rejected'}]})})
    status, message = redfish.poll_task(location='/redfish/v1/TaskService/Tasks/1')
    assert status is False and message == 'image rejected'


def test_polling_is_bounded_and_says_so():
    """
    The control pipeline holds a worker for the length of the call, so this may
    never wait indefinitely -- work that genuinely takes minutes belongs in the
    queue. Reaching the deadline is reported, not swallowed.
    """
    redfish = client(routes={'/redfish/v1/TaskService/Tasks/1':
                             FakeResponse(payload={'TaskState': 'Running'})})
    status, message = redfish.poll_task(location='/redfish/v1/TaskService/Tasks/1', deadline=0)
    assert status is False and 'still' in message


def test_no_task_location_is_refused_rather_than_polled():
    assert Redfish(device='192.0.2.10').poll_task(location=None)[0] is False


# --- which account a node is reached with -----------------------------------

def accounts(*roles):
    return [{'name': role or 'unroled', 'username': f'u{n}', 'password': 'p', 'role': role}
            for n, role in enumerate(roles)]


def test_a_write_takes_the_weakest_account_that_may_write():
    picked = RedfishAccess().pick_account(
        accounts=accounts('ReadOnly', 'Operator', 'Administrator'), write=True)
    assert picked['role'] == 'Administrator'


def test_a_read_takes_the_weakest_account_of_all():
    picked = RedfishAccess().pick_account(
        accounts=accounts('ReadOnly', 'Operator', 'Administrator'), write=False)
    assert picked['role'] == 'ReadOnly'


def test_an_account_without_a_role_is_usable_for_anything():
    """
    Roles are optional, and that is what keeps the simple case simple: one account
    with no role behaves exactly as a cluster does today. It also has to beat an
    account whose role is wrong for the job.
    """
    picked = RedfishAccess().pick_account(accounts=accounts('ReadOnly', None), write=True)
    assert picked['role'] is None


def test_a_single_administrator_account_behaves_as_today():
    for write in (True, False):
        picked = RedfishAccess().pick_account(accounts=accounts('Administrator'), write=write)
        assert picked['username'] == 'u0'


def test_a_role_the_daemon_does_not_rank_still_gets_used():
    """A vendor role name we have never heard of must not strand the node."""
    picked = RedfishAccess().pick_account(accounts=accounts('OemPowerOnly'), write=True)
    assert picked['role'] == 'OemPowerOnly'


# --- why a BMC could not be reached, in a few words -------------------------

@pytest.mark.parametrize('exception,expected', [
    (requests.exceptions.ConnectTimeout('...'), 'connect timed out after 5s'),
    (requests.exceptions.ReadTimeout('...'), 'no answer within 15s'),
    (requests.exceptions.SSLError('...'), 'TLS handshake failed'),
    (requests.exceptions.ConnectionError('...'), 'connection refused or host unreachable'),
])
def test_a_transport_failure_is_reported_in_a_few_words(exception, expected):
    """
    The raw exception is a paragraph of urllib3 internals - the pool object, the
    retry count, the nested cause - and a hostlist run prints one per node into a
    fixed-width column. Observed on a live controller: a single unreachable BMC
    produced a 250-character status cell. What an operator needs is which of the
    handful of things went wrong.
    """
    assert expected in Redfish(device='192.0.2.10').transport_reason(exception)


def test_an_unknown_transport_failure_is_still_bounded():
    """Whatever it is, it must not blow the column apart."""
    reason = Redfish(device='192.0.2.10').transport_reason(
        requests.exceptions.RequestException('x' * 500))
    assert len(reason) <= 120


def test_the_node_address_is_still_in_the_message():
    """Per-node reporting is worthless if the line does not say which node."""
    redfish = client(raises=requests.exceptions.ConnectTimeout('boom'))
    status, data = redfish.get(path='/redfish/v1/')
    assert status is False
    assert data == '192.0.2.10: connect timed out after 5s'
