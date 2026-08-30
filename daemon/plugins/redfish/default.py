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
Plugin Class :: Default Redfish interaction

Standards-based behaviour only. Core hands this plugin a Redfish client bound to
one BMC, and the plugin probes the service and reports back what it found. A
vendor file beside this one carries only what the standard cannot answer.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class Plugin():
    """
    This is the default class for Redfish interaction.
    """

    def __init__(self):
        """
        setting and upload are required methods.
        """

    def setting(self, redfish=None, uri=None, payload=None):
        """
        This method will modify properties of an existing Redfish resource.

        The resource is read before it is written, for two reasons. A URI the
        service does not serve is worth saying so about, rather than reporting
        whatever a PATCH against it happens to return. And a resource that takes
        staged changes advertises where they have to be written - see
        settings_target below.
        """
        if not uri:
            return False, 'No Redfish uri given'
        if payload is None:
            return False, 'No content given to apply'
        status, current = redfish.get(path=uri)
        if not status:
            return False, f'{uri}: {current}'
        target, applytimes = self.settings_target(resource=current)
        if target:
            status, response = redfish.patch(path=target, payload=payload)
            if not status:
                return False, f'{target}: {response}'
            message = f'staged on {target}'
            if applytimes:
                message += f", applies {'/'.join(applytimes)}"
            return True, message
        status, response = redfish.patch(path=uri, payload=payload)
        if not status:
            return False, f'{uri}: {response}'
        return True, f'applied on {uri}'


    def upload(self, redfish=None, uri=None, payload=None):
        """
        This method will submit a resource to the Redfish service, or invoke an
        action on it.

        A service that accepts the work but has not finished it answers with a
        task rather than a result. Saying "submitted, task <x>" is the truthful
        answer there - the control pipeline holds a worker for the length of this
        call, so waiting minutes for a firmware apply belongs in the queue.
        """
        if not uri:
            return False, 'No Redfish uri given'
        if payload is None:
            return False, 'No content given to upload'
        status, response = redfish.post(path=uri, payload=payload)
        if not status:
            return False, f'{uri}: {response}'
        location = self.task_location(response=response)
        if location:
            return True, f'submitted on {uri}, task {location}'
        return True, f'uploaded on {uri}'


    def multipart(self, component=None, filename=None):
        """
        This method returns the extra parts a multipart firmware push must carry
        for this board, and the name the image is presented under, as
        ({part name: JSON body}, filename).

        The standard names two parts, UpdateParameters and UpdateFile, and that is
        all the default sends. A vendor file overrides this where the board demands
        more: a board that refuses the standard form says so only in its rejection,
        which discovery cannot read before sending the image.
        """
        return {}, filename


    def probe(self, redfish=None, uri=None):
        """
        This method will read a Redfish resource and hand it back, so core can
        report what a BMC actually holds rather than what we assume it holds.
        """
        if not uri:
            uri = '/redfish/v1/'
        status, response = redfish.get(path=uri)
        if not status:
            return False, f'{uri}: {response}'
        return True, response


    def settings_target(self, resource=None):
        """
        This method will return where a staged change has to be written, and when
        the service says it would take effect.

        Redfish resources that cannot be modified in place - BIOS being the one
        everybody meets - carry an @Redfish.Settings annotation naming a separate
        settings object. Writing to the resource itself is then accepted and
        silently ignored, or refused, depending on the vendor. The annotation is
        the service telling us where the write belongs, so we follow it instead of
        hardcoding a per-vendor path.
        """
        if not isinstance(resource, dict):
            return None, None
        settings = resource.get('@Redfish.Settings')
        if not isinstance(settings, dict):
            return None, None
        target = settings.get('SettingsObject', {}).get('@odata.id')
        if not target:
            return None, None
        applytimes = settings.get('SupportedApplyTimes')
        if not isinstance(applytimes, list):
            applytimes = None
        return target, applytimes


    def task_location(self, response=None):
        """
        This method will return the task a Redfish service handed back for work it
        has accepted but not yet finished.
        """
        if not isinstance(response, dict):
            return None
        if str(response.get('@odata.type', '')).startswith('#Task.'):
            return response.get('@odata.id') or response.get('Id')
        if 'TaskState' in response:
            return response.get('@odata.id') or response.get('Id')
        return None
