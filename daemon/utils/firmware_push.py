
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


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is the board-facing half of a firmware update.

What the catalogue decided, this carries out - and the ordering of the two is the
point. The catalogue answers from stored inventory and is therefore cheap and
truthful for a machine that is switched off; nothing here is either, so nothing
here runs for a node the catalogue already declined.

Four things about a real board shape this, and none of them are obvious from the
specification.

An update service is not ready just because the BMC answered. AMI boards return
503 for between thirty seconds and two minutes after a reset and silently swallow
anything pushed into that window - the push is accepted, the flash never happens,
and every signal short of reading the version back says it worked. So readiness is
asked before anything is submitted, and a service that is not ready is a reason to
come back rather than a failure.

There is more than one way to hand a board an image, and boards differ on which
they implement. SimpleUpdate has the board fetch the image itself, which inverts
the load: one controller serving four thousand pulls rather than streaming sixty
megabytes four thousand times. Where a board will not pull, the multipart or plain
HTTP push URI it advertises is used instead. Which of the three is available is
discovered from the service, never assumed from the vendor.

A task is not an outcome. The monitor a service hands back is transient and many
implementations delete it the moment the work finishes, so a monitor that has gone
is the ordinary end of a successful flash and not a failure - the persistent task
carries the real answer. This tracker therefore reports what it saw and refuses to
conclude success on its own.

A board declares the shape of its own payload, and the shape differs. The transfer
protocol a board accepts, and even the name of the parameter that says which
component to flash, are published in the action's ActionInfo document rather than
inline - so a payload written from the specification is refused by a board that is
following the specification. Measured here: one board names it 'Targets' and takes
resource URIs, another names it 'UpdateComponent' and takes one string from its own
list, and neither publishes its transfer protocols inline at all.

And the version read back is the only evidence. An image can land in the inactive
slot with the task reporting Completed, so success is a comparison against what the
board says it is running afterwards, never the task state. That is why verify() is
separate from track(), and why nothing in this module returns 'done'.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import concurrent.futures
from time import sleep
from urllib.parse import urlparse

from common.constant import CONSTANT
from utils.database import Database
from utils.helper import Helper
from utils.log import Log
from utils.queue import Queue
from utils.ha import HA
from utils.firmware import FirmwareCatalog, FirmwareRequest


# How a board will take an image, in the order we would rather use them.
# SimpleUpdate first because the board fetches for itself, which is the difference
# between one transfer and four thousand.
SIMPLE = 'simple'
MULTIPART = 'multipart'
HTTP = 'http'

# Task states that end the work, from the DMTF's TaskState enumeration. 'Completed'
# is in neither list on purpose: it ends the waiting and decides nothing.
FAILED_STATES = ['Exception', 'Killed', 'Cancelled', 'Interrupted']
RUNNING_STATES = ['New', 'Starting', 'Running', 'Pending', 'Suspended', 'Stopping']

# How many boards are flashed at once, and the pause between batches. This protects
# the far end rather than the controller: a BMC is a small computer and a flash is
# the heaviest thing it ever does.
DEFAULT_BATCH = 10
DEFAULT_DELAY = 0


class FirmwarePush():
    """
    This class carries an image to a board and says what the board did with it.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def ready(self, redfish=None):
        """
        This method asks whether the update service will accept work, and returns
        (status, reason).

        Not ready is not broken. A BMC that has just been reset answers 503 here
        for up to two minutes and discards anything pushed into that window without
        saying so, so the only safe reading of 503 is 'come back', and the only
        unsafe one is to push anyway.
        """
        status, path, service = redfish.update_service()
        if not status:
            return False, path
        state = (((service or {}).get('Status') or {}).get('State') or '').strip()
        if state and state.lower() != 'enabled':
            return False, f'the update service is {state}, not Enabled'
        return True, None


    def push_target(self, service=None):
        """
        This method returns (kind, uri) for the way this board takes an image, or
        (None, reason) where it advertises no way at all.

        Discovered rather than assumed: the same vendor ships boards that differ on
        this between generations, so a per-vendor table would be wrong the moment a
        customer buys the next one.
        """
        service = service or {}
        actions = (service.get('Actions') or {}).get('#UpdateService.SimpleUpdate')
        if isinstance(actions, dict) and actions.get('target'):
            return SIMPLE, actions['target']
        if service.get('MultipartHttpPushUri'):
            return MULTIPART, service['MultipartHttpPushUri']
        if service.get('HttpPushUri'):
            return HTTP, service['HttpPushUri']
        return None, 'the update service offers no way to send it an image'


    def payload(self, redfish=None, action=None, image_url=None, component=None,
                targets=None):
        """
        This method builds the SimpleUpdate body this particular board will accept,
        and returns (status, body or reason).

        Built from what the board declares rather than from the specification,
        because the concept an action takes is universal and the name it wears is
        not. One board names the component to flash 'Targets' and takes a list of
        resource URIs; another names it 'UpdateComponent' and takes one string out
        of its own list - both properly declared, both standards-compliant, and a
        payload written for one is ignored or refused by the other. Measured on
        real hardware, not read.
        """
        scheme = str(urlparse(str(image_url or '')).scheme or '').upper()
        if not scheme:
            return False, 'the image URL names no transfer protocol'
        allowed = redfish.allowable(action=action, parameter='TransferProtocol')
        if allowed and scheme not in allowed:
            return False, (f'the board does not accept {scheme}; it allows '
                           f'{sorted(allowed)}')
        body = {'ImageURI': image_url, 'TransferProtocol': scheme}

        names = redfish.parameter_names(action=action)
        if 'UpdateComponent' in names:
            if not component:
                return False, ('the board asks which component to update and none '
                               'was named')
            choices = redfish.allowable(action=action, parameter='UpdateComponent')
            if choices and component not in choices:
                return False, (f'the board has no component {component}; it offers '
                               f'{sorted(choices)}')
            body['UpdateComponent'] = component
        elif targets:
            body['Targets'] = list(targets)
        return True, body


    def submit(self, redfish=None, kind=None, uri=None, action=None, image_url=None,
               component=None, targets=None):
        """
        This method hands the board the image and returns (status, task or reason).

        The image is named by URL rather than streamed from here, because the
        caller staged it on the controller's own webserver: this module is not the
        right place to decide which of a controller's addresses a BMC can reach.
        """
        if kind != SIMPLE:
            return False, (f'{kind} transfer is not implemented yet; the board '
                           'offers no SimpleUpdate')
        status, body = self.payload(redfish=redfish, action=action,
                                    image_url=image_url, component=component,
                                    targets=targets)
        if not status:
            return False, body
        status, answer = redfish.post(path=uri, payload=body)
        if not status:
            return False, answer
        return True, self.task_path(answer)


    def task_path(self, answer=None):
        """
        This method returns the task a service handed back, or None where it
        answered with a result instead.
        """
        if not isinstance(answer, dict):
            return None
        if str(answer.get('@odata.type', '')).startswith('#Task.') or 'TaskState' in answer:
            return answer.get('@odata.id') or answer.get('Id')
        return None


    def track(self, redfish=None, task=None, deadline=None, waited=0):
        """
        This method reads a firmware task once and says what to do next, returning
        (state, reason).

        State is 'waiting', 'gone', 'failed' or 'finished'. Note what is NOT here:
        'succeeded'. A task reporting Completed means the service finished handling
        the image, not that the board is running it - the image can land in the
        inactive slot and every signal short of the version says it worked. Only
        verify() decides that.

        'gone' is the case the specification does not prepare anybody for: the
        monitor is transient and implementations delete it on completion, so a task
        that has vanished is the ordinary end of a flash. Reporting it as a failure
        would fail successful updates, which is why it is its own answer and why the
        caller resolves it by looking at the board rather than at the task.
        """
        if not task:
            return 'gone', 'the service returned no task to follow'
        status, data = redfish.get(path=task)
        if not status:
            return 'gone', f'the task is no longer there: {data}'
        if not isinstance(data, dict):
            return 'gone', 'the task answered with something that is not a task'
        state = str(data.get('TaskState') or 'Unknown')
        if state in FAILED_STATES:
            return 'failed', redfish.reason(data, 0)
        if state in RUNNING_STATES:
            if deadline is not None and waited >= deadline:
                return 'failed', f'the task was still {state} after {waited} seconds'
            return 'waiting', state
        return 'finished', state


    def running_version(self, redfish=None, component=None):
        """
        This method returns the version the board says it is running for one
        component, read from its own FirmwareInventory.
        """
        status, _, service = redfish.update_service()
        if not status:
            return False, service
        path = ((service or {}).get('FirmwareInventory') or {}).get('@odata.id')
        if not path:
            return False, 'the update service publishes no firmware inventory'
        status, collection = redfish.get(path=path)
        if not status:
            return False, collection
        for member in (collection or {}).get('Members', []):
            status, data = redfish.get(path=member.get('@odata.id'))
            if not status or not isinstance(data, dict):
                continue
            names = [str(data.get('Id') or ''), str(data.get('Name') or '')]
            if component in names:
                return True, str(data.get('Version') or '')
        return False, f'the board reports no component called {component}'


    def verify(self, redfish=None, component=None, wanted=None):
        """
        This method decides whether the flash actually landed, and it is the only
        thing here that decides anything.

        A task said the service finished. This asks the board what it is running,
        which is the one question whose answer cannot be produced by an image that
        went into the slot the machine is not booting from.
        """
        status, version = self.running_version(redfish=redfish, component=component)
        if not status:
            return False, version
        if str(version).strip() == str(wanted).strip():
            return True, version
        return False, (f'{component} still reports {version or "nothing"} rather '
                       f'than {wanted}; the image may have landed in the inactive slot')


    def batch_settings(self):
        """
        This method returns how many boards to flash at once and the pause between
        batches, from luna.ini with the defaults in code.

        [FIRMWARE] is read only if an administrator put it there. Declaring it
        required would abort startup on every existing configuration that does not
        have it, and abort before the logger exists to say why.
        """
        batch, delay = DEFAULT_BATCH, DEFAULT_DELAY
        for option, default in (('FIRMWARE_BATCH_SIZE', batch),
                                ('FIRMWARE_BATCH_DELAY', delay)):
            value = default
            try:
                value = int(str(CONSTANT['FIRMWARE'][option]).replace('s', ''))
            except (KeyError, TypeError, ValueError):
                value = default
            if option.endswith('SIZE'):
                batch = max(1, value)
            else:
                delay = max(0, value)
        return batch, delay


    def sweep_child(self, pipeline, t=0):
        """
        One request per call; the mother decides how many of these run at once.
        """
        run = 1
        while run:
            run = 0
            item = pipeline.get_node()
            if not item:
                # more workers than requests left. Not an error, and it must not
                # raise: a child that dies inside an executor takes its exception
                # with it and the mother learns nothing
                continue
            key, request = item
            try:
                status, message = self.update_node(request)
            except Exception as exp:
                status, message = False, f'{exp}'
                self.logger.error(f'firmware update for request {key}: {exp}')
            pipeline.add_message({key: f'{status}={message}'})


    def sweep_mother(self, event):
        """
        This method drains firmware requests, master only.

        One sweep, not one queued task per node. The requests live in their own
        replicated table, so the sweep finds all of them in a single query and hands
        them to a pool - which means a boot storm's worth of work costs one query
        rather than a queue row, a claim and a removal per node.

        Master only, because two controllers flashing the same board would be racing
        over the one thing on a machine that must not be raced over. The passive one
        does not drop these: a queue entry left on a passive controller is a leak, but
        a request row is the record of what an operator asked for, and dropping it is
        how an instruction disappears at a failover. It simply does not act on them.
        """
        self.logger.info('Starting firmware sweep thread')
        ha_object = HA()
        requests = FirmwareRequest()
        while True:
            try:
                if (not ha_object.get_hastate()) or ha_object.get_role():
                    requests.reclaim_abandoned()
                    pipeline = Helper().Pipeline()
                    for row in requests.pending():
                        requests.claim(row['id'])
                        pipeline.add_nodes({row['id']: row})
                    if pipeline.has_nodes():
                        self.sweep_batches(pipeline, requests)
            except Exception as exp:
                self.logger.error(f'firmware sweep thread encountered problem: {exp}')
            if event.is_set():
                return
            sleep(5)


    def sweep_batches(self, pipeline, requests=None):
        """
        This method runs the claimed requests in batches and records what happened.
        """
        batch, delay = self.batch_settings()
        while pipeline.has_nodes():
            with concurrent.futures.ThreadPoolExecutor(max_workers=batch) as executor:
                _ = [executor.submit(self.sweep_child, pipeline, t)
                     for t in range(1, batch + 1)]
            sleep(0.1)
            results = pipeline.get_messages()
            for key in list(results):
                status, message, *_ = (results[key].split('=', 1) + [None])
                requests.finish(key, status == 'True', message)
                pipeline.del_message(key)
            if delay:
                sleep(delay)


    def update_node(self, request=None):
        """
        This method carries out one request, and answers whether the board is now
        running what the catalogue asked for.

        Every refusal below happens before anything is written to a board. What the
        node should run comes from the catalogue and its own stored inventory, so a
        request for a node the catalogue does not cover, or one nobody has collected
        inventory from, is declined here rather than after a connection.
        """
        nodename = request.get('nodename')
        status, plan = FirmwareCatalog().plan(nodename=nodename)
        if not status:
            return False, f'{nodename}: {plan}'
        wanted = [item for item in plan['differs']
                  if not request.get('component') or item['component'] == request['component']]
        if not wanted:
            return True, f'{nodename}: already running what the catalogue asks'
        return False, (f'{nodename}: {len(wanted)} component(s) to update - '
                       'the transfer itself is not implemented yet')
