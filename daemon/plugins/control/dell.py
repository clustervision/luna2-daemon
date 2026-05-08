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

Dell iDRAC exposes a standards-based Redfish API. This plugin prefers
Redfish over HTTPS through curl and falls back to the default ipmitool
plugin when Redfish is unavailable or a requested Redfish action is not
supported on the target system.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import json
import shlex

from utils.helper import Helper
from plugins.control.default import Plugin as DefaultPlugin


class Plugin():
    """Dell-specific control plugin."""

    def __init__(self):
        self.helper = Helper()
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

    def _curl_json(self, device=None, username=None, password=None,
                   method='GET', path='/redfish/v1/', payload=None,
                   timeout=15):
        if not all([device, username, password]):
            return False, 0, 'Missing Redfish device or credentials'

        url = f'https://{device}{path}'
        command = 'curl -sSk'
        command += f' --connect-timeout 5 -m {int(timeout)}'
        command += f' -u {shlex.quote(str(username) + ":" + str(password))}'
        command += ' -H "Accept: application/json"'
        command += ' -H "Content-Type: application/json"'
        command += f' -X {shlex.quote(method)}'
        if payload is not None:
            command += f' --data-raw {shlex.quote(json.dumps(payload))}'
        command += f' {shlex.quote(url)}'
        command += ' -w "\n%{http_code}"'

        output, exit_code = self.helper.runcommand(command, True, timeout + 5)
        stdout = ''
        stderr = ''
        if output:
            if len(output) > 0 and output[0]:
                stdout = output[0].decode(errors='replace')
            if len(output) > 1 and output[1]:
                stderr = output[1].decode(errors='replace')

        if exit_code != 0:
            return False, 0, stderr.strip() or stdout.strip() or f'curl exit code {exit_code}'

        if '\n' in stdout:
            body, http_code = stdout.rsplit('\n', 1)
        else:
            body, http_code = stdout, '0'

        try:
            http_code = int(http_code.strip())
        except Exception:
            http_code = 0

        if http_code < 200 or http_code >= 300:
            return False, http_code, body.strip() or stderr.strip() or f'Redfish HTTP {http_code}'
        return True, http_code, body.strip()

    def _request_json(self, device=None, username=None, password=None,
                      path='/redfish/v1/'):
        status, _, response = self._curl_json(
            device=device,
            username=username,
            password=password,
            method='GET',
            path=path
        )
        if not status:
            return False, response
        if not response:
            return True, {}
        try:
            return True, json.loads(response)
        except Exception as exp:
            return False, f'Invalid JSON from {path}: {exp}'

    def _post_json(self, device=None, username=None, password=None,
                   path=None, payload=None):
        status, _, response = self._curl_json(
            device=device,
            username=username,
            password=password,
            method='POST',
            path=path,
            payload=payload,
            timeout=20
        )
        return status, response

    def _patch_json(self, device=None, username=None, password=None,
                    path=None, payload=None):
        status, _, response = self._curl_json(
            device=device,
            username=username,
            password=password,
            method='PATCH',
            path=path,
            payload=payload,
            timeout=20
        )
        return status, response

    def _first_member_path(self, device=None, username=None, password=None,
                           collection_path=None):
        status, data = self._request_json(
            device=device,
            username=username,
            password=password,
            path=collection_path
        )
        if not status:
            return False, data
        for member in data.get('Members', []):
            member_path = member.get('@odata.id')
            if member_path:
                return True, member_path
        return False, f'No members found in {collection_path}'

    def _service_root(self, device=None, username=None, password=None):
        return self._request_json(
            device=device,
            username=username,
            password=password,
            path='/redfish/v1/'
        )

    def _system_resource(self, device=None, username=None, password=None):
        status, root = self._service_root(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, root, None
        systems_path = root.get('Systems', {}).get('@odata.id')
        if not systems_path:
            return False, 'Systems collection missing from Redfish root', None
        status, system_path = self._first_member_path(
            device=device,
            username=username,
            password=password,
            collection_path=systems_path
        )
        if not status:
            return False, system_path, None
        status, system_data = self._request_json(
            device=device,
            username=username,
            password=password,
            path=system_path
        )
        if not status:
            return False, system_data, None
        return True, system_path, system_data

    def _manager_resource(self, device=None, username=None, password=None):
        status, root = self._service_root(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, root, None
        managers_path = root.get('Managers', {}).get('@odata.id')
        if not managers_path:
            return False, 'Managers collection missing from Redfish root', None
        status, manager_path = self._first_member_path(
            device=device,
            username=username,
            password=password,
            collection_path=managers_path
        )
        if not status:
            return False, manager_path, None
        status, manager_data = self._request_json(
            device=device,
            username=username,
            password=password,
            path=manager_path
        )
        if not status:
            return False, manager_data, None
        return True, manager_path, manager_data

    def _chassis_resource(self, device=None, username=None, password=None):
        status, root = self._service_root(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, root, None
        chassis_path = root.get('Chassis', {}).get('@odata.id')
        if not chassis_path:
            return False, 'Chassis collection missing from Redfish root', None
        status, member_path = self._first_member_path(
            device=device,
            username=username,
            password=password,
            collection_path=chassis_path
        )
        if not status:
            return False, member_path, None
        status, chassis_data = self._request_json(
            device=device,
            username=username,
            password=password,
            path=member_path
        )
        if not status:
            return False, chassis_data, None
        return True, member_path, chassis_data

    def _redfish_reset(self, reset_type=None, device=None, username=None,
                       password=None):
        status, system_path, system_data = self._system_resource(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, system_path
        reset_target = system_data.get('Actions', {}).get('#ComputerSystem.Reset', {}).get('target')
        if not reset_target:
            return False, 'ComputerSystem.Reset action not available'
        return self._post_json(
            device=device,
            username=username,
            password=password,
            path=reset_target,
            payload={'ResetType': reset_type}
        )

    def _redfish_power_status(self, device=None, username=None, password=None):
        status, _, system_data = self._system_resource(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, 'Unable to query system resource'
        power_state = str(system_data.get('PowerState', '')).strip().lower()
        if not power_state:
            return False, 'PowerState missing from system resource'
        return True, power_state

    def _redfish_set_identify(self, enabled=False, device=None,
                              username=None, password=None):
        candidates = []
        status, path, data = self._system_resource(
            device=device,
            username=username,
            password=password
        )
        if status:
            candidates.append((path, data))
        status, path, data = self._chassis_resource(
            device=device,
            username=username,
            password=password
        )
        if status:
            candidates.append((path, data))

        for path, data in candidates:
            if 'LocationIndicatorActive' in data:
                status, response = self._patch_json(
                    device=device,
                    username=username,
                    password=password,
                    path=path,
                    payload={'LocationIndicatorActive': bool(enabled)}
                )
                if status:
                    return True, 'identify' if enabled else 'noidentify'
            if 'IndicatorLED' in data:
                desired_states = ['Lit', 'Blinking'] if enabled else ['Off']
                for state in desired_states:
                    status, response = self._patch_json(
                        device=device,
                        username=username,
                        password=password,
                        path=path,
                        payload={'IndicatorLED': state}
                    )
                    if status:
                        return True, 'identify' if enabled else 'noidentify'
        return False, 'No supported Redfish identify property found'

    def _log_service_paths(self, device=None, username=None, password=None):
        status, _, manager_data = self._manager_resource(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, manager_data
        log_services_path = manager_data.get('LogServices', {}).get('@odata.id')
        if not log_services_path:
            return False, 'LogServices collection missing from manager resource'
        status, log_services = self._request_json(
            device=device,
            username=username,
            password=password,
            path=log_services_path
        )
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
        status, service_paths = self._log_service_paths(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, service_paths

        cleared = []
        errors = []
        for service_path in service_paths:
            service_status, service_data = self._request_json(
                device=device,
                username=username,
                password=password,
                path=service_path
            )
            if not service_status:
                errors.append(service_data)
                continue
            clear_target = service_data.get('Actions', {}).get('#LogService.ClearLog', {}).get('target')
            if not clear_target:
                continue
            clear_status, clear_response = self._post_json(
                device=device,
                username=username,
                password=password,
                path=clear_target,
                payload={}
            )
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
        status, service_paths = self._log_service_paths(
            device=device,
            username=username,
            password=password
        )
        if not status:
            return False, service_paths

        lines = []
        for service_path in service_paths:
            service_status, service_data = self._request_json(
                device=device,
                username=username,
                password=password,
                path=service_path
            )
            if not service_status:
                continue
            entries_path = service_data.get('Entries', {}).get('@odata.id')
            if not entries_path:
                entries_path = service_path.rstrip('/') + '/Entries'
            entries_status, entries_data = self._request_json(
                device=device,
                username=username,
                password=password,
                path=entries_path
            )
            if not entries_status:
                continue
            members = entries_data.get('Members', [])
            if not members:
                lines.append(f'[{service_path}] no log entries')
                continue
            for member in members:
                if isinstance(member, dict) and '@odata.id' in member:
                    entry_status, entry_data = self._request_json(
                        device=device,
                        username=username,
                        password=password,
                        path=member['@odata.id']
                    )
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
