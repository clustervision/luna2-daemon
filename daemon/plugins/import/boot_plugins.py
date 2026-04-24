#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Import boot role and script plugins for HA synchronization.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import hashlib
import os
from base64 import b64decode
from common.constant import CONSTANT
from utils.log import Log


class Plugin():
    """
    Class for importing boot plugin files.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.plugins_path = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.import_roots = {
            'roles': f'{self.plugins_path}/boot/roles',
            'scripts': f'{self.plugins_path}/boot/scripts',
        }

    def _validate_payload(self, payload):
        if not isinstance(payload, dict):
            return False, 'boot plugins payload must be a dictionary'
        for section in self.import_roots.keys():
            if section not in payload:
                return False, f'missing payload section {section}'
            if not isinstance(payload[section], dict):
                return False, f'payload section {section} must be a dictionary'
        return True, 'ok'

    def _write_file(self, directory, filename, metadata):
        if '/' in filename or filename.startswith('.') or not filename.endswith('.py'):
            raise ValueError(f'invalid boot plugin filename {filename}')
        if 'content_b64' not in metadata:
            raise ValueError(f'missing content_b64 for {filename}')
        content = b64decode(metadata['content_b64'])
        checksum = hashlib.sha256(content).hexdigest()
        if metadata.get('sha256') and metadata['sha256'] != checksum:
            raise ValueError(f'checksum mismatch for {filename}')
        mode = metadata.get('mode', 0o644)
        final_path = f'{directory}/{filename}'
        temp_path = f'{directory}/.{filename}.tmp'
        if os.path.exists(final_path):
            self.logger.info(f'Passive/non-master overwriting plugin file {final_path}')
        else:
            self.logger.info(f'Passive/non-master creating plugin file {final_path}')
        with open(temp_path, 'wb') as file_handle:
            file_handle.write(content)
        os.chmod(temp_path, mode)
        os.replace(temp_path, final_path)

    def _sync_directory(self, directory, desired_files):
        existing = set()
        for filename in os.listdir(directory):
            if filename.endswith('.py') and os.path.isfile(f'{directory}/{filename}'):
                existing.add(filename)
        desired = set(desired_files.keys())
        for filename, metadata in desired_files.items():
            self._write_file(directory, filename, metadata)
        stale = sorted(existing - desired)
        for filename in stale:
            os.unlink(f'{directory}/{filename}')

    def Import(self, json_data=None):
        status, message = self._validate_payload(json_data)
        if not status:
            self.logger.error(message)
            return False, message
        try:
            for section, directory in self.import_roots.items():
                if not os.path.isdir(directory):
                    raise FileNotFoundError(f'{directory} is not available')
                self._sync_directory(directory, json_data[section])
        except Exception as exp:
            self.logger.error(f'Failed to import boot plugins: {exp}')
            return False, f'Failed to import boot plugins: {exp}'
        return True, 'boot plugins synchronized'
