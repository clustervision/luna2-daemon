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
                "SECRET_KEY": "test", "ENDPOINT": "localhost:7050", "PROTOCOL": "http"},
        "DATABASE": {"DRIVER": "SQLite3", "DATABASE": ":memory:",
                     "DBUSER": "", "DBPASSWORD": "", "HOST": "", "PORT": ""},
        "FILES": {"KEYFILE": None, "IMAGE_FILES": None, "IMAGE_DIRECTORY": None,
                  "MAXPACKAGINGTIME": None, "TMP_DIRECTORY": None},
        "SECRETS": {"ENCRYPT_SECRETS": "yes"},
        "PLUGINS": {"PLUGINS_DIRECTORY": None, "IMAGE_FILESYSTEM": "default"},
        "SERVICES": {}, "DHCP": {}, "BMCCONTROL": {}, "TEMPLATES": {},
    }
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
def sqlite_db(tmp_path):
    """
    A temporary, schema-complete SQLite database for regression tests.

    Points the stubbed DATABASE at a temp file, builds every table from the
    daemon's own database_layout definitions, and yields the file path. The
    daemon's Database() picks up the path through CONSTANT, so the real data
    layer is exercised, not a mock.
    """
    constant = sys.modules["common.constant"].CONSTANT
    original = constant["DATABASE"]["DATABASE"]
    db_path = str(tmp_path / "luna-test.db")
    constant["DATABASE"]["DATABASE"] = db_path

    from utils import database as database_module
    from utils.database import Database
    from utils.dbstructure import DBStructure

    # Database caches a per-thread connection; drop any cached one so this test
    # binds to the temp file rather than a connection from an earlier test.
    _reset_thread_connection(database_module)

    structure = DBStructure()
    for table in structure.tables:
        Database().create(table, structure.get_database_table_structure(table))

    yield db_path

    _reset_thread_connection(database_module)
    constant["DATABASE"]["DATABASE"] = original


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
