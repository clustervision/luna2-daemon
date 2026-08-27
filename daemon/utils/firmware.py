
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


from utils.log import Log
from utils.database import Database
from utils.redfish import RedfishAccess


# Why a node cannot be pushed to, in the words the operator needs. Kept as
# constants because the group report groups by them: at four thousand nodes the
# failures share a handful of causes, and a line per node is unreadable.
NO_INVENTORY = 'no inventory; has this node booted?'
NO_ENTRY = 'no catalogue entry for this hardware'
NO_VERSION = 'the catalogue entry names no version'


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


    def plan(self, nodename=None):
        """
        This method returns what a firmware push would do to one node, and why it
        would not, without contacting anything.

        Returns (status, answer). A False status carries the reason as a string,
        one of the constants above, so a caller fanning out over a group can group
        thousands of nodes by a handful of causes rather than printing a line each.
        """
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
        for nodename in nodenames or []:
            status, answer = self.plan(nodename=nodename)
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
