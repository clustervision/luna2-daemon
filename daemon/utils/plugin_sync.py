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
Synchronize boot plugin files between HA controllers.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from time import sleep
import os
import sys
from common.constant import CONSTANT
from utils.log import Log
from base.plugin_export import Export
from base.plugin_import import Import
from utils.ha import HA
from utils.journal import Journal


class PluginSync(object):

    def __init__(self):
        self.logger = Log.get_logger()
        self.boot_plugins_fingerprint = None

    def _boot_plugins_directories(self):
        plugin_path = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        return {
            'roles': f'{plugin_path}/boot/roles',
            'scripts': f'{plugin_path}/boot/scripts',
        }

    def _boot_plugins_fingerprint(self):
        fingerprint = []
        for section, directory in self._boot_plugins_directories().items():
            if not os.path.isdir(directory):
                fingerprint.append((section, '__missing__'))
                continue
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith('.py'):
                    continue
                filepath = f'{directory}/{filename}'
                if not os.path.isfile(filepath):
                    continue
                stat_result = os.stat(filepath)
                fingerprint.append((section, filename, stat_result.st_mtime_ns, stat_result.st_size))
        return tuple(fingerprint)

    def _boot_plugin_changes(self, previous_fingerprint, current_fingerprint):
        previous_map = {}
        current_map = {}

        for entry in previous_fingerprint or []:
            if len(entry) == 4:
                previous_map[(entry[0], entry[1])] = entry[2:]
        for entry in current_fingerprint or []:
            if len(entry) == 4:
                current_map[(entry[0], entry[1])] = entry[2:]

        changes = []
        all_files = sorted(set(previous_map.keys()) | set(current_map.keys()))
        for section, filename in all_files:
            key = (section, filename)
            if key not in previous_map:
                changes.append(f'added {section}/{filename}')
            elif key not in current_map:
                changes.append(f'removed {section}/{filename}')
            elif previous_map[key] != current_map[key]:
                changes.append(f'updated {section}/{filename}')
        return changes

    def sync_boot_plugins(self):
        status, payload = Export().plugin('boot_plugins')
        if not status:
            self.logger.error(f'boot plugin sync export failed: {payload}')
            return False

        journal_status, journal_response = Journal().add_request(
            function='Import.plugin',
            object='boot_plugins',
            payload=payload,
        )
        if not journal_status:
            self.logger.error(f'boot plugin sync journal failed: {journal_response}')
            return False

        # We, ourselves do not need to copy. This code kept in place for future use.
        #import_status, import_response = Import().plugin('boot_plugins', payload)
        #if not import_status:
        #    self.logger.error(f'boot plugin sync import failed: {import_response}')
        #    return False

        self.logger.info('boot plugin synchronization completed')
        return True

    def boot_plugins_mother(self,event):
        self.logger.info('Starting boot plugin sync watcher thread')
        ha_object = HA()
        interval = 5
        while True:
            try:
                if event.is_set():
                    return
                if not ha_object.get_hastate():
                    self.boot_plugins_fingerprint = self._boot_plugins_fingerprint()
                    sleep(interval)
                    continue
                current_fingerprint = self._boot_plugins_fingerprint()
                if not ha_object.get_role():
                    if self.boot_plugins_fingerprint is not None and current_fingerprint != self.boot_plugins_fingerprint:
                        changes = self._boot_plugin_changes(self.boot_plugins_fingerprint, current_fingerprint)
                        change_summary = ', '.join(changes) if changes else 'unknown change'
                        self.logger.warning(f'Detected local boot plugin change on passive controller: {change_summary}')
                    self.boot_plugins_fingerprint = current_fingerprint
                    sleep(interval)
                    continue
                if self.boot_plugins_fingerprint is None:
                    self.boot_plugins_fingerprint = current_fingerprint
                elif current_fingerprint != self.boot_plugins_fingerprint:
                    changes = self._boot_plugin_changes(self.boot_plugins_fingerprint, current_fingerprint)
                    if changes:
                        change_summary = ', '.join(changes)
                        self.logger.info(f'Detected local boot plugin change on HA master: {change_summary}')
                    else:
                        self.logger.info('Detected local boot plugin change on HA master, synchronizing to controllers')
                    if self.sync_boot_plugins():
                        current_fingerprint = self._boot_plugins_fingerprint()
                    self.boot_plugins_fingerprint = current_fingerprint
                sleep(interval)
            except Exception as exp:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                self.logger.error(f'boot_plugins_mother thread encountered problem: {exp}, {exc_type}, in {exc_tb.tb_lineno}')
                sleep(interval)
