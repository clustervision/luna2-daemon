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
Export boot role and script plugins for HA synchronization.
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
from base64 import b64encode
from common.constant import CONSTANT
from utils.log import Log


class Plugin():
    """
    Class for exporting boot plugin files.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.plugins_path = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.export_roots = {
            'roles': f'{self.plugins_path}/boot/roles',
            'scripts': f'{self.plugins_path}/boot/scripts',
        }

    def _encode_file(self, filepath):
        with open(filepath, 'rb') as file_handle:
            content = file_handle.read()
        encoded = b64encode(content).decode('ascii')
        stat_data = os.stat(filepath)
        checksum = hashlib.sha256(content).hexdigest()
        return {
            'content_b64': encoded,
            'sha256': checksum,
            'mode': stat_data.st_mode & 0o777,
        }

    def _export_directory(self, directory):
        data = {}
        if not os.path.isdir(directory):
            raise FileNotFoundError(f'{directory} is not available')
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith('.py'):
                continue
            filepath = f'{directory}/{filename}'
            if not os.path.isfile(filepath):
                continue
            data[filename] = self._encode_file(filepath)
        return data

    def Export(self,args=None):
        payload = {'version': 1}
        try:
            for section, directory in self.export_roots.items():
                payload[section] = self._export_directory(directory)
        except Exception as exp:
            self.logger.error(f'Failed to export boot plugins: {exp}')
            return False, f'Failed to export boot plugins: {exp}'
        return True, payload
