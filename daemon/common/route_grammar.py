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
What every route requires, derived from its path.

The token carries who; the path carries what is asked of which object. The entity is
path segment two under /config, the object is the path's name argument, and the verb
comes from the action suffix, else GET reads and POST writes. Where the suffix would
lie about the verb it is in a named table here. There is no default: a route this
module cannot place raises, and the derived test over the registered routes fails on it.

Nothing here refuses anything. The decorators store the answer on the request; the bit
check against the object's columns is a later step.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class GrammarError(Exception):
    """
    A route the grammar cannot place. Never caught into a default.
    """


# Routes deliberately without a token: the boot path, read-only monitoring and the
# HA liveness probe.
# Listed as (rule, method) so a route that loses or gains its decorator fails the test.
OPEN = {
    ('/token', 'POST'), ('/tpm/<string:nodename>', 'POST'), ('/filesauth', 'GET'),
    ('/boot', 'GET'), ('/boot/short', 'GET'), ('/boot/disk', 'GET'),
    ('/boot/switch/<string:name>', 'GET'), ('/boot/switch/<string:name>/commands', 'GET'),
    ('/boot/search/mac/<string:macaddress>', 'GET'),
    ('/boot/manual/group/<string:groupname>/<string:macaddress>', 'GET'),
    ('/boot/manual/hostname/<string:hostname>/<string:macaddress>', 'GET'),
    ('/kickstart/install/<string:node>', 'GET'),
    ('/config/status/<string:request_id>', 'GET'), ('/control/status/<string:request_id>', 'GET'),
    ('/service/status/<string:request_id>', 'GET'),
    ('/files', 'GET'), ('/files/<string:filename>', 'GET'),
    ('/monitor/sync', 'GET'), ('/monitor/osimage', 'GET'), ('/monitor/ha', 'GET'),
    ('/monitor/mother', 'GET'), ('/monitor/node', 'GET'),
    ('/monitor/service/<string:name>', 'GET'), ('/monitor/node/<string:node>', 'GET'),
    ('/monitor/ha/<string:name>', 'GET'), ('/monitor/sync/<string:name>', 'GET'),
    ('/monitor/osimage/<string:name>', 'GET'), ('/monitor/mother/<string:name>', 'GET'),
    ('/export/<string:name>', 'GET'), ('/announce', 'GET'), ('/scrape', 'GET'), ('/ping', 'GET'),
}

# Whole families that stay with rootus: controller-to-controller traffic, HA, service
# control, table data, import and export, OS accounts, and the identity tables.
ROOTUS_FAMILIES = {'hash', 'table', 'journal', 'ha', 'service', 'import', 'export', 'monitor'}
ROOTUS_ENTITIES = {'osuser', 'osgroup', 'user', 'usergroupmap'}

# Path words that are not the entity they sit under.
ALIAS = {'otherdev': 'otherdevices', 'profiles': 'profile', 'osimagetag': 'osimage', 'dns': 'network'}

# Suffixes that state the verb outright.
SUFFIX_BITS = {'_delete': 'w', '_remove': 'w', '_unassign': 'w', '_pack': 'w', '_cancel': 'w',
               '_updatecerts': 'w', '_member': 'r', '_nextfreeip': 'r', '_preview': 'r'}

# Suffixes whose check spans two objects or a create; each is resolved by name later.
# clone: w on the new object's class and r on the source. push and grab: x on the node
# or group and w on the catalogue object. redfish and provision: x on the node.
# couple and decouple: w on the target and r on the route.
SUFFIX_OVERRIDES = {'_clone', '_osgrab', '_ospush', '_biosgrab', '_biospush', '_firmwarepush',
                    '_redfish', '_provision', '_couple', '_decouple', '_chmod', '_chgrp', '_chown'}

KINDS = ('open', 'self', 'rootus', 'provision', 'dynamic', 'membership', 'object', 'override')


def requirement(rule=None, method=None, args=None, declared=None):
    """
    Input - a Flask rule, the method, the path arguments of the request, and what the
            route declared on its decorator, if anything: a kind such as 'rootus', or an
            (entity, bit) pair. A declaration wins; the grammar answers the rest.
    Output - a dict with kind, and for objects entity, name and bit
    """
    args = args or {}
    parts = rule.strip('/').split('/')
    head = parts[0]
    if declared is not None:
        if isinstance(declared, str):
            if declared not in KINDS:
                raise GrammarError(f'{method} {rule} declares an unknown kind {declared}')
            return {'kind': declared, 'entity': head}
        entity, bit = declared
        if bit not in ('r', 'w', 'x'):
            raise GrammarError(f'{method} {rule} declares an unknown bit {bit}')
        return {'kind': 'object', 'entity': entity, 'name': args.get('name'), 'bit': bit}
    if (rule, method) in OPEN:
        return {'kind': 'open'}
    if head == 'whoami':
        return {'kind': 'self'}
    if head == 'control':
        return {'kind': 'dynamic', 'entity': 'node', 'name': args.get('hostname'), 'action': args.get('action')}
    if head in ROOTUS_FAMILIES:
        return {'kind': 'rootus', 'entity': head}
    if head == 'boot':
        return {'kind': 'provision', 'entity': 'node', 'name': args.get('node')}
    if head != 'config' or len(parts) < 2:
        raise GrammarError(f'{method} {rule} is not a route the grammar knows')
    entity = parts[1]
    generic = entity.startswith('<')
    if generic:
        # the generic chmod, chgrp and chown routes name the entity and the object in the path
        entity = args.get('entity') or entity
    if entity in ROOTUS_ENTITIES:
        return {'kind': 'rootus', 'entity': entity}
    if entity == 'usergroup':
        if 'members' in parts:
            return {'kind': 'membership', 'entity': 'usergroup', 'name': args.get('name'),
                    'bit': 'r' if method == 'GET' else 'w'}
        return {'kind': 'rootus', 'entity': entity}
    if entity == 'secrets' and len(parts) > 2 and parts[2] == 'cluster':
        # clustersecrets is the named exception: cluster is readable by everyone, its secrets are not
        return {'kind': 'rootus', 'entity': 'clustersecrets'}
    if entity in ('secrets', 'profiles') and len(parts) > 2 and parts[2] in ('node', 'group', 'cluster'):
        entity = parts[2]
    elif entity == 'secrets':
        # the listing across node, group and cluster secrets; the rows are filtered per parent
        return {'kind': 'object', 'entity': 'cluster', 'name': None, 'bit': 'r' if method == 'GET' else 'w'}
    entity = ALIAS.get(entity, entity)
    name = 'cluster' if entity == 'cluster' else (args.get('objectname') if generic else args.get('name'))
    last = parts[-1]
    if last.startswith('_'):
        if last in SUFFIX_OVERRIDES:
            return {'kind': 'override', 'entity': entity, 'name': name, 'action': last[1:], 'args': dict(args)}
        if last not in SUFFIX_BITS:
            raise GrammarError(f'{method} {rule}: the action {last} is not in the suffix table')
        bit = SUFFIX_BITS[last]
    else:
        bit = 'r' if method == 'GET' else 'w'
    return {'kind': 'object', 'entity': entity, 'name': name, 'bit': bit}
