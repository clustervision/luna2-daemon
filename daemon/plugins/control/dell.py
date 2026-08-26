#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
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
Plugin Class :: Dell Power Control

Dell iDRAC exposes a standards-based Redfish API. This plugin prefers Redfish
over the shared client and falls back to the default ipmitool plugin when
Redfish is unavailable or a requested Redfish action is not supported on the
target system.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.redfish import Redfish
from plugins.control.default import Plugin as DefaultPlugin


class Plugin():
    """Dell-specific control plugin."""

    def __init__(self):
        self.default = DefaultPlugin()

    def power_on(self, device=None, username=None, password=None):
        return self._reset_or_fallback(
            reset_type='On',
            fallback_method='power_on',
            success_message='on',
            device=device,
            username=username,
            password=password
        )

    def power_off(self, device=None, username=None, password=None):
        return self._reset_or_fallback(
            reset_type='ForceOff',
            fallback_method='power_off',
            success_message='off',
            device=device,
            username=username,
            password=password
        )

    def power_reset(self, device=None, username=None, password=None):
        return self._reset_or_fallback(
            reset_type='ForceRestart',
            fallback_method='power_reset',
            success_message='reset',
            device=device,
            username=username,
            password=password
        )

    def power_status(self, device=None, username=None, password=None):
        status, response = self._redfish_power_status(
            device=device,
            username=username,
            password=password
        )
        if status:
            return status, response
        return self.default.power_status(device=device, username=username, password=password)

    def power_cycle(self, device=None, username=None, password=None):
        return self._reset_or_fallback(
            reset_type='PowerCycle',
            fallback_method='power_cycle',
            success_message='cycle',
            device=device,
            username=username,
            password=password
        )

    def identify(self, device=None, username=None, password=None):
        status, response = self._redfish_set_identify(
            enabled=True,
            device=device,
            username=username,
            password=password
        )
        if status:
            return status, response
        return self.default.identify(device=device, username=username, password=password)

    def no_identify(self, device=None, username=None, password=None):
        status, response = self._redfish_set_identify(
            enabled=False,
            device=device,
            username=username,
            password=password
        )
        if status:
            return status, response
        return self.default.no_identify(device=device, username=username, password=password)

    def sel_clear(self, device=None, username=None, password=None):
        status, response = self._redfish_sel_clear(
            device=device,
            username=username,
            password=password
        )
        if status:
            return status, response
        return self.default.sel_clear(device=device, username=username, password=password)

    def sel_list(self, device=None, username=None, password=None, newlines=True):
        status, response = self._redfish_sel_list(
            device=device,
            username=username,
            password=password,
            newlines=newlines
        )
        if status:
            return status, response
        return self.default.sel_list(
            device=device,
            username=username,
            password=password,
            newlines=newlines
        )

    def _client(self, device=None, username=None, password=None):
        """
        The shared Redfish client, bound to this node's BMC. Timeout is 20
        seconds because that is what the writing half of this plugin has always
        allowed itself; a BMC that is off or unreachable still costs only the
        connect timeout.
        """
        return Redfish(device=device, username=username, password=password, timeout=20)

    def _reset_or_fallback(self, reset_type=None, fallback_method=None,
                           success_message=None, device=None, username=None,
                           password=None):
        status, response = self._redfish_reset(
            reset_type=reset_type,
            device=device,
            username=username,
            password=password
        )
        if status:
            return True, success_message
        return getattr(self.default, fallback_method)(
            device=device,
            username=username,
            password=password
        )

    def _redfish_reset(self, reset_type=None, device=None, username=None,
                       password=None):
        redfish = self._client(device=device, username=username, password=password)
        status, system_path, system_data = redfish.system()
        if not status:
            return False, system_path
        reset_target = system_data.get('Actions', {}).get('#ComputerSystem.Reset', {}).get('target')
        if not reset_target:
            return False, 'ComputerSystem.Reset action not available'
        return redfish.post(path=reset_target, payload={'ResetType': reset_type})

    def _redfish_power_status(self, device=None, username=None, password=None):
        redfish = self._client(device=device, username=username, password=password)
        status, _, system_data = redfish.system()
        if not status:
            return False, 'Unable to query system resource'
        power_state = str(system_data.get('PowerState', '')).strip().lower()
        if not power_state:
            return False, 'PowerState missing from system resource'
        return True, power_state

    def _redfish_set_identify(self, enabled=False, device=None,
                              username=None, password=None):
        redfish = self._client(device=device, username=username, password=password)
        candidates = []
        status, path, data = redfish.system()
        if status:
            candidates.append((path, data))
        status, path, data = redfish.chassis()
        if status:
            candidates.append((path, data))

        for path, data in candidates:
            if 'LocationIndicatorActive' in data:
                status, response = redfish.patch(
                    path=path,
                    payload={'LocationIndicatorActive': bool(enabled)}
                )
                if status:
                    return True, 'identify' if enabled else 'noidentify'
            if 'IndicatorLED' in data:
                desired_states = ['Lit', 'Blinking'] if enabled else ['Off']
                for state in desired_states:
                    status, response = redfish.patch(
                        path=path,
                        payload={'IndicatorLED': state}
                    )
                    if status:
                        return True, 'identify' if enabled else 'noidentify'
        return False, 'No supported Redfish identify property found'

    def _log_service_paths(self, redfish=None):
        status, _, manager_data = redfish.manager()
        if not status:
            return False, manager_data
        log_services_path = manager_data.get('LogServices', {}).get('@odata.id')
        if not log_services_path:
            return False, 'LogServices collection missing from manager resource'
        status, log_services = redfish.get(path=log_services_path)
        if not status:
            return False, log_services
        paths = []
        for member in log_services.get('Members', []):
            member_path = member.get('@odata.id')
            if member_path:
                paths.append(member_path)
        if not paths:
            return False, 'No Redfish log services found'
        return True, paths

    def _redfish_sel_clear(self, device=None, username=None, password=None):
        redfish = self._client(device=device, username=username, password=password)
        status, service_paths = self._log_service_paths(redfish=redfish)
        if not status:
            return False, service_paths

        cleared = []
        errors = []
        for service_path in service_paths:
            service_status, service_data = redfish.get(path=service_path)
            if not service_status:
                errors.append(service_data)
                continue
            clear_target = service_data.get('Actions', {}).get('#LogService.ClearLog', {}).get('target')
            if not clear_target:
                continue
            clear_status, clear_response = redfish.post(path=clear_target, payload={})
            if clear_status:
                cleared.append(service_path)
            else:
                errors.append(clear_response)

        if cleared:
            return True, f'cleared {len(cleared)} Redfish log service(s)'
        if errors:
            return False, '; '.join(errors)
        return False, 'No Redfish log service exposes ClearLog'

    def _format_log_entry(self, service_path=None, entry_data=None):
        entry_id = entry_data.get('Id', '?')
        created = entry_data.get('Created', '')
        severity = entry_data.get('Severity', '')
        name = entry_data.get('Name', '')
        message = entry_data.get('Message', '') or entry_data.get('MessageId', '')
        parts = [f'[{service_path}]', f'id={entry_id}']
        if created:
            parts.append(f'created={created}')
        if severity:
            parts.append(f'severity={severity}')
        if name:
            parts.append(f'name={name}')
        if message:
            parts.append(f'message={message}')
        return ' '.join(parts)

    def _redfish_sel_list(self, device=None, username=None, password=None,
                          newlines=True):
        redfish = self._client(device=device, username=username, password=password)
        status, service_paths = self._log_service_paths(redfish=redfish)
        if not status:
            return False, service_paths

        lines = []
        for service_path in service_paths:
            service_status, service_data = redfish.get(path=service_path)
            if not service_status:
                continue
            entries_path = service_data.get('Entries', {}).get('@odata.id')
            if not entries_path:
                entries_path = service_path.rstrip('/') + '/Entries'
            entries_status, entries_data = redfish.get(path=entries_path)
            if not entries_status:
                continue
            members = entries_data.get('Members', [])
            if not members:
                lines.append(f'[{service_path}] no log entries')
                continue
            for member in members:
                if isinstance(member, dict) and '@odata.id' in member:
                    entry_status, entry_data = redfish.get(path=member['@odata.id'])
                    if not entry_status:
                        continue
                else:
                    entry_data = member
                lines.append(self._format_log_entry(service_path=service_path, entry_data=entry_data))

        if not lines:
            return False, 'No Redfish log entries found'

        response = '\n'.join(lines)
        if not newlines:
            response = response.replace('\n', '')
        return True, response
