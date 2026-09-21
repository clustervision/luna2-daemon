#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Test bootstrap and shared fixtures.

The daemon's ``common.constant`` reads ``/trinity/local/luna/daemon/config/luna.ini``
and a key file at import time, and aborts when they are absent. That makes every
``utils.*`` / ``common.*`` module unimportable outside a real deployment.

To test the real code unchanged, we inject a minimal stand-in ``common.constant``
into ``sys.modules`` before any daemon module is imported. pytest loads this
conftest before collecting test modules, so the stub is in place in time.
"""

import ipaddress
import os
import socket
import sys
import types

from cryptography.fernet import Fernet

# A real, valid Fernet key so encrypt/decrypt exercises the genuine cipher path.
_LUNAKEY = Fernet.generate_key().decode()


def _install_constant_stub():
    """Put a minimal common.constant in sys.modules before the daemon imports it."""
    if "common.constant" in sys.modules:
        return
    stub = types.ModuleType("common.constant")
    stub.CONSTANT = {
        "LOGGER": {"LEVEL": "error", "LOGFILE": None},
        "API": {"USERNAME": "luna", "PASSWORD": "luna", "EXPIRY": "1h",
                "SECRET_KEY": "test", "ENDPOINT": "localhost:7050", "PROTOCOL": "http",
                "VERIFY_CERTIFICATE": "no"},
        "DATABASE": {"DRIVER": "SQLite3", "DATABASE": ":memory:",
                     "DBUSER": "", "DBPASSWORD": "", "HOST": "", "PORT": ""},
        "FILES": {"KEYFILE": None, "IMAGE_FILES": None, "IMAGE_DIRECTORY": None,
                  "MAXPACKAGINGTIME": None, "TMP_DIRECTORY": None},
        "SECRETS": {"ENCRYPT_SECRETS": "yes"},
        "PLUGINS": {"PLUGINS_DIRECTORY": None, "IMAGE_FILESYSTEM": "default"},
        "SERVICES": {}, "DHCP": {},
        "BMCCONTROL": {"BMC_BATCH_SIZE": "10", "BMC_BATCH_DELAY": "0"}, "TEMPLATES": {},
    }
    # base/cluster.py imports this name and reports it as a path; nothing opens it here.
    stub.CONFIGFILE = '/trinity/local/luna/daemon/config/luna.ini'
    stub.LUNAKEY = _LUNAKEY
    sys.modules["common.constant"] = stub


_install_constant_stub()

# Safe to import now: the stub satisfies the import-time dependency.
import pytest
from utils.log import Log

Log.init_log("error")


@pytest.fixture(scope="session")
def constant():
    """The stubbed CONSTANT dict, so tests can read or tweak config values."""
    return sys.modules["common.constant"].CONSTANT


@pytest.fixture
def helper():
    """A Helper instance backed by the stubbed configuration."""
    from utils.helper import Helper
    return Helper()


@pytest.fixture
def config():
    """A Config instance backed by the stubbed configuration."""
    from utils.config import Config
    return Config()


@pytest.fixture
def sqlite_db_path(tmp_path):
    """
    A fresh, EMPTY temporary SQLite database wired into the daemon's config.

    Points the stubbed DATABASE at a temp file and clears the cached thread
    connection so Database() binds to it. No schema is created -- use this when
    the test itself builds the tables (e.g. exercising create_database_tables).
    """
    constant = sys.modules["common.constant"].CONSTANT
    original = constant["DATABASE"]["DATABASE"]
    db_path = str(tmp_path / "luna-test.db")
    constant["DATABASE"]["DATABASE"] = db_path

    from utils import database as database_module

    # Database caches a per-thread connection; drop any cached one so this test
    # binds to the temp file rather than a connection from an earlier test.
    _reset_thread_connection(database_module)

    yield db_path

    _reset_thread_connection(database_module)
    constant["DATABASE"]["DATABASE"] = original


@pytest.fixture
def sqlite_db(sqlite_db_path):
    """
    A temporary, schema-complete SQLite database for regression tests.

    Builds every table from the daemon's own database_layout definitions on top
    of sqlite_db_path. The daemon's Database() picks up the path through
    CONSTANT, so the real data layer is exercised, not a mock.
    """
    from utils.database import Database
    from utils.dbstructure import DBStructure

    structure = DBStructure()
    for table in structure.tables:
        Database().create(table, structure.get_database_table_structure(table))
    return sqlite_db_path


def _reset_thread_connection(database_module):
    """Close and clear the daemon's cached thread-local DB connection."""
    local_thread = database_module.local_thread
    connection = getattr(local_thread, "connection", None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass
    local_thread.connection = None
    local_thread.cursor = None


# ── no test reaches the network ─────────────────────────────────────────────
# A sweep that a test starts in a background pool can connect to a seeded BMC address
# after the test has returned; nothing waits for it, and interpreter shutdown does.
# Every non-loopback connect is refused at once and remembered with the test that was
# running, so the run exits and the report names the culprit (TRIX-2132).

_REACHED = []
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


def _offsite(sock, address):
    if sock.family not in (socket.AF_INET, socket.AF_INET6) or not isinstance(address, tuple):
        return False
    try:
        return not ipaddress.ip_address(address[0]).is_loopback
    except ValueError:
        return address[0] not in ('localhost',)


def _guarded_connect(sock, address):
    if _offsite(sock, address):
        _REACHED.append((address, os.environ.get('PYTEST_CURRENT_TEST', '<outside a test>')))
        raise ConnectionRefusedError(f'test reached the network: {address}')
    return _REAL_CONNECT(sock, address)


def _guarded_connect_ex(sock, address):
    if _offsite(sock, address):
        _REACHED.append((address, os.environ.get('PYTEST_CURRENT_TEST', '<outside a test>')))
        return 111
    return _REAL_CONNECT_EX(sock, address)


@pytest.fixture(scope="session", autouse=True)
def no_network(request):
    request.config.network_reached = _REACHED
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    yield
    socket.socket.connect = _REAL_CONNECT
    socket.socket.connect_ex = _REAL_CONNECT_EX


def pytest_sessionfinish(session, exitstatus):
    if _REACHED:
        lines = [f"  {test}  ->  {address[0]}:{address[1]}" for address, test in _REACHED]
        session.config.pluginmanager.get_plugin('terminalreporter').write_sep(
            '=', 'tests reached the network (TRIX-2132); stub the transport in:', red=True)
        session.config.pluginmanager.get_plugin('terminalreporter').write_line('\n'.join(lines))
        session.exitstatus = 1
