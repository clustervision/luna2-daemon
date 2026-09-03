#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
Plugin Class :: Redfish Power Control

Standards-based power and chassis control for any BMC that speaks Redfish, over
the shared client. The power, chassis and sel methods fall back to the default
ipmitool plugin when Redfish is unavailable or the board does not support the
action, so a node whose BMC does not answer behaves exactly as it did before. The
boot methods do not: the IPMI boot flags are not reliable, so they refuse instead.

A vendor file beside this one subclasses it and overrides only what that vendor
does differently. Everything standards-based belongs here, not there.
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
    """Vendor-neutral Redfish control plugin."""

    # What Luna's actions mean in Redfish, most preferred first. The first entry of
    # each is what the Dell plugin has always sent, so a board offering it behaves
    # exactly as before; the rest are only reached when the board says it does not
    # accept the first.
    RESET_TYPES = {
        'on':     ['On', 'ForceOn'],
        'off':    ['ForceOff', 'GracefulShutdown', 'Off'],
        'reset':  ['ForceRestart', 'GracefulRestart', 'PowerCycle'],
        'cycle':  ['PowerCycle', 'ForceRestart'],
    }

    # What Luna's boot targets mean in Redfish. A new target is a row here plus
    # its check on a real board, not code.
    BOOT_TARGETS = {
        'bios': 'BiosSetup',
    }
    OVERRIDE_FIELDS = ('BootSourceOverrideTarget', 'BootSourceOverrideEnabled',
                       'BootSourceOverrideMode')

    def __init__(self):
        self.default = DefaultPlugin()

    # --- the control contract ------------------------------------------------

    def power_on(self, device=None, username=None, password=None):
        return self.reset_or_fallback('on', 'power_on', 'on', device, username, password)

    def power_off(self, device=None, username=None, password=None):
        return self.reset_or_fallback('off', 'power_off', 'off', device, username, password)

    def power_reset(self, device=None, username=None, password=None):
        return self.reset_or_fallback('reset', 'power_reset', 'reset', device, username, password)

    def power_cycle(self, device=None, username=None, password=None):
        return self.reset_or_fallback('cycle', 'power_cycle', 'cycle', device, username, password)

    def power_status(self, device=None, username=None, password=None):
        status, response = self.redfish_power_status(device, username, password)
        if status:
            return status, response
        return self.default.power_status(device=device, username=username, password=password)

    def identify(self, device=None, username=None, password=None):
        status, response = self.set_identify(True, device, username, password)
        if status:
            return status, response
        return self.default.identify(device=device, username=username, password=password)

    def no_identify(self, device=None, username=None, password=None):
        status, response = self.set_identify(False, device, username, password)
        if status:
            return status, response
        return self.default.no_identify(device=device, username=username, password=password)

    def sel_clear(self, device=None, username=None, password=None):
        status, response = self.redfish_sel_clear(device, username, password)
        if status:
            return status, response
        return self.default.sel_clear(device=device, username=username, password=password)

    def sel_list(self, device=None, username=None, password=None, newlines=True):
        status, response = self.redfish_sel_list(device, username, password, newlines)
        if status:
            return status, response
        return self.default.sel_list(device=device, username=username, password=password,
                                     newlines=newlines)

    def boot_bios(self, device=None, username=None, password=None):
        return self.redfish_next_boot('bios', device, username, password)

    def boot_status(self, device=None, username=None, password=None):
        return self.redfish_boot_status(device, username, password)

    def boot_clear(self, device=None, username=None, password=None):
        return self.redfish_boot_clear(device, username, password)

    # --- the Redfish half ----------------------------------------------------

    def client(self, device=None, username=None, password=None):
        """
        The shared Redfish client for this node's BMC.

        The credentials are the ones core handed in, which are bmcsetup's. A
        redfishsetup is deliberately not used here: every method falls back to
        ipmitool, and a Redfish-only account would authenticate the first attempt
        and then break the fallback it depends on.
        """
        return Redfish(device=device, username=username, password=password, timeout=20)

    def allowable_reset_types(self, system_data=None, redfish=None):
        """
        This method returns the reset types the board says it accepts.

        A board advertises them either on the action itself or in the ActionInfo
        resource the action points at. Asking is what lets Luna map its own verbs
        onto what the hardware actually offers, instead of sending a fixed value
        and learning from the error which is the same thing one round trip later
        and one failed power operation worse.
        """
        action = (system_data or {}).get('Actions', {}).get('#ComputerSystem.Reset', {})
        allowed = action.get('ResetType@Redfish.AllowableValues')
        if isinstance(allowed, list) and allowed:
            return [str(entry) for entry in allowed]
        info_path = action.get('@Redfish.ActionInfo')
        if info_path and redfish:
            status, info = redfish.get(path=info_path, cache=True)
            if status and isinstance(info, dict):
                for parameter in info.get('Parameters', []):
                    if parameter.get('Name') == 'ResetType':
                        values = parameter.get('AllowableValues')
                        if isinstance(values, list) and values:
                            return [str(entry) for entry in values]
        return []

    def reset_type_for(self, action=None, system_data=None, redfish=None):
        """
        This method picks the reset type to send: the most preferred one the board
        accepts, or the most preferred one outright when the board does not say.
        """
        wanted = self.RESET_TYPES.get(action, [])
        allowed = self.allowable_reset_types(system_data=system_data, redfish=redfish)
        if not allowed:
            return wanted[0] if wanted else None
        for candidate in wanted:
            if candidate in allowed:
                return candidate
        return None

    def reset_or_fallback(self, action=None, fallback=None, message=None,
                          device=None, username=None, password=None):
        status, response = self.redfish_reset(action, device, username, password)
        if status:
            return True, message
        return getattr(self.default, fallback)(device=device, username=username,
                                               password=password)

    def redfish_reset(self, action=None, device=None, username=None, password=None,
                      redfish=None):
        redfish = redfish or self.client(device=device, username=username, password=password)
        status, system_path, system_data = redfish.system()
        if not status:
            return False, system_path
        target = system_data.get('Actions', {}).get('#ComputerSystem.Reset', {}).get('target')
        if not target:
            return False, 'ComputerSystem.Reset action not available'
        reset_type = self.reset_type_for(action=action, system_data=system_data, redfish=redfish)
        if not reset_type:
            return False, (f'this system accepts none of the reset types Luna uses for '
                           f'{action}: {self.allowable_reset_types(system_data, redfish)}')
        return redfish.post(path=target, payload={'ResetType': reset_type})

    def redfish_power_status(self, device=None, username=None, password=None):
        redfish = self.client(device=device, username=username, password=password)
        status, _, system_data = redfish.system()
        if not status:
            return False, 'Unable to query system resource'
        power_state = str(system_data.get('PowerState', '')).strip().lower()
        if not power_state:
            return False, 'PowerState missing from system resource'
        return True, power_state

    def redfish_next_boot(self, target=None, device=None, username=None, password=None):
        """
        This method arms a one-shot boot override and resets the node into it.

        There is no ipmitool fallback here, unlike the power actions: the IPMI
        boot flags were found unreliable on real hardware, and a reset without the
        override is an ordinary reboot that reads as success. So every step that
        cannot be confirmed refuses instead, and says why, per node.

        The override is read back before the reset. A board can answer 200 to the
        PATCH and change nothing, and the read-back is the only thing that tells
        that apart from a board that did what it was asked.
        """
        wanted = self.BOOT_TARGETS.get(target)
        if not wanted:
            return False, f'unknown boot target {target}'
        redfish = self.client(device=device, username=username, password=password)
        status, system_path, system_data = redfish.system()
        if not status:
            return False, system_path
        boot = system_data.get('Boot')
        if not isinstance(boot, dict):
            return False, 'this system exposes no boot override'
        allowed = boot.get('BootSourceOverrideTarget@Redfish.AllowableValues')
        if isinstance(allowed, list) and allowed and wanted not in allowed:
            return False, f'boot targets this system accepts: {allowed}'
        payload = {'Boot': {'BootSourceOverrideEnabled': 'Once',
                            'BootSourceOverrideTarget': wanted}}
        status, response = redfish.patch(path=system_path, payload=payload,
                                         etag=system_data.get('@odata.etag'))
        if not status:
            return False, f'override refused: {response}'
        status, current = redfish.get(path=system_path)
        if not status:
            return False, f'override written but unreadable afterwards: {current}'
        boot = current.get('Boot') or {}
        if (boot.get('BootSourceOverrideTarget') != wanted
                or boot.get('BootSourceOverrideEnabled') not in ('Once', 'Continuous')):
            return False, ('override not applied by the board: target '
                           f"{boot.get('BootSourceOverrideTarget')}, enabled "
                           f"{boot.get('BootSourceOverrideEnabled')}")
        # a node that is off cannot be reset; powering it on boots it into the
        # override just the same
        power_state = str(current.get('PowerState', '')).strip().lower()
        action = 'on' if power_state == 'off' else 'reset'
        # the same client: the board has already been walked once, and every
        # round trip on a slow BMC is paid by the operator waiting on the CLI
        status, response = self.redfish_reset(action, device, username, password,
                                              redfish=redfish)
        if not status:
            return False, f'override armed but the {action} was refused: {response}'
        return True, f'{target} on next boot, {action} sent'

    def redfish_boot_clear(self, device=None, username=None, password=None):
        """
        This method disarms the boot override, and sends no reset.

        A one-shot override is meant to be consumed by the boot it applies to,
        but a board does not always count a boot that ends in the setup screen:
        an AMI MegaRAC keeps BiosSetup/Once armed while the node sits in setup,
        so every reset lands there again. This is the way out without a console.
        """
        redfish = self.client(device=device, username=username, password=password)
        status, system_path, system_data = redfish.system()
        if not status:
            return False, system_path
        boot = system_data.get('Boot')
        if not isinstance(boot, dict):
            return False, 'this system exposes no boot override'
        payload = {'Boot': {'BootSourceOverrideEnabled': 'Disabled',
                            'BootSourceOverrideTarget': 'None'}}
        status, response = redfish.patch(path=system_path, payload=payload,
                                         etag=system_data.get('@odata.etag'))
        if not status:
            return False, f'clear refused: {response}'
        status, current = redfish.get(path=system_path)
        if not status:
            return False, f'cleared but unreadable afterwards: {current}'
        boot = current.get('Boot') or {}
        if boot.get('BootSourceOverrideEnabled') != 'Disabled':
            return False, ('clear not applied by the board: target '
                           f"{boot.get('BootSourceOverrideTarget')}, enabled "
                           f"{boot.get('BootSourceOverrideEnabled')}")
        return True, 'override cleared, next boot follows the normal order'

    def redfish_boot_status(self, device=None, username=None, password=None):
        redfish = self.client(device=device, username=username, password=password)
        status, _, system_data = redfish.system()
        if not status:
            return False, system_data
        boot = system_data.get('Boot')
        if not isinstance(boot, dict):
            return False, 'this system exposes no boot override'
        parts = [f"{field.replace('BootSourceOverride', '').lower()}={boot.get(field, '-')}"
                 for field in self.OVERRIDE_FIELDS]
        return True, ', '.join(parts)

    def set_identify(self, enabled=False, device=None, username=None, password=None):
        redfish = self.client(device=device, username=username, password=password)
        candidates = []
        status, path, data = redfish.system()
        if status:
            candidates.append((path, data))
        status, path, data = redfish.chassis()
        if status:
            candidates.append((path, data))
        for path, data in candidates:
            if 'LocationIndicatorActive' in data:
                status, _ = redfish.patch(path=path,
                                          payload={'LocationIndicatorActive': bool(enabled)})
                if status:
                    return True, 'identify' if enabled else 'noidentify'
            if 'IndicatorLED' in data:
                for state in (['Lit', 'Blinking'] if enabled else ['Off']):
                    status, _ = redfish.patch(path=path, payload={'IndicatorLED': state})
                    if status:
                        return True, 'identify' if enabled else 'noidentify'
        return False, 'No supported Redfish identify property found'

    def log_service_paths(self, redfish=None):
        status, _, manager_data = redfish.manager()
        if not status:
            return False, manager_data
        services_path = manager_data.get('LogServices', {}).get('@odata.id')
        if not services_path:
            return False, 'LogServices collection missing from manager resource'
        status, services = redfish.get(path=services_path)
        if not status:
            return False, services
        paths = [member['@odata.id'] for member in services.get('Members', [])
                 if member.get('@odata.id')]
        if not paths:
            return False, 'No Redfish log services found'
        return True, paths

    def redfish_sel_clear(self, device=None, username=None, password=None):
        redfish = self.client(device=device, username=username, password=password)
        status, service_paths = self.log_service_paths(redfish=redfish)
        if not status:
            return False, service_paths
        cleared, errors = [], []
        for service_path in service_paths:
            status, service_data = redfish.get(path=service_path)
            if not status:
                errors.append(service_data)
                continue
            target = service_data.get('Actions', {}).get('#LogService.ClearLog', {}).get('target')
            if not target:
                continue
            status, response = redfish.post(path=target, payload={})
            if status:
                cleared.append(service_path)
            else:
                errors.append(response)
        if cleared:
            return True, f'cleared {len(cleared)} Redfish log service(s)'
        if errors:
            return False, '; '.join(errors)
        return False, 'No Redfish log service exposes ClearLog'

    def format_log_entry(self, service_path=None, entry_data=None):
        parts = [f'[{service_path}]', f"id={entry_data.get('Id', '?')}"]
        for label, key in (('created', 'Created'), ('severity', 'Severity'), ('name', 'Name')):
            if entry_data.get(key):
                parts.append(f'{label}={entry_data[key]}')
        message = entry_data.get('Message') or entry_data.get('MessageId')
        if message:
            parts.append(f'message={message}')
        return ' '.join(parts)

    def redfish_sel_list(self, device=None, username=None, password=None, newlines=True):
        redfish = self.client(device=device, username=username, password=password)
        status, service_paths = self.log_service_paths(redfish=redfish)
        if not status:
            return False, service_paths
        lines = []
        for service_path in service_paths:
            status, service_data = redfish.get(path=service_path)
            if not status:
                continue
            entries_path = service_data.get('Entries', {}).get('@odata.id')
            if not entries_path:
                entries_path = service_path.rstrip('/') + '/Entries'
            status, entries_data = redfish.get(path=entries_path)
            if not status:
                continue
            members = entries_data.get('Members', [])
            if not members:
                lines.append(f'[{service_path}] no log entries')
                continue
            for member in members:
                if isinstance(member, dict) and '@odata.id' in member:
                    status, entry_data = redfish.get(path=member['@odata.id'])
                    if not status:
                        continue
                else:
                    entry_data = member
                lines.append(self.format_log_entry(service_path=service_path,
                                                   entry_data=entry_data))
        if not lines:
            return False, 'No Redfish log entries found'
        response = '\n'.join(lines)
        if not newlines:
            response = response.replace('\n', '')
        return True, response
