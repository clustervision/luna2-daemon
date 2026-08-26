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
from utils.database import Database
from utils.log import Log
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
            'grab_exclude': ', '.join(self.exclude_list(record)),
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
        unknown = [key for key in data if key not in self.editable + ['newbiosname']]
        if unknown:
            return False, f"Cannot set {', '.join(sorted(unknown))} on a BIOS configuration"

        record = Database().get_record(table=self.table, where=f'name = "{name}"')
        row = {}
        if 'grab_exclude' in data:
            row['grab_exclude'] = self.encode(data['grab_exclude'])
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
        for member in collection.get('Members') or []:
            path = member.get('@odata.id')
            if not path:
                continue
            status, entry = redfish.get(path=path, cache=True)
            # a registry that will not load is not the one we want; keep looking
            # rather than abandoning the search on the first bad member
            if not status or entry.get('Registry') != wanted:
                continue
            for location in entry.get('Location') or []:
                uri = location.get('Uri')
                if not uri:
                    continue
                status, registry = redfish.get(path=uri)
                if status:
                    return True, registry
            return False, f'registry {wanted} lists no readable location'
        return False, f'registry {wanted} is not published by this machine'


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
