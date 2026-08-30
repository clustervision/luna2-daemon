
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
This is the firmware catalogue, and what it says about a node.

The catalogue is desired state: for a given kind of hardware, which version each
firmware component should be running, and which image carries it. It is keyed on
the hardware and never on the group, because a group is an operational grouping
and not a statement about what is in the chassis - one group routinely holds more
than one platform, and a version that is right for one of them is meaningless for
the other.

So a group-wide instruction is answered per node: each node's own hardware selects
its own catalogue entries. That is the same rule the Redfish plugin path already
follows, and matching reuses the same normalisation - an operator writes
'Dell Inc.' or 'Dell' and either matches the board, because vendors do not spell
themselves consistently and nobody should have to guess which spelling arrived.

Two things are deliberately not here.

There is no ordering of versions. Firmware version strings are vendor-defined and
not comparable - the same lesson the BIOS attribute registry taught, where the
concept is universal and the identifier never is. 'Latest' is therefore whatever
the catalogue says it is, declared by whoever maintains it, and never a sort.

And nothing here talks to a BMC. Every answer below comes from stored inventory,
which is what makes it cheap enough to run over a whole cluster and truthful for
a machine that is switched off. The board remains the authority at the moment of
a push; this decides what is worth attempting.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import os
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.redfish import RedfishAccess


# Why a node cannot be pushed to, in the words the operator needs. Kept as
# constants because the group report groups by them: at four thousand nodes the
# failures share a handful of causes, and a line per node is unreadable.
NO_INVENTORY = 'no inventory; has this node booted?'
NO_ENTRY = 'no catalogue entry for this hardware'
NO_VERSION = 'the catalogue entry names no version'
NO_IMAGEFILE = 'the catalogue entry names no image file'
NO_IMAGE = 'image {imagefile} is not staged on this controller'


class FirmwareCatalog():
    """
    This class answers what the catalogue says a node should be running.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'firmwarecatalog'


    def hardware(self, nodename=None):
        """
        This method returns the (manufacturer, model) a node last reported, or
        (None, None) where nothing is known.

        (None, None) is not an error here, it is the ordinary state of a node that
        has never booted - and a node that has never booted almost certainly has no
        BMC address either, so it was never going to answer. Declining it early is
        cheaper than a connect timeout and truer than a failure.
        """
        return RedfishAccess().hardware(nodename=nodename)


    def entries(self, manufacturer=None, model=None):
        """
        This method returns the catalogue entries for one kind of hardware.

        Matching normalises both sides through the same function that names a
        plugin, so a row written as 'Dell Inc.' matches a board that says 'Dell'.
        """
        access = RedfishAccess()
        want = (access.token(manufacturer), access.token(model, first=False))
        if not all(want):
            return []
        return [row for row in Database().get_record(table=self.table) or []
                if (access.token(row['manufacturer']),
                    access.token(row['model'], first=False)) == want]


    def running(self, nodename=None):
        """
        This method returns what a node was last seen running, per component.

        Redfish wins over an in-band answer where both exist, for the reason it
        wins everywhere else: it is the BMC's own answer, and it is the one that
        exists before a node has ever been provisioned.
        """
        rows = Database().get_record(
            table='nodeinventoryfirmware',
            where=f'nodeid IN (SELECT id FROM node WHERE name = "{nodename}")')
        versions = {}
        for row in rows or []:
            component = str(row['component'] or '').strip()
            if not component:
                continue
            redfish = str(row['source'] or '').strip().lower() == 'redfish'
            if component not in versions or redfish:
                versions[component] = {'version': str(row['version'] or '').strip(),
                                       'updateable': bool(row['updateable']),
                                       'source': row['source']}
        return versions


    def staged_images(self):
        """
        This method returns the names of the image files present on this controller.

        preview() reads it once and hands it to every plan(): a stat per component
        per node is twelve thousand stats on a four-thousand-node dry run, where one
        directory listing answers for all of them. A directory that cannot be read
        stages nothing - every node is then skipped for a named file, which is loud
        in the right place, and the cause is in the log.
        """
        location = CONSTANT['FILES']['IMAGE_FILES']
        try:
            return set(os.listdir(location))
        except (OSError, TypeError) as exp:
            self.logger.error(f'cannot list the staged images in {location}: {exp}')
            return set()


    def plan(self, nodename=None, staged=None):
        """
        This method returns what a firmware push would do to one node, and why it
        would not, without contacting anything.

        Returns (status, answer). A False status carries the reason as a string,
        one of the constants above, so a caller fanning out over a group can group
        thousands of nodes by a handful of causes rather than printing a line each.

        An image is needed to flash, not to compare, so it is only looked for where
        a component would change: a fleet already on the catalogue version stays
        'as the catalogue asks' after the file has been tidied away.
        """
        if staged is None:
            staged = self.staged_images()
        manufacturer, model = self.hardware(nodename=nodename)
        if not manufacturer or not model:
            return False, NO_INVENTORY
        entries = self.entries(manufacturer=manufacturer, model=model)
        if not entries:
            return False, NO_ENTRY
        running = self.running(nodename=nodename)
        wanted, differs = [], []
        for entry in entries:
            version = str(entry['version'] or '').strip()
            if not version:
                return False, NO_VERSION
            component = str(entry['component'] or '').strip()
            current = running.get(component) or {}
            item = {'component': component, 'entry': entry['name'],
                    'wanted': version, 'running': current.get('version') or None,
                    'updateable': current.get('updateable'),
                    'imagefile': entry['imagefile']}
            wanted.append(item)
            if item['running'] != version:
                imagefile = str(entry['imagefile'] or '').strip()
                if not imagefile:
                    return False, NO_IMAGEFILE
                if imagefile not in staged:
                    return False, NO_IMAGE.format(imagefile=imagefile)
                differs.append(item)
        return True, {'node': nodename, 'hardware': (manufacturer, model),
                      'components': wanted, 'differs': differs}


    def preview(self, nodenames=None):
        """
        This method answers the same question for many nodes, grouped by cause.

        A group instruction is a per-node question asked many times - one group can
        hold several platforms, so 'what would this do' has a different answer for
        each member. What it must not do is report that node by node: at four
        thousand nodes the skips share a handful of reasons, and a line each is a
        wall nobody reads.

        Nodes that cannot be pushed to do not stop the ones that can. A node with no
        inventory has almost certainly never had a BMC configured, so it was not a
        candidate rather than a failure - and letting it block a rack would be the
        wrong way round.
        """
        ready, skipped = [], {}
        staged = self.staged_images()
        for nodename in nodenames or []:
            status, answer = self.plan(nodename=nodename, staged=staged)
            if status:
                ready.append(answer)
            else:
                skipped.setdefault(answer, []).append(nodename)
        return {'ready': ready, 'skipped': skipped,
                'summary': self.summarise(ready=ready, skipped=skipped)}


    def summarise(self, ready=None, skipped=None):
        """
        This method renders the counts an operator reads before deciding to push.

        Says what would change rather than what was looked at: a node already on the
        catalogue version is not work, and counting it as work would make a push of
        nothing look like a push of everything.
        """
        changing = [answer for answer in ready or [] if answer['differs']]
        lines = [f'{len(changing)} node(s) would change, '
                 f'{len(ready or []) - len(changing)} already as the catalogue asks']
        for reason, nodes in sorted((skipped or {}).items()):
            lines.append(f'{len(nodes)} skipped: {reason}')
        return lines


# What a request is doing. 'queued' is waiting for the sweeper, 'in progress' has
# been claimed by it, and anything else is a finished state kept for the status view.
QUEUED = 'queued'
CLAIMED = 'in progress'


class FirmwareRequest():
    """
    This class records that somebody asked for a node's firmware to be updated, and
    is what the sweeper reads.

    A request is stored rather than derived, and that is the whole point. What the
    catalogue says a node SHOULD run is derivable at any moment - that is what the
    preview answers - but a flash is not a reconciliation. Acting on drift by itself
    would mean a cluster reflashing because somebody edited a catalogue row, which is
    the same reasoning that made a BIOS push explicit and applies harder here.

    It lives in its own replicated table rather than in the queue. The queue is not
    replicated: a task reaches the other controller only as a journal replay and the
    passive one drops it, so work recorded only there is lost at a failover. A row
    here is backed up, hashed and replicated, so a request outlives the controller
    that took it.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'firmwarerequest'


    def record(self, nodeids=None, component=None, request_id=None):
        """
        This method records a request for each node, and returns how many it wrote.

        One row per node, because a node is the unit the work is done in and the unit
        an answer is given about. Asking twice is not collapsed: the operator asked
        again, and the catalogue or the machine may well have moved on since.
        """
        written = 0
        for nodeid in nodeids or []:
            row = Helper().make_rows({'nodeid': nodeid, 'component': component or '',
                                      'request_id': request_id or '',
                                      'status': QUEUED, 'created': 'NOW'})
            if Database().insert(self.table, row):
                written += 1
        return written


    def pending(self, status=QUEUED):
        """
        This method returns every request waiting, node name included, in one query.

        One query and not one per node: the sweeper's whole job is to find the work,
        and a sweep whose cost grows a round trip at a time is one that stops being
        affordable exactly when a cluster is large enough to need it.
        """
        return Database().get_record_join(
            ['firmwarerequest.id', 'firmwarerequest.nodeid', 'firmwarerequest.component',
             'firmwarerequest.request_id', 'node.name as nodename'],
            ['node.id=firmwarerequest.nodeid'],
            [f'firmwarerequest.status="{status}"']) or []


    def claim(self, requestid=None):
        """
        This method marks one request as taken, and it marks rather than deletes.

        A request removed when it is claimed is lost if the daemon stops mid-flash,
        and the node is then left part-updated with nothing recording that anybody
        ever asked. Marked, it can be reclaimed.
        """
        Database().update(self.table, Helper().make_rows({'status': CLAIMED, 'updated': 'NOW'}),
                          [{"column": "id", "value": requestid}])


    def finish(self, requestid=None, status=None, message=None):
        """
        This method records how a request ended, and leaves the row for the status view.
        """
        Database().update(self.table,
                          Helper().make_rows({'status': 'done' if status else 'failed',
                                              'message': str(message or '')[:2000],
                                              'updated': 'NOW'}),
                          [{"column": "id", "value": requestid}])


    def reclaim_abandoned(self, minutes=60):
        """
        This method returns requests a stopped daemon left claimed, to be tried again.

        Nothing else will ever pick them up. A firmware flash is long enough that the
        window has to be generous, which is why it is an hour rather than the half
        hour a profile delivery uses.
        """
        stale = Database().get_record(
            table=self.table,
            where=f'status="{CLAIMED}" AND updated<datetime("now","-{minutes} minute")') or []
        for row in stale:
            self.logger.warning(f'firmware request {row["id"]} was left in progress; '
                                'it will be tried again')
            Database().update(self.table, Helper().make_rows({'status': QUEUED}),
                              [{"column": "id", "value": row['id']}])
        return stale
