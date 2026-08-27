#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Start sushy-tools' Redfish emulator for tests/unit/test_bios_against_emulator.py.

Nothing here is substituted or subclassed: the driver, the routes, the staging
and every byte that goes over the wire are sushy-tools'. That is the point - our
client is being tested against somebody else's reading of the specification, and
anything of ours in the path would weaken it.

See README.md in this directory for what it does and does not prove, and for why
it currently wants sushy-tools from source rather than from PyPI.

    ~/sushy-emu-venv/bin/python tests/emulator/launch.py [--port 8000]
"""

import argparse
import os

from sushy_tools.emulator import main

# Matches the default in tests/unit/test_bios_against_emulator.py. Change both
# together, or the tests will not find the system they ask for.
SYSTEM_UUID = '27946b59-9e44-4fa7-8e91-f3527a1ef094'


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--state-dir',
                        default=os.path.join(os.path.dirname(
                            os.path.abspath(__file__)), 'state'),
                        help='where the emulator keeps its machines between runs')
    args = parser.parse_args()

    main.app.config.update(
        SUSHY_EMULATOR_FEATURE_SET='full',
        SUSHY_EMULATOR_FAKE_DRIVER=True,
        SUSHY_EMULATOR_STATE_DIR=args.state_dir,
        SUSHY_EMULATOR_FAKE_SYSTEMS=[{
            'uuid': SYSTEM_UUID,
            'name': 'emu-node',
            'power_state': 'On',
            'external_notifier': False,
            'boot_device': 'Hdd',
            'boot_mode': 'UEFI',
            'secure_boot': False,
            'nics': [{'mac': '00:5c:52:31:3a:9c', 'ip': '172.22.0.100'}],
        }],
    )
    main.app.run(host=args.interface, port=args.port)


if __name__ == '__main__':
    run()
