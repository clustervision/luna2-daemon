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
Bios Class will handle stored BIOS configurations.

A configuration is grabbed from one node and pushed to others, which is the same
shape osgrab and ospush already have for an operating system - a golden machine,
a stored artefact, and an explicit instruction to put it somewhere else. Nothing
here happens on its own: there is no sweep and no reconciler, because a BIOS
change on a node nobody asked about is not a service we want to offer.

What may be carried to another machine is decided by the target's own attribute
registry rather than by a list we maintain per vendor and per model - see
utils/bios.py. The configuration carries its own exclude list on top of that,
exactly as an osimage carries grab_exclude, so a site can drop things we would
not have thought of without waiting for us.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from base64 import b64encode, b64decode
from datetime import datetime
from json import dumps, loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.queue import Queue
from utils.status import Status
from utils.helper import Helper
from utils.bios import Bios as BiosPlanner, DEFAULT_EXCLUDE
from utils.redfish import Redfish
from base.nodeinventory import NodeInventory


class Bios():
    """
    This class is responsible for all operations on stored BIOS configurations.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'biosconfig'
        self.planner = BiosPlanner()
        # what an administrator may set; everything else on the row is written by
        # a grab and is a statement about the machine it came from
        self.editable = ['grab_exclude', 'comment']


    def encode(self, value=None):
        """
        This method encodes a value for storage. Always, never sometimes - a
        column that is only sometimes encoded pushes a guess onto every reader.
        """
        return b64encode(str(value).encode()).decode('ascii')


    def decode(self, value=None):
        """
        This method decodes a stored value.

        A row written before this column existed, or one an administrator has
        edited straight in the database, is not base64 and must not be turned
        into nonsense - so a value that will not decode is returned as it stands
        and the caller sees what is really there.
        """
        if not value:
            return ''
        try:
            return b64decode(str(value), validate=True).decode('utf-8')
        except Exception:
            return str(value)


    def exclude_list(self, record=None):
        """
        This method returns a configuration's exclude patterns as a list.

        Comma separated, as osimage's grab_exclude is, so an administrator who
        knows one knows the other.
        """
        raw = self.decode((record or {}).get('grab_exclude'))
        return [item.strip() for item in raw.split(',') if item.strip()]


    def get_all_bios(self):
        """
        This method will return all the BIOS configurations.
        """
        records = Database().get_record(table=self.table, where=None)
        if not records:
            return False, 'No BIOS configuration is available'
        response = {'config': {self.table: {}}}
        for record in records:
            response['config'][self.table][record['name']] = self.detail(record)
        return True, response


    def get_bios(self, name=None):
        """
        This method will return one BIOS configuration, with its attributes.
        """
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not record:
            return False, f'BIOS configuration {name} is not available'
        detail = self.detail(record[0])
        detail['attributes'] = self.stored_attributes(record[0])
        return True, {'config': {self.table: {name: detail}}}

    def detail(self, record=None):
        """
        This method builds the summary of one configuration.

        The name is in the dict as well as being the key it lands under, and both
        deliberately: the generic list renderer looks its columns up inside the
        record and prints --NA-- for anything it cannot find there.

        The node is resolved to its name here rather than stored as one. It is
        provenance and nothing acts on it, so a node that has since been deleted
        simply reports as unknown rather than making the configuration unusable.
        """
        attributes = self.stored_attributes(record)
        node = Database().name_by_id('node', record['nodeid']) if record['nodeid'] else None
        return {
            'name': record['name'],
            'manufacturer': record['manufacturer'],
            'model': record['model'],
            'biosversion': record['biosversion'],
            'grabbedfrom': node or '',
            'settings': len(attributes),
            # returned as stored, which is how it was sent: the client decodes
            # its editor keys for display, and handing back a decoded value here
            # would leave it showing something no other entity shows
            'grab_exclude': record['grab_exclude'],
            'updated': record['updated'],
            'comment': record['comment']
        }


    def stored_attributes(self, record=None):
        """
        This method returns a configuration's attributes as a dict.

        A row whose attributes will not parse is reported empty and said out loud
        rather than raising: the configuration is still there to be looked at and
        repaired, and an exception here would take out the list of every other
        configuration alongside it.
        """
        raw = self.decode((record or {}).get('attributes'))
        if not raw:
            return {}
        try:
            return loads(raw)
        except ValueError:
            self.logger.error(f"BIOS configuration {record.get('name')} has unreadable attributes")
            return {}


    def update_bios(self, name=None, request_data=None):
        """
        This method will create or update what an administrator owns on a BIOS
        configuration - its exclude list and its comment.

        It deliberately does not take attributes. Those are what a machine said
        about itself, and a configuration hand-edited into something no machine
        ever reported is the thing a golden node exists to avoid.
        """
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        try:
            data = request_data['config'][self.table][name]
        except (KeyError, TypeError):
            return False, 'Invalid request: BIOS configuration data not found in structure'
        # The CLI puts the record's own name in the body as well as in the URL, so
        # it arrives on every change. It is the identity rather than a field, and
        # the URL is what says which record is meant, so it is accepted and
        # ignored. Rejecting it made every 'luna biosconfig change' fail.
        unknown = [key for key in data if key not in self.editable + ['newbiosname', 'name']]
        if unknown:
            return False, f"Cannot set {', '.join(sorted(unknown))} on a BIOS configuration"

        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        row = {}
        if 'grab_exclude' in data:
            # It arrives base64 and it is stored base64: grab_exclude is one of the
            # CLI's editor keys, so the client has already encoded it, exactly as it
            # does for comment. Encoding it again here stored a value that decoded
            # to base64 rather than to the patterns, and the next grab excluded
            # nothing. Both directions agree - what is sent encoded is stored and
            # returned encoded, so no caller has to guess.
            row['grab_exclude'] = data['grab_exclude']
        if 'comment' in data:
            row['comment'] = data['comment']
        if not record:
            return False, (f'BIOS configuration {name} is not available; '
                           'it is created by grabbing one from a node')
        if 'newbiosname' in data:
            if Database().get_record(table=self.table, where=f"name = \"{data['newbiosname']}\""):
                return False, f"BIOS configuration {data['newbiosname']} already exists"
            row['name'] = data['newbiosname']
        if not row:
            return False, 'Nothing to update'
        Database().update(self.table, Helper().make_rows(row),
                          [{"column": "id", "value": record[0]['id']}])
        return True, f'BIOS configuration {name} updated'


    def delete_bios(self, name=None):
        """
        This method will delete a BIOS configuration.
        """
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if not record:
            return False, f'BIOS configuration {name} is not available'
        Database().delete_row(self.table, [{"column": "id", "value": record[0]['id']}])
        return True, f'BIOS configuration {name} removed'


    def registry(self, redfish=None, bios=None):
        """
        This method resolves the BIOS attribute registry a machine points at.

        The Bios resource names a registry by id, and the id has to be looked up
        in the service's registry collection to get a URI. That indirection is
        the standard's, not a vendor's, and skipping it - guessing the path -
        works on one machine and not the next.

        Three fields can carry the name and services do not agree on which. A
        collection entry has a Registry and an Id, and the document it points at
        has an Id of its own; where a service is tidy all three say the same
        thing, and where it is not, insisting on one of them refuses a registry
        that is published and findable. So all three are accepted - the two free
        ones first, and the document's own Id only for what is left, because that
        one costs a fetch per candidate.

        This is not the same as guessing a path, which is the thing this method
        exists to avoid. It is still the service telling us which registry this
        is; only the field it chose to say it in differs.

        Returns (True, registry) or (False, reason). A machine that serves no
        registry is a real answer rather than an error, and it is the caller that
        decides what to do about it.
        """
        wanted = (bios or {}).get('AttributeRegistry')
        if not wanted:
            return False, 'this machine names no BIOS attribute registry'
        status, collection = redfish.get(path='/redfish/v1/Registries', cache=True)
        if not status:
            return False, f'registry collection unreadable: {collection}'
        candidates = []
        for member in collection.get('Members') or []:
            path = member.get('@odata.id')
            if not path:
                continue
            status, entry = redfish.get(path=path, cache=True)
            # a registry that will not load is not the one we want; keep looking
            # rather than abandoning the search on the first bad member
            if not status:
                continue
            if wanted in (entry.get('Registry'), entry.get('Id')):
                found, registry = self.located(redfish=redfish, entry=entry)
                if found:
                    return True, registry
                return False, f'registry {wanted} lists no readable location'
            candidates.append(entry)
        for entry in candidates:
            found, registry = self.located(redfish=redfish, entry=entry)
            if found and registry.get('Id') == wanted:
                self.logger.info(
                    f'this service names BIOS registry {wanted} only in the '
                    f'document itself; its collection entry calls it '
                    f'{entry.get("Id")}/{entry.get("Registry")}'
                )
                return True, registry
        return False, f'registry {wanted} is not published by this machine'


    def located(self, redfish=None, entry=None):
        """
        This method reads the document a registry collection entry points at.

        A entry may list several locations - languages, or a local copy beside a
        published URI - so the first one that answers wins rather than the first
        one listed.
        """
        for location in (entry or {}).get('Location') or []:
            uri = location.get('Uri')
            if not uri:
                continue
            status, registry = redfish.get(path=uri, cache=True)
            if status:
                return True, registry
        return False, None


    def collect_bios(self, node=None, name=None):
        """
        This method reads a node's BIOS over Redfish and hands back what would be
        stored, without storing it.

        It collects and does not write for the same reason the inventory
        collector does not: storing it is a replicated change, and the route is
        what decides replication.

        The registry is what says which attributes may travel. A machine that
        publishes none is refused rather than grabbed wholesale - a configuration
        we cannot filter is one we would push identity values out of, and the
        node it came from is the only machine that can tell us which those are.
        """
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        exclude = self.exclude_list(record[0]) if record else list(DEFAULT_EXCLUDE)

        status, access = NodeInventory().bmc_for(name=node)
        if not status:
            return False, access
        redfish = Redfish(device=access['device'], username=access['username'],
                          password=access['password'], scheme=access['scheme'],
                          port=access['port'], verify=access['verify'])
        status, path, system = redfish.system()
        if not status:
            return False, f'{node}: {path}'
        bios_path = (system.get('Bios') or {}).get('@odata.id')
        if not bios_path:
            return False, f'{node}: this machine exposes no Bios resource'
        status, bios = redfish.get(path=bios_path)
        if not status:
            return False, f'{node}: {bios}'
        attributes = bios.get('Attributes')
        if not isinstance(attributes, dict) or not attributes:
            return False, f'{node}: the Bios resource carries no attributes'

        status, registry = self.registry(redfish=redfish, bios=bios)
        if not status:
            return False, f'{node}: {registry}'
        kept, dropped = self.planner.portable(registry=registry, attributes=attributes,
                                              exclude=exclude)
        if not kept:
            return False, (f'{node}: nothing in this machine\'s BIOS may be carried '
                           f'to another; {len(dropped)} attribute(s) were dropped')
        return True, {'config': {self.table: {name: {
            'attributes': kept,
            'dropped': dropped,
            'manufacturer': system.get('Manufacturer'),
            'model': system.get('Model'),
            'biosversion': system.get('BiosVersion'),
            'node': node
        }}}}


    def store_grabbed(self, name=None, payload=None):
        """
        This method stores what collect_bios read. Replicated, so it is reached
        through the journal and never called from the route directly.
        """
        try:
            data = payload['config'][self.table][name]
        except (KeyError, TypeError):
            return False, 'Invalid request: BIOS configuration data not found in structure'
        node = Database().get_record(table='node', where=f"name = \"{data.get('node')}\"")
        row = {
            'name': name,
            'manufacturer': data.get('manufacturer'),
            'model': data.get('model'),
            'biosversion': data.get('biosversion'),
            'nodeid': node[0]['id'] if node else None,
            'attributes': self.encode(dumps(data.get('attributes') or {})),
            'updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        if record:
            Database().update(self.table, Helper().make_rows(row),
                              [{"column": "id", "value": record[0]['id']}])
        else:
            # a new configuration is seeded with the shipped exclude list rather
            # than an empty one, so it is visible and editable from the start -
            # an administrator who cannot see what was excluded cannot judge it
            row['grab_exclude'] = self.encode(', '.join(DEFAULT_EXCLUDE))
            Database().insert(self.table, Helper().make_rows(row))
        dropped = data.get('dropped') or {}
        kept = len(data.get('attributes') or {})
        return True, (f"BIOS configuration {name} grabbed from {data.get('node')}: "
                      f"{kept} setting(s) stored, {len(dropped)} not carried")


    def push_targets(self, object_type=None, name=None):
        """
        This method resolves what a push was aimed at into a list of node names.

        A group is expanded here, at the edge, rather than carried as a group
        into the queue: the members are read now, so a node added to the group
        after the operator asked is not silently included in something they did
        not see.
        """
        if object_type == 'group':
            # the group is looked up on its own and the nodes fetched by id,
            # rather than joined on group.name. 'group' is a reserved SQL word,
            # so a where clause naming it is a syntax error - and the error is
            # logged and swallowed, so the caller gets an empty result and
            # reports the group as having no nodes. Empty and broken look
            # identical, which is exactly why this is not written the short way
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if not group:
                return False, f'group {name} does not exist'
            nodes = Database().get_record(table='node',
                                          where=f"groupid = \"{group[0]['id']}\"")
            if not nodes:
                return False, f'group {name} has no nodes'
            return True, [node['name'] for node in nodes]
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return False, f'node {name} does not exist'
        return True, [name]


    def status(self, name=None, group=None):
        """
        Where every node stands on its BIOS, from what is stored - no BMC is
        contacted, and no node needs to be powered on.

        This answers the question an operator asks weeks after a push, when the
        machines may well be off: what is holding which configuration, and when
        did we last actually look. It deliberately does NOT answer "how many
        stages remain", because that needs the board's registry and its current
        values, and a stored answer presented as a current one is worse than no
        answer. `luna node biospush` recomputes that against the machine, which is
        the only place it can honestly be computed.

        Three fields carry the whole of it, which is why this costs bytes per node
        rather than the tens of megabytes the attribute sets themselves would:
        the digest of what the machine held when we last read it, the name of the
        configuration it was last found to match, and the digest it had at that
        moment. Drift is the third disagreeing with the first.

        Scoped to one node, to one group, or to the whole cluster. A BIOS
        configuration is as much a group-level thing as a node-level one - a GPU
        group and a plain compute group want different settings - so the group is
        both a filter and a column, and an operator can ask about one without
        reading past the other.

        States, and each says something different:
          matched      the last read found it holding that configuration
          drifted      it matched once, and its BIOS has moved since - somebody
                       changed something outside Luna, or a push half landed
          collected    we have read its BIOS and it matches no configuration
          unknown      no Redfish inventory has ever been taken from it, so we
                       have never looked. Not a problem, just not an answer
        """
        if group and not name:
            # 'group' is a reserved SQL word, so it is backticked - the form
            # utils/osimage.py already uses. Bare, the statement is a syntax error
            # that the daemon logs and swallows, and the caller then gets an empty
            # result that reads exactly like a group with no nodes
            nodes = Database().get_record_join(
                ['node.id as id', 'node.name as name', 'node.groupid as groupid'],
                ['group.id=node.groupid'], [f'`group`.name="{group}"'])
        else:
            nodes = Database().get_record(
                table='node', where=f'name = "{name}"' if name else None)
        if not nodes:
            if name:
                return False, f'Node {name} is not available'
            if group:
                # only on the empty path, and only to tell the two apart: a group
                # nobody made and a group nobody put a node in want different answers
                exists = Database().get_record(table='group', where=f'name = "{group}"')
                return False, (f'Group {group} has no nodes' if exists
                               else f'Group {group} is not available')
            return False, 'No nodes available'
        # one lookup for the whole cluster rather than one per node: at four thousand
        # nodes the difference is a query and four thousand queries
        groups = {record['id']: record['name']
                  for record in Database().get_record(table='group') or []}
        response = {'config': {self.table: {'status': {}, 'summary': {}}}}
        for node in nodes:
            row = self.stored_state(nodeid=node['id'])
            row['group'] = groups.get(node['groupid']) or ''
            response['config'][self.table]['status'][node['name']] = row
            summary = response['config'][self.table]['summary']
            summary[row['state']] = summary.get(row['state'], 0) + 1
        return True, response


    def stored_state(self, nodeid=None):
        """
        This method reads one node's stored BIOS state and names it.
        """
        row = {'config': '', 'digest': '', 'state': 'unknown',
               'bios_version': '', 'since': ''}
        snapshot = Database().get_record(
            table='nodeinventory',
            where=f'nodeid = "{nodeid}" AND source = "redfish"')
        if not snapshot:
            return row
        held = snapshot[0]
        digest = held.get('bios_digest') or ''
        row['config'] = held.get('bios_config') or ''
        row['digest'] = digest[:12]
        row['bios_version'] = held.get('bios_version') or ''
        row['since'] = held.get('updated') or ''
        if not digest:
            return row
        if not row['config']:
            row['state'] = 'collected'
        elif digest == (held.get('bios_config_digest') or ''):
            row['state'] = 'matched'
        else:
            row['state'] = 'drifted'
        return row


    def record_match(self, name=None, payload=None):
        """
        This method records that a node was found holding a configuration.

        Written where the inventory lives rather than on the node, because it is an
        observation about the machine and belongs beside the rest of what we
        observed - backed up with it, and carrying its own timestamp so nobody
        mistakes it for current.

        And written *through the journal*, because nodeinventory is in
        Tables().tables: the peer is expected to hold identical content and the
        controllers compare hashes over it. Updating it directly would work
        perfectly on the controller that ran the push and leave the other one
        disagreeing on that table forever - which the secondary answers by clearing
        and re-importing the whole of it. The collector beside this one goes through
        the journal for exactly the same reason.

        The signature is (object, payload) because that is the shape the journal
        dispatches: it guesses arity from which of object/param/payload are set.
        """
        config = (payload or {}).get('config') or ''
        digest = (payload or {}).get('digest') or ''
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return False
        if not Database().get_record(table='nodeinventory',
                                     where=f"nodeid = \"{node[0]['id']}\" "
                                           f'AND source = "redfish"'):
            # nothing collected from this machine, so there is no observation to
            # annotate. Inventing the row would put a BIOS record beside no inventory
            return False
        Database().update('nodeinventory',
                          Helper().make_rows({'bios_config': config,
                                              'bios_config_digest': digest,
                                              'bios_digest': digest}),
                          [{"column": "nodeid", "value": node[0]['id']},
                           {"column": "source", "value": "redfish"}])
        return True


    def push_bios(self, object_type=None, name=None, request_data=None):
        """
        This method queues a BIOS configuration to be applied to a node or to
        every node of a group, and hands back the request to watch.

        It queues and does not apply. A stage is a write, a reset and a wait for
        POST, and a machine can need several - so this would hold an HTTP request
        open for the better part of an hour. The work is reported through the
        status channel instead, which is what the osimage push already does.

        Nothing here happens on its own: this is the only way a BIOS setting is
        ever written to a machine by Luna.
        """
        try:
            data = request_data['config'][object_type][name]
            configname = data['biosconfig']
        except (KeyError, TypeError):
            return False, 'Invalid request: no biosconfig name supplied'
        record = Database().get_record(table=self.table, where=f'name = "{configname}"')
        if not record:
            return False, f'BIOS configuration {configname} is not available'
        if not self.stored_attributes(record[0]):
            return False, (f'BIOS configuration {configname} carries no settings; '
                           'grab it from a node first')
        policy = str(data.get('version_match') or self.version_policy()).strip().lower()

        status, targets = self.push_targets(object_type=object_type, name=name)
        if not status:
            return False, targets
        request_id = Status().gen_request_id()
        for target in targets:
            # force, because the collapse window would fold a second push of the
            # same configuration into the first one - and here that is wrong: the
            # operator asked again, and the machine may well have moved on
            Queue().add_task_to_queue(task='push_bios',
                                      param=f'{target}:{configname}:{policy}',
                                      subsystem='bios', request_id=request_id, force=True)
        Status().add_message(request_id, 'luna',
                             f'queued {configname} for {len(targets)} node(s)')
        return True, f'BIOS configuration {configname} queued for {len(targets)} node(s)', request_id


    def version_policy(self):
        """
        How strict to be about a BIOS version difference, from luna.ini.

        Read as optional with the default in code. [BIOS] is only there if an
        administrator put it there, and declaring it required would abort startup
        on every existing configuration that does not have it - before the logger
        exists to say why.
        """
        try:
            return str(CONSTANT['BIOS']['VERSION_MATCH']).strip().lower()
        except (KeyError, TypeError):
            return 'warn'
