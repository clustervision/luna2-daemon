#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Start sushy-tools' Redfish emulator with a BIOS-capable driver.

Only the driver class is substituted. Everything that goes over the wire - the
routes, the @Redfish.Settings annotation, the settings object pointer, the JSON
templates, the auth and the error bodies - is sushy-tools', which is the entire
point of testing our client against it rather than against our own fake.

See README.md in this directory for what that does and does not prove.

    ~/sushy-emu-venv/bin/python tests/emulator/launch.py [--port 8000]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sushy_tools.emulator.resources.systems import fakedriver     # noqa: E402
from biosdriver import BiosFakeDriver                             # noqa: E402

fakedriver.FakeDriver = BiosFakeDriver          # before the app builds its driver

from sushy_tools.emulator import main           # noqa: E402

# Matches the default in tests/unit/test_bios_against_emulator.py. Override both
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
