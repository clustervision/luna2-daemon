#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Regenerate the plugin_selection.json golden from the current selection behaviour.

Run this ONLY after an intended change to plugin selection, or after adding a plugin root or
a plugin file that legitimately changes what gets picked, then read the diff before
committing. Every moved line is a claim that the new module is the correct one for that
candidate shape -- an unexplained move is a regression, not a file to refresh.

    python tests/regression/regen_plugin_selection.py
"""

import os
import sys
import tempfile
import types

from cryptography.fernet import Fernet

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'daemon'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))

_stub = types.ModuleType('common.constant')
_stub.CONSTANT = {
    'LOGGER': {'LEVEL': 'error', 'LOGFILE': None},
    'DATABASE': {'DRIVER': 'SQLite3', 'DATABASE': ':memory:'},
    'FILES': {'KEYFILE': None}, 'SECRETS': {'ENCRYPT_SECRETS': 'yes'},
    'API': {}, 'SERVICES': {}, 'PLUGINS': {}, 'TEMPLATES': {}, 'BMCCONTROL': {}, 'DHCP': {},
}
_stub.LUNAKEY = Fernet.generate_key().decode()
sys.modules['common.constant'] = _stub

from utils.log import Log  # noqa: E402

Log.init_log('error')

from cases.plugin_selection_cases import build_selection_map, dumps  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), 'golden', 'plugin_selection.json')
PLUGINS = os.path.join(ROOT, 'daemon', 'plugins')


def main():
    with tempfile.TemporaryDirectory() as workdir:
        selection_map = build_selection_map(PLUGINS, workdir)
    with open(GOLDEN, 'w', encoding='utf-8') as handle:
        handle.write(dumps(selection_map))
    print(f'wrote {GOLDEN}: {len(selection_map["roots"])} roots, '
          f'{len(selection_map["selection"])} resolutions')


if __name__ == '__main__':
    main()
