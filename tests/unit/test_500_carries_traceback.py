#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2212: a 500 caused by an uncaught exception carries that exception's full
traceback as detail, next to the Server Error message every client already reads.
The daemon does not filter it; what to show is decided by the CLI and the GUI.
A deliberate abort(500) has no exception behind it and carries no detail.
"""

import json
import logging
import sys

import pytest
from flask import abort

# luna.py imports the daemon-wide logger from the module the suite stubs.
if not hasattr(sys.modules['common.constant'], 'LOGGER'):
    sys.modules['common.constant'].LOGGER = logging.getLogger('luna2-daemon-tests')

import luna


@luna.daemon.route('/tests/raise')
def raising():
    raise RuntimeError('qa2212 test')


@luna.daemon.route('/tests/abort')
def aborting():
    abort(500)


@pytest.fixture(name='client')
def client_fixture():
    return luna.daemon.test_client()


def test_an_uncaught_exception_answers_server_error_with_its_traceback(client):
    response = client.get('/tests/raise')
    body = json.loads(response.data)
    assert response.status_code == 500
    assert body['message'] == 'Server Error'
    detail = body.get('detail')
    assert detail, 'the 500 carries no detail'
    assert detail.startswith('Traceback (most recent call last):\n')
    assert ', in raising\n' in detail
    assert detail.rstrip('\n').endswith('RuntimeError: qa2212 test')


def test_a_deliberate_abort_carries_no_detail(client):
    response = client.get('/tests/abort')
    assert response.status_code == 500
    assert json.loads(response.data) == {'message': 'Server Error'}
