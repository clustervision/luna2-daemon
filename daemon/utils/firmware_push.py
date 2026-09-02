
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
import os
import uuid
from json import dumps
from time import sleep
from urllib.parse import urlparse

from common.constant import CONSTANT
from utils.database import Database
from utils.helper import Helper
from utils.log import Log
from utils.queue import Queue
from utils.ha import HA
from utils.firmware import FirmwareCatalog, FirmwareRequest, NO_IMAGEFILE, NO_IMAGE
from utils.status import Status


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


# Name fragments marking a component whose flash reinitialises the BMC to factory
# defaults - default credentials and DHCP. On the AMI boards this was proven against,
# a BMC flash does exactly that, and the standard Redfish SimpleUpdate carries no way
# to preserve it. Luna does not fight that: it holds the intended config (the node's
# bmcsetup and its assigned address) and restores it in-band through setupbmc on the
# node's next boot through Luna. That restore is an operator action - Luna reports it
# and does NOT reboot the node, because a firmware push is not licence to drain one. A
# BMC flash does not reboot the host either, so the note always applies to it; a
# component whose flash did reboot the node through Luna would have setupbmc run on
# its own, but none here do.
#
# Matched as a fragment of the name rather than as the whole of it, because a board
# names the same flash in more than one way and we only ever see the list it happens
# to publish. One AMI board offers both 'BMC' and 'HPM_BMC' in its own UpdateComponent
# list, and holds its firmware as 'BMCImage1'/'BMCImage2'; each of those resets the
# same configuration. An exact list learns about a spelling only after somebody is
# locked out by it. The cost either way is unequal and decides this: a fragment that
# matches too widely adds a sentence to a success message, one that matches too
# narrowly leaves an operator with an unreachable BMC and nothing saying why.
RESETS_BMC_CONFIG = ['BMC']

# How many boards are flashed at once, and the pause between batches. This protects
# the far end rather than the controller: a BMC is a small computer and a flash is
# the heaviest thing it ever does.
DEFAULT_BATCH = 10
DEFAULT_DELAY = 0

# How long one component's flash is given, and how often the task is read. A flash
# is ten to thirty minutes and drops the connection by design, so the worker holds
# for it the way the BIOS push holds through a reboot.
FLASH_DEADLINE = 2400
POLL_INTERVAL = 15
# How long to wait for an update service to come back before giving up on it. A BMC
# that has just flashed itself is unreachable for a while, and that is not a failure.
READY_DEADLINE = 300
# how long to wait for a board to answer once an image has been pushed into it. A
# push is the controller sending megabytes to a BMC that writes them as they come;
# the ordinary read timeout is sized for an answer, not for that
UPLOAD_TIMEOUT = 900
# how long to keep asking a board what it runs after a flash, before deciding. A BMC
# that has just flashed itself reboots, and while it does its inventory is absent or
# incomplete - measured: the task reported Completed, and the component was 'not
# there' for the minutes the service took to come back
VERIFY_DEADLINE = 900
# how long the restore waits for a BMC that setupbmc has just re-addressed to answer
# Redfish with the stored credentials. The node holds its install for about this
# long, so the two are sized together: see hold_for_daemon in the install template
RESTORE_READY_DEADLINE = 240
# how long an install holds after setupbmc when a restore or a BIOS push is scheduled
# for the node, so that the reset it needs lands in the hold and not mid-install.
# It has to cover the time to the FIRST reset only - the status reaching the master
# (tens of seconds, journaled), the queue pickup, the BMC readiness wait above and
# the write - not the whole restore, since the reset ends the sleep. Measured on a
# real install: about a minute typical, under five worst case. Fixed and bounded:
# the node is told at render time and asks nothing afterwards. Bulk is not this
# number's business: the BIOS loop is serial, so after a fleet flash the later
# nodes sleep out and are reset mid-install when their turn comes, which a
# netboot install simply re-runs
HOLD_SECONDS = 450


class MultipartBody():
    """
    A multipart/form-data body that streams a file rather than holding it.

    Built by hand for one reason: the library would read the whole image into memory
    to build the form, and a batch of pushes is that many images at once - a
    four-hundred-megabyte board times ten is memory a controller does not have to
    spare. This reads the preamble, then the file, then the closing boundary, and
    knows its length up front so the transfer carries a Content-Length rather than
    chunked encoding, which not every BMC accepts.
    """

    def __init__(self, parameters=None, filename=None, path=None, extra=None):
        self.boundary = uuid.uuid4().hex
        parts = {'UpdateParameters': parameters or {}}
        parts.update(extra or {})
        head = ''
        for name, body in parts.items():
            head += (f'--{self.boundary}\r\n'
                     f'Content-Disposition: form-data; name="{name}"\r\n'
                     'Content-Type: application/json\r\n\r\n'
                     f'{dumps(body)}\r\n')
        head += (f'--{self.boundary}\r\n'
                 f'Content-Disposition: form-data; name="UpdateFile"; filename="{filename}"\r\n'
                 'Content-Type: application/octet-stream\r\n\r\n')
        self.head = head.encode()
        self.tail = f'\r\n--{self.boundary}--\r\n'.encode()
        self.path = path
        self.size = os.path.getsize(path)
        self.parts = None
        self.handle = None

    @property
    def content_type(self):
        return f'multipart/form-data; boundary={self.boundary}'

    def __len__(self):
        return len(self.head) + self.size + len(self.tail)

    def read(self, size=-1):
        """
        Hands out the body in order; the file is opened on first read and closed
        when it is exhausted, so a body that is never sent never opens it.
        """
        if self.parts is None:
            self.handle = open(self.path, 'rb')
            self.parts = [self.head, self.handle, self.tail]
        while self.parts:
            current = self.parts[0]
            if isinstance(current, bytes):
                chunk, rest = (current, b'') if size < 0 else (current[:size], current[size:])
                if rest:
                    self.parts[0] = rest
                else:
                    self.parts.pop(0)
                if chunk:
                    return chunk
                continue
            chunk = current.read(size)
            if chunk:
                return chunk
            current.close()
            self.parts.pop(0)
        return b''

    def close(self):
        if self.handle:
            self.handle.close()


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
               component=None, targets=None, image_path=None, service=None, plugin=None):
        """
        This method hands the board the image and returns (status, task or reason).

        SimpleUpdate names the image by URL and the board fetches it - one transfer
        per board, in parallel, which is why it is preferred. The push transfers
        send the staged file from here, for a board that will not or cannot fetch:
        the controller is then the sender, and a batch of pushes is that many images
        leaving this machine at once, so they are the tool for the boards that need
        them and not the default.
        """
        if kind == MULTIPART:
            return self.push_multipart(redfish=redfish, uri=uri, image_path=image_path,
                                       service=service, component=component, plugin=plugin)
        if kind == HTTP:
            return self.push_http(redfish=redfish, uri=uri, image_path=image_path,
                                  service=service, component=component)
        if kind != SIMPLE:
            return False, f'{kind} is not a transfer this daemon knows'
        status, body = self.payload(redfish=redfish, action=action,
                                    image_url=image_url, component=component,
                                    targets=targets)
        if not status:
            return False, body
        status, answer, location = redfish.action(path=uri, payload=body)
        if not status:
            return False, answer
        # A board answers with the task in the body, or in the Location header, or
        # in neither. Both are read, and the body wins where both are there because
        # it names the persistent task while the header often names a monitor that
        # is deleted the moment the work finishes. Measured on a board that returns
        # a bare 202: the header was the only handle on the work, and without it a
        # perfectly ordinary flash looks like one that never started.
        return True, self.task_path(answer) or location


    def taken(self, redfish=None, status=None, answer=None, headers=None):
        """
        This method turns a board's answer to a push into (status, task or reason),
        the same way submit() reads a SimpleUpdate's: task in the body, else in the
        Location header, else nothing to follow.
        """
        if not status:
            return False, answer
        location = (headers or {}).get('Location')
        return True, self.task_path(answer) or location


    def image_size_fits(self, image_path=None, service=None):
        """
        This method refuses an image the board has said it cannot take, before a
        byte of it is sent.
        """
        limit = (service or {}).get('MaxImageSizeBytes')
        size = os.path.getsize(image_path)
        if limit and int(limit) and size > int(limit):
            return False, (f'{os.path.basename(image_path)} is {size} bytes and the board '
                           f'takes at most {limit}')
        return True, size


    def inventory_target(self, service=None, component=None):
        """
        This method names the firmware inventory member a push is for, from the
        board's own inventory path - or nothing, where no component was named and
        the board is left to tell from the image.
        """
        inventory = ((service or {}).get('FirmwareInventory') or {}).get('@odata.id')
        if not component or not inventory:
            return None
        return f'{inventory.rstrip("/")}/{component}'


    def push_multipart(self, redfish=None, uri=None, image_path=None, service=None,
                       component=None, plugin=None):
        """
        This method sends the image to the board's MultipartHttpPushUri as the two
        parts the standard names - UpdateParameters and UpdateFile - streamed, plus
        whatever the board's vendor plugin says this board demands on top.

        Targets is left empty where no component was named: the board then tells
        from the image. No apply-time is sent - it is optional in the standard and
        refused by a board that was measured, and the push is immediate anyway.
        """
        status, size = self.image_size_fits(image_path=image_path, service=service)
        if not status:
            return False, size
        target = self.inventory_target(service=service, component=component)
        parameters = {'Targets': [target] if target else []}
        extra, filename = {}, os.path.basename(image_path)
        if plugin is not None and hasattr(plugin, 'multipart'):
            extra, filename = plugin.multipart(component=component, filename=filename)
        body = MultipartBody(parameters=parameters, filename=filename, path=image_path,
                             extra=extra)
        try:
            status, _, answer, headers = redfish.upload(path=uri, body=body,
                                                       content_type=body.content_type,
                                                       timeout=UPLOAD_TIMEOUT)
        finally:
            body.close()
        return self.taken(redfish=redfish, status=status, answer=answer, headers=headers)


    def push_http(self, redfish=None, uri=None, image_path=None, service=None,
                  component=None):
        """
        This method sends the raw image to the board's HttpPushUri. Where the board
        exposes HttpPushUriTargets, the component is named there first, as the
        standard has it; a board without it is left to tell from the image.
        """
        status, size = self.image_size_fits(image_path=image_path, service=service)
        if not status:
            return False, size
        target = self.inventory_target(service=service, component=component)
        if target and 'HttpPushUriTargets' in (service or {}):
            status, reason = redfish.patch(path=service.get('@odata.id') or '/redfish/v1/UpdateService',
                                           payload={'HttpPushUriTargets': [target]})
            if not status:
                return False, f'the board refused the push target {target}: {reason}'
        with open(image_path, 'rb') as handle:
            status, _, answer, headers = redfish.upload(path=uri, body=handle,
                                                       content_type='application/octet-stream',
                                                       timeout=UPLOAD_TIMEOUT)
        return self.taken(redfish=redfish, status=status, answer=answer, headers=headers)


    def vendor_plugin(self, nodename=None):
        """
        This method returns the Redfish plugin for a node - node, group, then the
        vendor its inventory names, then default - the same search path control
        uses, so a vendor's quirk is written once and found by everything.
        """
        from utils.redfish import RedfishAccess
        node = Database().get_record_join(['group.name as groupname'], ['group.id=node.groupid'],
                                          [f'node.name="{nodename}"'])
        groupname = node[0]['groupname'] if node else None
        candidates, model = RedfishAccess().plugin_candidates(nodename=nodename,
                                                              groupname=groupname)
        plugins = Helper().plugin_finder(f"{CONSTANT['PLUGINS']['PLUGINS_DIRECTORY']}/redfish")
        loaded = Helper().plugin_load(plugins, 'redfish', candidates, model)
        # the loader hands back the class; every caller in the daemon instantiates it
        return loaded() if loaded else None


    def image_path(self, imagefile=None):
        """
        This method returns where the staged image is on this controller, for a
        transfer that sends it from here, or why there is none.
        """
        if not imagefile:
            return False, NO_IMAGEFILE
        if imagefile not in FirmwareCatalog().staged_images():
            return False, NO_IMAGE.format(imagefile=imagefile)
        return True, os.path.join(CONSTANT['FILES']['IMAGE_FILES'], imagefile)


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


    def verify(self, redfish=None, component=None, wanted=None, deadline=VERIFY_DEADLINE):
        """
        This method decides whether the flash actually landed, and it is the only
        thing here that decides anything.

        A task said the service finished. This asks the board what it is running,
        which is the one question whose answer cannot be produced by an image that
        went into the slot the machine is not booting from.

        It keeps asking while the board cannot answer: a BMC that has just flashed
        itself is rebooting, and a read that lands in that window sees no service or
        an inventory without the component - neither of which says anything about
        the flash. Only an answer decides; the deadline only says how long to wait
        for one.
        """
        waited = 0
        while True:
            status, version = self.running_version(redfish=redfish, component=component)
            if status or waited >= deadline:
                break
            sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
        if not status:
            # not a verdict: the board never answered, so nothing here says whether
            # the flash landed. The caller decides what silence means
            return None, f'{version} (asked for {waited}s after the flash)'
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
                    if not self.peer_takes_writes(ha_object):
                        # every claim is journaled and waits five seconds before
                        # refusing; with N requests pending that is 5N seconds and
                        # N warnings per sweep for as long as the peer is away
                        self.logger.debug('firmware sweep skipped: not in sync with the peer')
                        if event.is_set():
                            return
                        sleep(5)
                        continue
                    requests.reclaim_abandoned()
                    pipeline = Helper().Pipeline()
                    for row in requests.pending():
                        if requests.claim(row['id']):
                            pipeline.add_nodes({row['id']: row})
                        else:
                            self.logger.warning(f'firmware request {row["id"]} for '
                                                f'{row["nodename"]} left queued: the claim '
                                                'could not be replicated; tried again next sweep')
                    if pipeline.has_nodes():
                        self.sweep_batches(pipeline, requests)
            except Exception as exp:
                self.logger.error(f'firmware sweep thread encountered problem: {exp}')
            if event.is_set():
                return
            sleep(5)


    def peer_takes_writes(self, ha_object=None):
        """
        Whether a journaled write would be accepted right now: a single controller
        always, an HA controller when in sync or overruled.
        """
        if not ha_object.get_hastate():
            return True
        return bool(ha_object.get_overrule() or ha_object.get_insync())


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


    def image_url(self, nodename=None, imagefile=None):
        """
        This method returns where this node's BMC can fetch an image from, or why it
        cannot.

        A BMC sits on the management network, so the address it can reach the
        controller on is the controller's address ON THAT network - not its cluster
        address, which is a different interface and unroutable from there.

        Both halves come from what Luna already knows how to work out. Which network
        the BMC is on is in the database, because Luna gave it that address. Which of
        the controller's own addresses is on that network is not - a controller has
        one ipaddress row and it is the cluster one - so it comes from the same walk
        of the interfaces that already maps a controller's NICs onto Luna's networks.

        It answers for this controller, which is the right one by construction: the
        sweep is master only and the image is staged on the machine running it.
        """
        if not imagefile:
            return False, NO_IMAGEFILE
        # the dry run looked; the sweep runs later, and the file can have gone in
        # between. One listing per flash is nothing against the minutes a flash takes
        if imagefile not in FirmwareCatalog().staged_images():
            return False, NO_IMAGE.format(imagefile=imagefile)
        bmc = Database().get_record_join(
            ['network.name as network'],
            ['nodeinterface.nodeid=node.id', 'ipaddress.tablerefid=nodeinterface.id',
             'network.id=ipaddress.networkid'],
            ['tableref="nodeinterface"', "nodeinterface.interface='BMC'",
             f"node.name='{nodename}'"])
        if not bmc or not bmc[0]['network']:
            return False, f'{nodename} has no BMC address on a network Luna knows'
        network = bmc[0]['network']
        addresses = Helper().get_controller_addresses_for_networks()
        source = addresses['ipv4'].get(network) or addresses['ipv6'].get(network)
        if not source:
            return False, (f'this controller has no address on {network}, so the BMC '
                           'has nowhere to fetch from')
        if ':' in source:
            source = f'[{source}]'
        protocol, port = self.file_port()
        return True, f'{protocol}://{source}:{port}/files/{imagefile}'


    def file_port(self):
        """
        This method returns (protocol, port) of the file server a BMC fetches from.
        """
        protocol, port = 'http', '7051'
        try:
            protocol = str(CONSTANT['WEBSERVER']['PROTOCOL'] or protocol)
            port = str(CONSTANT['WEBSERVER']['PORT'] or port)
        except (KeyError, TypeError):
            pass
        return protocol, port


    def follow(self, redfish=None, task=None, deadline=FLASH_DEADLINE):
        """
        This method waits on one firmware task and returns (state, reason).

        It only waits. Whether the flash worked is not this question - a task can
        report Completed over an image that went into the slot the machine is not
        booting from - so the answer here is handed to verify() and never treated as
        success on its own.
        """
        waited = 0
        while True:
            state, reason = self.track(redfish=redfish, task=task,
                                       deadline=deadline, waited=waited)
            if state != 'waiting':
                return state, reason
            sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL


    def wait_ready(self, redfish=None, deadline=READY_DEADLINE):
        """
        This method waits for the update service to be willing to take work.

        A board that has just flashed itself answers 503 for a while, and pushing
        into that window is accepted and silently discarded. So this is patient by
        design: not ready is a reason to come back, and only running out of patience
        is a failure.
        """
        waited = 0
        while True:
            status, reason = self.ready(redfish=redfish)
            if status:
                return True, None
            if waited >= deadline:
                return False, f'the update service was not ready after {waited}s: {reason}'
            sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL


    def update_node(self, request=None, redfish=None):
        """
        This method carries out one request, component by component, and answers
        whether the board is now running what the catalogue asked for.

        Every refusal that can be decided from stored state happens before a
        connection is made. What the node should run comes from the catalogue and its
        own inventory, so a node the catalogue does not cover, or one nobody has
        collected inventory from, is declined without waking a BMC.

        Components are done one at a time and each is verified before the next
        starts. Flashing a BMC takes its own service away for a minute or two, so the
        next component would otherwise be pushed into exactly the window that
        swallows things.
        """
        nodename = request.get('nodename')
        status, plan = FirmwareCatalog().plan(nodename=nodename)
        if not status:
            return False, f'{nodename}: {plan}'
        wanted = [item for item in plan['differs']
                  if not request.get('component') or item['component'] == request['component']]
        if not wanted:
            return True, f'{nodename}: already running what the catalogue asks'

        if redfish is None:
            from base.nodeinventory import NodeInventory
            from utils.redfish import Redfish
            status, access = NodeInventory().bmc_for(name=nodename)
            if not status:
                return False, f'{nodename}: {access}'
            redfish = Redfish(device=access['device'], username=access['username'],
                              password=access['password'], scheme=access['scheme'],
                              port=access['port'], verify=access['verify'])

        done = []
        for item in wanted:
            status, message = self.update_component(redfish=redfish, nodename=nodename,
                                                    item=item)
            if status is None:
                # the BMC was reset by its flash; nothing further can be flashed
                # through it now, and the restore is owed
                done.append(item['component'])
                if request.get('id'):
                    FirmwareRequest().mark_restore(request['id'])
                return True, f'{message}{self.reconfigure_note(done)}'
            if not status:
                return False, (f'{message}' if not done
                               else f'{message} (after {", ".join(done)})')
            done.append(item['component'])
        # the board answered the stored credentials on its intended address, so
        # those survived whatever the flash did. Whether the BIOS settings did is
        # asked of the board now, against what Luna last recorded for the node
        configname, drift = self.bios_drift(nodename=nodename, redfish=redfish)
        message = f'{nodename}: {", ".join(done)} now at the catalogue version; BMC configuration retained'
        if drift:
            if request.get('id'):
                FirmwareRequest().mark_restore(request['id'])
            return True, (f'{message}; {len(drift)} BIOS setting(s) differ from the recorded '
                          f'configuration {configname} - re-applied when the node next '
                          'installs through Luna')
        if configname:
            message += f' and BIOS settings as recorded ({configname})'
        return True, message


    def bios_drift(self, nodename=None, redfish=None):
        """
        This method compares the BIOS settings a node holds now with the
        configuration Luna last recorded for it, and returns (configuration name,
        {attribute: value the board now holds}) - (None, {}) where nothing was
        recorded or the board cannot be read.

        A read, never a write: it only answers whether a flash took the settings
        with it. Only attributes the board still publishes are compared; one it no
        longer publishes is a different question from one it changed.
        """
        snapshot = Database().get_record(
            table='nodeinventory',
            where=f'nodeid IN (SELECT id FROM node WHERE name = "{nodename}") '
                  'AND source = "redfish"')
        configname = str((snapshot or [{}])[0].get('bios_config') or '').strip()
        if not configname:
            return None, {}
        record = Database().get_record(table='biosconfig', where=f'name = "{configname}"')
        if not record:
            return None, {}
        from base.bios import Bios
        from utils.bios_push import BiosPush
        stored = Bios().stored_attributes(record[0]) or {}
        status, _, bios = BiosPush().bios_resource(redfish=redfish)
        if not status:
            return configname, {}
        current = (bios or {}).get('Attributes') or {}
        return configname, {name: current[name] for name, value in stored.items()
                            if name in current and current[name] != value}


    def resets_config(self, components=None):
        """
        This method says whether flashing these components can reset the BMC - the
        components that carry the BMC firmware itself. Whether a flash DID is
        decided from the board afterwards, not from this list.
        """
        return any(marker in str(component).upper()
                   for component in components or [] for marker in RESETS_BMC_CONFIG)


    def reconfigure_note(self, components=None):
        """
        This method returns the operator note for a flash that reset the BMC, or an
        empty string when none did.

        Kept apart from the success message so the wording lives in one place and can
        be asserted on its own. It says what Luna will do and what it will not: the
        address and credentials come back in band when the node next installs through
        Luna, the daemon then verifies the BMC and re-applies the BIOS configuration it
        last recorded for the node - and getting the node to that install is the
        operator's, because Luna reboots nothing on its own initiative.
        """
        if not self.resets_config(components):
            return ''
        return ('; its configuration was reset by the flash - boot the node through '
                'Luna (setupbmc): its address and credentials are restored in band, '
                'after which Luna verifies the BMC and re-applies the BIOS configuration '
                'it last recorded for this node. Until then Luna cannot reach it')


    def queue_restore(self, nodename=None):
        """
        This method queues the restore a flash left owed, when a node reports
        install.setupbmc. Returns the number of restores queued, so a caller can
        say whether anything is coming.

        Queued and not done here: the node's status update must not wait on its BMC.
        Not deferred either, unlike the inventory collection: the node is holding its
        install for exactly this, so the restore starts now and waits for the BMC
        itself, bounded.
        """
        node = Database().get_record(table='node', where=f'name = "{nodename}"')
        if not node:
            return 0
        pending = FirmwareRequest().restore_pending(nodeid=node[0]['id'])
        for row in pending:
            Queue().add_task_to_queue(task='restore_after_flash', param=nodename,
                                      subsystem='bios', request_id=row['request_id'])
        if pending:
            self.logger.info(f'{nodename} reported its BMC configured; the restore owed '
                             f'by its firmware flash is queued')
        return len(pending)


    def hold(self, nodename=None):
        """
        This method answers 'is anything scheduled for this node that may reset it':
        a restore owed by a firmware flash, or a BIOS push already queued or running.
        Decided when the install template is rendered, so the node needs nothing
        from the daemon afterwards: it waits a fixed, bounded time after setupbmc and
        continues regardless, and a daemon that stops cannot deadlock a node.
        """
        node = Database().get_record(table='node', where=f'name = "{nodename}"')
        if not node:
            return False, 'unknown node'
        if FirmwareRequest().restore_pending(nodeid=node[0]['id']):
            # a restore only resets the node when it has a BIOS configuration to put
            # back; with none recorded it verifies the BMC and touches nothing, and
            # holding for that would cost every plain BMC flash ten idle minutes
            snapshot = Database().get_record(
                table='nodeinventory',
                where=f'nodeid = "{node[0]["id"]}" AND source = "redfish"')
            row = (snapshot or [{}])[0]
            # ... and only on a board that can take the write. A board whose last
            # inventory found no settings object cannot be restored by a staged
            # push, so holding for it would be ten idle minutes before a refusal.
            # Unknown counts as writable: the safe side is to hold
            if (str(row.get('bios_config') or '').strip()
                    and str(row.get('bios_writable') or '') != '0'):
                return True, 'a restore owed by a firmware flash is scheduled'
        # a BIOS task carries the node as its parameter: bare for a restore,
        # node:config:policy for a push
        if Database().get_record(table='queue',
                                 where=f'subsystem = "bios" AND (param = "{nodename}" '
                                       f'OR param LIKE "{nodename}:%")'):
            return True, 'a BIOS task is scheduled'
        return False, 'nothing scheduled'


    def hold_seconds(self, nodename=None):
        """
        This method returns how long the installer should hold after setupbmc and
        why: the full bound when something is scheduled, nothing when nothing is.
        The reason is rendered into the install so the admin sees it on the console.
        """
        hold, reason = self.hold(nodename=nodename)
        return (HOLD_SECONDS if hold else 0), reason


    def restore_after_flash(self, nodename=None, request_id=None):
        """
        This method gives a node back what a flash took: it waits for the BMC to
        answer on its intended address with the stored credentials, then re-applies
        the BIOS configuration Luna last recorded for the node. Only what Luna
        itself applied is restored; a node with no recorded configuration gets its
        BMC verified and nothing else.

        Runs when the node reports install.setupbmc, which is the moment the address
        and credentials are back and the moment before anyone has touched the BIOS
        out of band. The BIOS push resets the machine as its stages need; the node
        is holding its install for that.
        """
        from base.nodeinventory import NodeInventory
        from utils.bios_push import BiosPush
        from utils.redfish import Redfish

        node = Database().get_record(table='node', where=f'name = "{nodename}"')
        if not node:
            return None, f'{nodename} no longer exists'
        pending = FirmwareRequest().restore_pending(nodeid=node[0]['id'])
        if not pending:
            return None, f'{nodename}: no restore is owed'
        status, message = self.restore_node(nodename=nodename, request_id=request_id,
                                            inventory=NodeInventory(), redfish_class=Redfish,
                                            bios=BiosPush())
        for row in pending:
            FirmwareRequest().finish_restore(requestid=row['id'], status=status,
                                             message=message)
        level = self.logger.info if status else self.logger.error
        level(f'restore after flash, {nodename}: {message}')
        if request_id:
            Status().add_message(request_id, 'luna', f'restore {nodename}: {message}')
        return status, message


    def restore_node(self, nodename=None, request_id=None, inventory=None,
                     redfish_class=None, bios=None, deadline=RESTORE_READY_DEADLINE):
        """
        This method does the work for restore_after_flash(), given its collaborators.
        """
        status, access = inventory.bmc_for(name=nodename)
        if not status:
            return False, f'BMC not verified: {access}'
        redfish = redfish_class(device=access['device'], username=access['username'],
                                password=access['password'], scheme=access['scheme'],
                                port=access['port'], verify=access['verify'])
        waited, reason = 0, None
        while True:
            status, reason, _ = redfish.system()
            if status:
                break
            if waited >= deadline:
                return False, (f'BMC at {access["device"]} did not answer with the stored '
                               f'credentials within {waited}s: {reason}')
            sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
        verified = f'BMC at {access["device"]} answers with the stored credentials'
        snapshot = Database().get_record(
            table='nodeinventory',
            where=f'nodeid IN (SELECT id FROM node WHERE name = "{nodename}") '
                  'AND source = "redfish"')
        configname = str((snapshot or [{}])[0].get('bios_config') or '').strip()
        if not configname:
            return True, f'{verified}; no BIOS configuration recorded for this node, nothing to restore'
        record = Database().get_record(table='biosconfig', where=f'name = "{configname}"')
        if not record:
            return False, (f'{verified}; the BIOS configuration {configname} recorded for '
                           'this node no longer exists, so it was not restored')
        from base.bios import Bios
        config = {'attributes': Bios().stored_attributes(record[0]),
                  'manufacturer': record[0]['manufacturer'],
                  'model': record[0]['model'],
                  'biosversion': record[0]['biosversion']}
        status, message = bios.push_node(nodename=nodename, config=config, policy='warn',
                                         request_id=request_id)
        if status:
            bios.record_applied(nodename=nodename, configname=configname)
            return True, f'{verified}; BIOS configuration {configname}: {message}'
        return False, f'{verified}; BIOS configuration {configname} not restored: {message}'


    def update_component(self, redfish=None, nodename=None, item=None):
        """
        This method flashes one component and reads the version back.
        """
        component = item['component']
        label = f'{nodename} {component}'
        status, reason = self.wait_ready(redfish=redfish)
        if not status:
            return False, f'{label}: {reason}'
        status, path, service = redfish.update_service()
        if not status:
            return False, f'{label}: {path}'
        kind, uri = self.push_target(service=service)
        if not kind:
            return False, f'{label}: {uri}'
        # a board that fetches needs a URL it can reach; one that is sent the image
        # needs the file here. Two questions with different failure modes, asked
        # separately so the refusal names the right one
        url, path = None, None
        if kind == SIMPLE:
            status, url = self.image_url(nodename=nodename, imagefile=item.get('imagefile'))
        else:
            status, path = self.image_path(imagefile=item.get('imagefile'))
        if not status:
            return False, f'{label}: {url or path}'
        action = ((service.get('Actions') or {}).get('#UpdateService.SimpleUpdate')) or {}
        status, answer = self.submit(redfish=redfish, kind=kind, uri=uri, action=action,
                                     image_url=url, component=component, image_path=path,
                                     service=service, plugin=self.vendor_plugin(nodename))
        if not status:
            return False, f'{label}: {answer}'
        state, reason = self.follow(redfish=redfish, task=answer)
        if state == 'failed':
            return False, f'{label}: {reason}'
        # 'gone' is the ordinary end of a flash on a service that deletes its task,
        # and 'finished' only says the service stopped working on it. Neither is
        # evidence, so both fall through to the one question that is
        status, version = self.verify(redfish=redfish, component=component,
                                      wanted=item['wanted'])
        if status is None and self.resets_config([component]):
            # the task completed and then the board stopped answering the stored
            # credentials: that is what a flash that resets the BMC looks like from
            # here. Flashed, unverified, configuration presumed gone - the caller
            # records the restore this leaves owed
            return None, (f'{label}: flashed (the task completed), but the board no '
                          f'longer answers the stored credentials - {version}')
        if not status:
            return False, f'{label}: {version}'
        return True, f'{label} is running {version}'
