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
Which tables are governed, and what a caller may do with a row.

Every governed table carries owners (user ids), usergroups (usergroup ids) and access
(an octal mode stored the way the mode columns store one, rwx at the edge). A row with
NULL in those columns is rootus-owned with the table's default mode. Resolution is the
POSIX one with plural classes: rootus or the admin flag allows; in owners, the owner bits;
else any usergroup of the caller listed on the row, its bits AND the caller's highest
role cap among them; else other. Missing r answers 404, so nothing outside a caller's
scope exists; a missing bit with r present answers 403 and names the bit.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import re
from flask import g, has_request_context, request
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from base.usergroup import ROLE_CAPS

# Governed tables and their default mode when the row says nothing (design section 5).
GOVERNED = {
    'node': '770', 'group': '770', 'bmcsetup': '770', 'redfishsetup': '770', 'profile': '770',
    'osimage': '774', 'biosconfig': '774', 'firmwarecatalog': '774',
    'cluster': '644', 'network': '644', 'route': '644', 'cloud': '644', 'switch': '644',
    'rack': '644', 'otherdevices': '644',
}

# Children carry nothing of their own and follow the parent named here: the parent table
# and the column holding its id. Named, not guessed from column names: biosconfig.nodeid
# and bmcsetup.userid look like parents and are not.
CHILDREN = {
    'nodeinterface': ('node', 'nodeid'), 'nodesecrets': ('node', 'nodeid'),
    'nodeinventory': ('node', 'nodeid'), 'nodeinventorydisk': ('node', 'nodeid'),
    'nodeinventorygpu': ('node', 'nodeid'), 'nodeinventorynic': ('node', 'nodeid'),
    'nodeinventoryfirmware': ('node', 'nodeid'), 'firmwarerequest': ('node', 'nodeid'),
    'groupinterface': ('group', 'groupid'), 'groupsecrets': ('group', 'groupid'),
    'osimagetag': ('osimage', 'osimageid'), 'redfishaccount': ('redfishsetup', 'redfishsetupid'),
    'profilefile': ('profile', 'profileid'), 'rackinventory': ('rack', 'rackid'),
    'switchinterface': ('switch', 'switchid'), 'routemap': ('route', 'routeid'),
    'dns': ('network', 'networkid'),
    'ipaddress': ('tableref', 'tablerefid'), 'monitor': ('tableref', 'tablerefid'),
}

# Rootus only, by name: runtime state, controller-to-controller tables, the identity
# tables, and clustersecrets, which carries a cluster id but is not a child of cluster
# because cluster is readable by everyone and its secrets must not be.
ROOTUS = {
    'clustersecrets', 'controller', 'ha', 'journal', 'hash', 'queue', 'status', 'tracker',
    'reference', 'reservedipaddress', 'ownercache', 'ping',
    'user', 'usergroup', 'usergroupmember', 'usergroupmap',
}

BITS = {'r': 4, 'w': 2, 'x': 1}

# Departments that create their own objects, and what they may create: with a role of
# admin or manager in a usergroup, these; with the usergroup's hardware flag as well,
# nodes into its own groups and the hardware catalogue.
DEPARTMENT_CREATES = {'group', 'osimage', 'profile'}
HARDWARE_CREATES = {'node', 'bmcsetup', 'redfishsetup', 'biosconfig', 'firmwarecatalog'}

# On a node or group a department holds w on, these fields are the cluster's hardware
# and network, changed by rootus and admin only, or by admins and managers of a listed
# usergroup that carries the hardware flag. Everything else on the row is config.
# A derived test asserts every column of node and group is on one of the two lists.
HARDWARE_FIELDS = {
    'node': {'name', 'switchid', 'switchport', 'cloudid', 'bmcsetupid', 'redfishsetupid',
             'biosconfigid', 'setupbmc', 'setupredfish', 'unmanaged_bmc_users', 'tpm_uuid',
             'tpm_pubkey', 'tpm_sha256', 'vendor', 'assettag', 'provision_interface', 'service',
             'status'},
    'group': {'name', 'bmcsetupid', 'redfishsetupid', 'biosconfigid', 'setupbmc', 'setupredfish',
              'unmanaged_bmc_users', 'provision_interface', 'domain'},
}
CONFIG_FIELDS = {
    'node': {'groupid', 'osimageid', 'osimagetagid', 'kerneloptions', 'ipxe_kernel', 'roles', 'scripts',
             'profiles', 'profiles_digest', 'prescript', 'partscript', 'postscript', 'install_mode',
             'disklayout', 'osimage_filter', 'netboot', 'bootmenu', 'provision_method',
             'provision_fallback', 'mounts', 'comment'},
    'group': {'osimageid', 'osimagetagid', 'kerneloptions', 'ipxe_kernel', 'roles', 'scripts', 'profiles',
              'prescript', 'partscript', 'postscript', 'install_mode', 'disklayout', 'osimage_filter',
              'netboot', 'bootmenu', 'provision_method', 'provision_fallback', 'mounts', 'comment'},
}
# Body keys that name another governed object, and the table each names: a write that sets
# one needs r on what it names (design: referencing needs r on the target, w on the holder).
# A derived test holds this to the *id columns of node and group.
REFERENCES = {
    'node': {'group': 'group', 'osimage': 'osimage', 'bmcsetup': 'bmcsetup', 'redfishsetup': 'redfishsetup',
             'biosconfig': 'biosconfig', 'switch': 'switch', 'cloud': 'cloud', 'profiles': 'profile'},
    'group': {'osimage': 'osimage', 'bmcsetup': 'bmcsetup', 'redfishsetup': 'redfishsetup',
              'biosconfig': 'biosconfig', 'profiles': 'profile'},
}

# the same fields as the API names them, for the request body
HARDWARE_KEYS = {
    'node': {'newnodename', 'switch', 'switchport', 'cloud', 'bmcsetup', 'redfishsetup',
             'biosconfig', 'setupbmc', 'setupredfish', 'unmanaged_bmc_users', 'tpm_uuid',
             'tpm_pubkey', 'tpm_sha256', 'vendor', 'assettag', 'provision_interface', 'service',
             'macaddress', 'interfaces'},
    'group': {'newgroupname', 'bmcsetup', 'redfishsetup', 'biosconfig', 'setupbmc', 'setupredfish',
              'unmanaged_bmc_users', 'provision_interface', 'domain', 'interfaces'},
}


class AccessRefused(Exception):
    """
    A check that failed, carrying the code to answer with and the message.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Access():
    """
    This class answers what a caller may do with a governed row, and changes who may.
    """

    def __init__(self):
        self.logger = Log.get_logger()


    # ── modes ──────────────────────────────────────────────────────────────

    def mode_text(self, octal=None, table=None):
        """
        Input - an octal mode as stored ('750'), or None for the table's default
        Output - the nine characters ls shows ('rwxr-x---')
        """
        value = int(str(octal or GOVERNED.get(table, '000')), 8)
        text = ''
        for shift in (6, 3, 0):
            triplet = (value >> shift) & 7
            text += ('r' if triplet & 4 else '-') + ('w' if triplet & 2 else '-') + ('x' if triplet & 1 else '-')
        return text

    def mode_octal(self, text=None):
        """
        Input - nine characters as ls shows them, or three octal digits as chmod takes them
        Output - the octal text stored in the table
        """
        if re.fullmatch(r'[0-7]{3}', str(text or '')):
            return str(text)
        value = 0
        for index, char in enumerate(text):
            if char != '-':
                value |= BITS[char] << (6 - 3 * (index // 3))
        return format(value, 'o').rjust(3, '0')

    def mask(self, text=None):
        """
        Input - three characters such as 'r-x'
        Output - their value 0 to 7
        """
        return sum(BITS[char] for char in text if char != '-')


    # ── the caller ─────────────────────────────────────────────────────────

    def caller(self, userid=None):
        """
        Output - {'id', 'admin', 'usergroups': {usergroupid: role}} for a user id; id 0 is
                 rootus and admin. Cached on the request, so a request reads it once.
        """
        if has_request_context() and getattr(g, 'caller', None) and g.caller['id'] == userid:
            return g.caller
        if userid in (0, '0', None):
            caller = {'id': 0, 'admin': True, 'usergroups': {}, 'hardware': set()}
        else:
            rows = Database().get_record(table='user', where=f"id = '{userid}'")
            if not rows:
                raise AccessRefused(401, f'User {userid} no longer exists')
            if not Helper().make_bool(rows[0]['enabled']):
                raise AccessRefused(401, f"User {rows[0]['username']} is disabled")
            admin = Helper().make_bool(rows[0]['admin']) is True
            usergroups, hardware = {}, set()
            for row in Database().get_record(table='usergroupmember', where=f"userid = '{userid}'") or []:
                usergroups[int(row['usergroupid'])] = row['role']
            leading = [gid for gid, role in usergroups.items() if role in ('admin', 'manager')]
            if leading:
                for row in Database().get_record(table='usergroup', where=f"id IN ({','.join(map(str, leading))}) AND hardware = '1'") or []:
                    hardware.add(int(row['id']))
            caller = {'id': int(userid), 'admin': admin, 'usergroups': usergroups, 'hardware': hardware}
        if has_request_context():
            g.caller = caller
        return caller


    # ── rows and bits ──────────────────────────────────────────────────────

    def row(self, table=None, name=None):
        """
        Output - the governed row, or None. cluster is one row and needs no name.
        """
        if table not in GOVERNED:
            return None
        if table == 'cluster':
            rows = Database().get_record(table='cluster')
        else:
            rows = Database().get_record(table=table, where=f"name = '{name}'")
        return rows[0] if rows else None

    def ids(self, value=None):
        """
        Input - a csv of ids as stored, or None
        Output - a list of ints
        """
        return [int(item) for item in str(value or '').split(',') if item.strip()]

    def bits(self, caller=None, table=None, row=None):
        """
        Output - the three characters the caller effectively holds on the row.
        """
        if caller['admin']:
            return 'rwx'
        mode = int(str(row.get('access') or GOVERNED[table]), 8)
        if caller['id'] in self.ids(row.get('owners')):
            return self._text((mode >> 6) & 7)
        shared = [gid for gid in self.ids(row.get('usergroups')) if gid in caller['usergroups']]
        if shared:
            cap = max(self.mask(ROLE_CAPS[caller['usergroups'][gid]]) for gid in shared)
            return self._text(((mode >> 3) & 7) & cap)
        return self._text(mode & 7)

    def _text(self, triplet):
        return ('r' if triplet & 4 else '-') + ('w' if triplet & 2 else '-') + ('x' if triplet & 1 else '-')

    def class_of(self, caller=None, row=None):
        """
        Output - which class applied, for a refusal message.
        """
        if caller['admin']:
            return 'admin'
        if caller['id'] in self.ids(row.get('owners')):
            return 'owner'
        shared = [gid for gid in self.ids(row.get('usergroups')) if gid in caller['usergroups']]
        if shared:
            names = Database().get_record(table='usergroup', where=f"id IN ({','.join(str(g) for g in shared)})") or []
            return ', '.join(f"{caller['usergroups'][int(n['id'])]} in {n['name']}" for n in names)
        return 'other'

    def allowed(self, userid=None, table=None, name=None, bit=None):
        """
        Process - the bit check on one row. Raises AccessRefused with 404 when the caller
                  may not even see the object, 403 when it may but lacks the bit.
        Output - the row, so the caller need not read it again.
        """
        caller = self.caller(userid)
        row = self.row(table, name)
        if caller['admin']:
            return row
        if row is None:
            raise AccessRefused(404, f'{table} {name} is not available')
        held = self.bits(caller, table, row)
        if 'r' not in held:
            raise AccessRefused(404, f'{table} {name} is not available')
        if bit not in held:
            raise AccessRefused(403, f'{table} {name} requires {bit}; you hold {held} ({self.class_of(caller, row)})')
        return row

    def pushed_object(self, object_type=None, name=None, request_data=None, key=None, column=None, table=None):
        """
        Output - the catalogue object a push or grab aims at: the one the body names under
                 key, else the node's or group's own through column; None when neither.
        """
        try:
            named = request_data['config'][object_type][name].get(key)
        except (KeyError, TypeError, AttributeError):
            named = None
        if named:
            return named
        row = self.row(object_type, name)
        if row and row.get(column):
            return Database().name_by_id(table, row[column])
        return None

    def may_create(self, caller=None, table=None, body=None):
        """
        The create rule. rootus and admin create anything. A department, admins and managers
        of a usergroup, creates group, osimage and profile; with the usergroup's hardware
        flag also nodes into groups that usergroup is listed on with w, on networks the
        caller may read, and the hardware catalogue. Raises AccessRefused otherwise.
        """
        if caller['admin']:
            return
        leading = [gid for gid, role in caller['usergroups'].items() if role in ('admin', 'manager')]
        if table in DEPARTMENT_CREATES and leading:
            return
        if table in HARDWARE_CREATES and caller['hardware']:
            if table == 'node':
                self._node_create_fences(caller, body or {})
            return
        if table in DEPARTMENT_CREATES or table in HARDWARE_CREATES:
            raise AccessRefused(403, f'creating a {table} needs the admin or manager role in a usergroup'
                                + (' with the hardware flag' if table in HARDWARE_CREATES else ''))
        raise AccessRefused(403, f'creating a {table} is for rootus and admin users')

    def _node_create_fences(self, caller, body):
        """
        A department creates nodes only into its own groups, and only with addresses on
        networks it may read: rootus fences by withholding r on a network.
        """
        group = body.get('group')
        if not group:
            raise AccessRefused(403, 'creating a node needs a group the usergroup is listed on')
        row = self.row('group', group)
        if row is None or not (set(self.ids(row.get('usergroups'))) & caller['hardware']) \
                or 'w' not in self.bits(caller, 'group', row):
            raise AccessRefused(403, f'creating a node into group {group} needs w on it through a usergroup with the hardware flag')
        for interface in body.get('interfaces') or []:
            network = interface.get('network') if isinstance(interface, dict) else None
            if network:
                self.allowed(caller['id'], 'network', network, 'r')

    def require_create(self, table=None, body=None):
        """
        The create rule from inside a route, for a second object that does not exist yet.
        Output - (True, None) or (False, message, code)
        """
        caller = self.request_caller()
        if caller is None:
            return True, None
        try:
            self.may_create(caller, table, body)
            return True, None
        except AccessRefused as exp:
            return False, exp.message, exp.code

    def created_row(self, table=None, row=None):
        """
        Input - the row about to be inserted, as make_rows builds it
        Output - the same row carrying the three columns: a node copies its group's; any
                 other object created by a department lists every usergroup in which the
                 creator is admin or manager and names the creator as owner; a rootus or
                 admin create leaves them NULL. Called at every insert into a governed table;
                 the derived test checks that.
        """
        if table not in GOVERNED:
            return row
        columns = {entry['column']: entry['value'] for entry in row}
        if any(columns.get(key) for key in ('owners', 'usergroups', 'access')):
            return row
        caller = self.request_caller()
        values = {}
        if table == 'node' and columns.get('groupid'):
            groups = Database().get_record(table='group', where=f"id = '{columns['groupid']}'")
            if groups:
                values = {key: groups[0].get(key) for key in ('owners', 'usergroups', 'access')}
        elif caller is not None and not caller['admin']:
            leading = [gid for gid, role in caller['usergroups'].items() if role in ('admin', 'manager')]
            values = {'owners': str(caller['id']), 'usergroups': ','.join(str(gid) for gid in leading)}
        for key, value in values.items():
            if value:
                row = [entry for entry in row if entry['column'] != key] + [{'column': key, 'value': value}]
        return row

    def hardware_allowed(self, caller=None, row=None):
        """
        Whether the caller may touch the hardware fields of this node or group: rootus, admin,
        or a leading role in a listed usergroup with the hardware flag.
        """
        return caller['admin'] or bool(set(self.ids(row.get('usergroups'))) & caller['hardware'])

    def require(self, table=None, name=None, bit=None):
        """
        The same check from inside a route or a base class, for a second object the body
        names. Outside a request, as when the journal replays, there is nobody to refuse.
        Output - (True, row) or (False, message, code)
        """
        if not has_request_context() or getattr(g, 'userid', None) is None:
            return True, None
        if name is None:
            return False, f'Invalid request: no {table} named', 400
        try:
            return True, self.allowed(g.userid, table, name, bit)
        except AccessRefused as exp:
            return False, exp.message, exp.code


    # ── what a caller may see, for the list and show paths ──────────────────

    def request_caller(self):
        """
        Output - the caller of the current request, or None outside a request (a journal
                 replay, housekeeping, a test calling a base class directly).
        """
        if not has_request_context() or getattr(g, 'userid', None) is None:
            return None
        return self.caller(g.userid)

    def admin_caller(self):
        """
        Output - True when there is nobody to hide anything from: no request, rootus, admin.
        """
        caller = self.request_caller()
        return caller is None or caller['admin']

    def visible(self, table=None, records=None):
        """
        Input - rows of a governed table as fetched, carrying name and the three columns
        Output - the rows the caller may read, with owners and usergroups as names and access
                 as rwx text. Every row when there is nobody to hide from. Called by every
                 list and show over the rows it already holds; the derived test checks that.
        """
        records = records or []
        caller = self.request_caller()
        if caller is None or caller['admin']:
            kept = list(records)
        else:
            kept = [row for row in records if 'r' in self.bits(caller, table, row)]
        self._render(table, kept)
        return kept

    def visible_names(self, table=None, names=None):
        """
        Input - names of rows of a governed table, from a join or a child listing
        Output - those the caller may read, in the same order; one read of the table.
                 A table that is not governed is for rootus and admin only.
        """
        names = list(names or [])
        caller = self.request_caller()
        if caller is None or caller['admin']:
            return names
        if table not in GOVERNED:
            return []
        rows = {row['name']: row for row in Database().get_record(
            select=['name', 'owners', 'usergroups', 'access'], table=table) or []}
        return [name for name in names if name in rows and 'r' in self.bits(caller, table, rows[name])]

    def _render(self, table=None, rows=None):
        """
        Replace the stored ids and octal with names and rwx, in place, with two lookups for
        the whole listing rather than two per row.
        """
        owner_ids, group_ids = set(), set()
        for row in rows:
            owner_ids.update(self.ids(row.get('owners')))
            group_ids.update(self.ids(row.get('usergroups')))
        owners = {int(r['id']): r['username'] for r in (Database().get_record(
            table='user', where=f"id IN ({','.join(map(str, owner_ids))})") if owner_ids else [])}
        groups = {int(r['id']): r['name'] for r in (Database().get_record(
            table='usergroup', where=f"id IN ({','.join(map(str, group_ids))})") if group_ids else [])}
        for row in rows:
            row['access'] = self.mode_text(row.get('access'), table)
            row['owners'] = [owners.get(i, str(i)) for i in self.ids(row.get('owners'))] or ['rootus']
            row['usergroups'] = [groups.get(i, str(i)) for i in self.ids(row.get('usergroups'))]


    # ── the check the decorators run ───────────────────────────────────────

    def check(self, userid=None, requirement=None):
        """
        Input - the caller's id and what the route requires, from the grammar
        Output - (True, None, None) or (False, code, message)
        """
        if requirement is None:
            return False, 403, 'This route declares no requirement'
        kind = requirement['kind']
        try:
            if kind in ('open', 'self'):
                return True, None, None
            caller = self.caller(userid)
            if kind == 'provision':
                # a node's own token never gets here; a person asking for a node's install
                # script is reprovisioning it and receives its token, which is x. The role,
                # profile and script feeds are for nodes, not people.
                if requirement.get('name') is not None:
                    self.allowed(userid, 'node', requirement['name'], 'x')
                elif not caller['admin']:
                    raise AccessRefused(403, f"{requirement.get('entity')} boot content is for nodes, rootus and admin users")
                return True, None, None
            if kind == 'rootus':
                if not caller['admin']:
                    raise AccessRefused(403, f"{requirement.get('entity')} is for rootus and admin users")
                return True, None, None
            if kind == 'membership':
                self._membership(caller, requirement.get('name'))
                return True, None, None
            if kind == 'object':
                if requirement.get('name') is None:
                    return True, None, None
                entity, name, bit = requirement['entity'], requirement['name'], requirement['bit']
                if not caller['admin'] and bit == 'w' and self.row(entity, name) is None:
                    self.may_create(caller, entity, self._body_of(entity, name))
                    self._references(caller, entity, self._body_of(entity, name))
                    return True, None, None
                row = self.allowed(userid, entity, name, bit)
                if bit == 'w' and row is not None:
                    self._deletes(caller, entity, name, row)
                    if entity in HARDWARE_FIELDS:
                        self._hardware(caller, entity, name, row)
                    self._references(caller, entity, self._body_of(entity, name))
                return True, None, None
            if kind == 'dynamic':
                bit = 'r' if 'status' in str(requirement.get('action')) else 'x'
                if requirement.get('name') is None:
                    self._hostlist(userid, caller, bit, control=True)
                    return True, None, None
                self.allowed(userid, 'node', requirement['name'], bit)
                return True, None, None
            if kind == 'override':
                self._override(userid, caller, requirement)
                return True, None, None
        except AccessRefused as exp:
            return False, exp.code, exp.message
        return False, 403, f'unknown requirement kind {kind}'

    def _override(self, userid, caller, requirement):
        """
        The primary object of a two-object action; the second is checked where the body
        is known. clone and create stay with rootus and admin until the create rules land.
        """
        action = requirement['action']
        entity, name, args = requirement['entity'], requirement.get('name'), requirement.get('args', {})
        if action == 'clone':
            self.allowed(userid, entity, name, 'r')
            self.may_create(caller, entity, self._body_of(entity, name))
        elif action in ('ospush', 'osgrab', 'biospush', 'biosgrab', 'firmwarepush', 'redfish', 'provision'):
            if name is None:
                self._hostlist(userid, caller, 'x')
            else:
                self.allowed(userid, entity, name, 'x')
        elif action in ('couple', 'decouple'):
            self.allowed(userid, entity, name, 'r')
            self.allowed(userid, args.get('tableref'), args.get('target'), 'w')
        elif action in ('chmod', 'chgrp', 'chown'):
            self.allowed(userid, args.get('entity', entity), name, 'r')
        else:
            raise AccessRefused(403, f'{action} has no rule')


    def _body_of(self, entity, name):
        """
        The request body for one object, config.<entity>.<name>, or an empty dict.
        """
        try:
            body = request.get_json(force=True, silent=True) or {}
            return body['config'][entity][name] or {}
        except (KeyError, TypeError, AttributeError):
            return {}

    def _hardware(self, caller, entity, name, row):
        """
        A write to a node or group that names a hardware field, or writes its interfaces,
        needs the hardware axis: refused for anyone else, naming the field.
        """
        if self.hardware_allowed(caller, row):
            return
        rule = request.url_rule.rule if request.url_rule else ''
        if '/interfaces' in rule:
            raise AccessRefused(403, f'{entity} {name}: interfaces are hardware, for rootus, admin or a usergroup with the hardware flag')
        named = sorted(set(self._body_of(entity, name)) & HARDWARE_KEYS[entity])
        if named:
            raise AccessRefused(403, f"{entity} {name}: {', '.join(named)} is hardware, for rootus, admin or a usergroup with the hardware flag")

    def _deletes(self, caller, entity, name, row):
        """
        Removing follows creating. A node, an interface, a hardware catalogue object or one of
        its accounts needs the hardware axis, not only w; infrastructure (network, switch, rack,
        cloud, route, otherdevices) stays with rootus and admin; a department object goes with w.
        """
        rule = request.url_rule.rule if request.url_rule else ''
        if not rule.endswith('/_delete') or caller['admin']:
            return
        what = f'an interface of {entity} {name}' if '/interfaces/' in rule else f'{entity} {name}'
        if entity in HARDWARE_CREATES or '/interfaces/' in rule:
            if not self.hardware_allowed(caller, row):
                raise AccessRefused(403, f'removing {what} needs the admin or manager role in a usergroup with the hardware flag')
        elif entity not in DEPARTMENT_CREATES:
            raise AccessRefused(403, f'removing {what} is for rootus and admin users')

    def _references(self, caller, entity, body):
        """
        Every governed object the body names must be readable by the caller: a node goes
        into a group one may see, a group takes an osimage one may see. Unreadable answers
        as not available, the same as a show would.
        """
        if caller['admin']:
            return
        for key, table in REFERENCES.get(entity, {}).items():
            # profiles travel comma or space separated, the way the node base reads them
            for name in str(body.get(key) or '').replace(' ', ',').split(','):
                name = name.strip().lstrip('+-')
                if name:
                    self.allowed(caller['id'], table, name, 'r')

    def _membership(self, caller, usergroup):
        """
        The members path: rootus and admin anywhere; the admin role in that usergroup.
        """
        if caller['admin']:
            return
        rows = Database().get_record(table='usergroup', where=f"name = '{usergroup}'")
        if rows and caller['usergroups'].get(int(rows[0]['id'])) == 'admin':
            return
        raise AccessRefused(403, f'the members of usergroup {usergroup} are managed by its admins, rootus and admin users')

    def _hostlist(self, userid, caller, bit, control=False):
        """
        A hostlist or group-wide action names its nodes in the body: under
        control.<subsystem>.<action>.hostlist, or config.node.hostlist and config.node.group.
        Every node named needs the bit; refused whole, naming the nodes that were refused.
        """
        if caller['admin']:
            return
        try:
            body = request.get_json(force=True, silent=True) or {}
        except Exception:
            body = {}
        raw_hosts, group = None, None
        try:
            if control:
                subsystem = list(body['control'].keys())[0]
                action = list(body['control'][subsystem].keys())[0]
                raw_hosts = body['control'][subsystem][action].get('hostlist')
            else:
                raw_hosts = body['config']['node'].get('hostlist')
                group = body['config']['node'].get('group')
        except (KeyError, IndexError, AttributeError, TypeError):
            raw_hosts = None
        names = list(Helper().get_hostlist(raw_hosts) or []) if raw_hosts else []
        if group:
            names += [row['name'] for row in Database().get_record_join(
                ['node.name'], ['node.groupid=group.id'], [f"`group`.name='{group}'"]) or []]
        if not names:
            return
        refused = []
        for name in names:
            try:
                self.allowed(userid, 'node', name, bit)
            except AccessRefused as exp:
                refused.append(f'{name} ({exp.message})')
        if refused:
            raise AccessRefused(403, f"refused for {len(refused)} of {len(names)} nodes: {'; '.join(refused)}")


    # ── who may change who may ─────────────────────────────────────────────

    def annotate(self, table=None, row=None):
        """
        Output - owners and usergroups as names, access as rwx, for a response.
        """
        owners = self.ids(row.get('owners'))
        usergroups = self.ids(row.get('usergroups'))
        names_o = {int(r['id']): r['username'] for r in (Database().get_record(table='user', where=f"id IN ({','.join(map(str, owners))})") if owners else [])}
        names_g = {int(r['id']): r['name'] for r in (Database().get_record(table='usergroup', where=f"id IN ({','.join(map(str, usergroups))})") if usergroups else [])}
        return {'owners': [names_o.get(i, str(i)) for i in owners] or ['rootus'],
                'usergroups': [names_g.get(i, str(i)) for i in usergroups],
                'access': self.mode_text(row.get('access'), table)}

    def _edit_list(self, current, wanted, lookup):
        """
        Input - the stored ids, the request's names (a list or csv, +name adds, -name removes,
                a bare name replaces the whole list), and a name-to-id resolver
        Output - the new id list, or raises AccessRefused 400 for an unknown name
        """
        names = wanted if isinstance(wanted, list) else [n.strip() for n in str(wanted or '').split(',') if n.strip()]
        result = list(current)
        replace = [n for n in names if not n.startswith(('+', '-'))]
        if replace:
            result = []
        for entry in names:
            name = entry.lstrip('+-')
            ident = lookup(name)
            if ident is None:
                raise AccessRefused(400, f'Invalid request: {name} is not known')
            if entry.startswith('-'):
                result = [i for i in result if i != ident]
            elif ident not in result:
                result.append(ident)
        return result

    def _userid(self, name):
        if name == 'rootus':
            return 0
        rows = Database().get_record(table='user', where=f"username = '{name}'")
        return int(rows[0]['id']) if rows else None

    def _usergroupid(self, name):
        rows = Database().get_record(table='usergroup', where=f"name = '{name}'")
        return int(rows[0]['id']) if rows else None

    def forget_user(self, userid=None):
        """
        A deleted user leaves no ownership behind: its id goes out of the owners of every
        governed row, so nothing answers to that id later.
        """
        for table in GOVERNED:
            for row in Database().get_record(select=['id', 'owners'], table=table,
                                             where="owners IS NOT NULL AND owners != ''") or []:
                owners = self.ids(row['owners'])
                if int(userid) in owners:
                    remaining = ','.join(str(i) for i in owners if i != int(userid))
                    self._store(table, row, 'owners', remaining or None)

    def _admin_of_listed(self, caller, row):
        return any(caller['usergroups'].get(gid) == 'admin' for gid in self.ids(row.get('usergroups')))

    def _store(self, table, row, column, value):
        Database().update(table, Helper().make_rows({column: value}), [{'column': 'id', 'value': row['id']}])

    def chmod(self, table=None, name=None, request_data=None, userid=None, dry=False):
        """
        owners, usergroup admins on objects their usergroup is listed on, rootus and admin.
        """
        try:
            body = request_data['config'][table][name]
            text = body['access']
        except (KeyError, TypeError):
            return False, 'Invalid request: access is needed'
        caller = self.caller(userid)
        row = self.row(table, name)
        if row is None:
            return False, f'{table} {name} is not available'
        may = caller['admin'] or caller['id'] in self.ids(row.get('owners')) or self._admin_of_listed(caller, row)
        if not may:
            raise AccessRefused(403, f'{table} {name}: chmod is for owners, usergroup admins, rootus and admin users')
        if not dry:
            self._store(table, row, 'access', self.mode_octal(text))
        return True, f'{table} {name} access updated to {text}.'

    def chgrp(self, table=None, name=None, request_data=None, userid=None, dry=False):
        """
        Adding a usergroup needs membership of it, in any role, whoever asks: an object
        does not leave the organisation without a superuser. Owners and usergroup admins
        on listed objects may remove. rootus and admin anywhere.
        """
        try:
            wanted = request_data['config'][table][name]['usergroups']
        except (KeyError, TypeError):
            return False, 'Invalid request: usergroups is needed'
        caller = self.caller(userid)
        row = self.row(table, name)
        if row is None:
            return False, f'{table} {name} is not available'
        current = self.ids(row.get('usergroups'))
        new = self._edit_list(current, wanted, self._usergroupid)
        if not caller['admin']:
            full = caller['id'] in self.ids(row.get('owners')) or self._admin_of_listed(caller, row)
            removed = [gid for gid in current if gid not in new]
            added = [gid for gid in new if gid not in current]
            if removed and not full:
                raise AccessRefused(403, f'{table} {name}: removing a usergroup is for owners, usergroup admins, rootus and admin users')
            foreign = [gid for gid in added if gid not in caller['usergroups']]
            if foreign:
                raise AccessRefused(403, f'{table} {name}: you may only add usergroups you are a member of')
        if not dry:
            self._store(table, row, 'usergroups', ','.join(str(i) for i in new))
        return True, f'{table} {name} usergroups updated.'

    def chown(self, table=None, name=None, request_data=None, userid=None, dry=False):
        """
        rootus and admin anywhere; usergroup admins on listed objects, only to members of
        that usergroup, so ownership cannot leave the organisation without a superuser.
        """
        try:
            wanted = request_data['config'][table][name]['owners']
        except (KeyError, TypeError):
            return False, 'Invalid request: owners is needed'
        caller = self.caller(userid)
        row = self.row(table, name)
        if row is None:
            return False, f'{table} {name} is not available'
        current = self.ids(row.get('owners'))
        new = [i for i in self._edit_list(current, wanted, self._userid) if i != 0]
        if not caller['admin']:
            if not self._admin_of_listed(caller, row):
                raise AccessRefused(403, f'{table} {name}: chown is for usergroup admins on listed objects, rootus and admin users')
            listed = [gid for gid in self.ids(row.get('usergroups')) if caller['usergroups'].get(gid) == 'admin']
            for owner in new:
                if owner not in current and not self._member_of_any(owner, listed):
                    raise AccessRefused(403, f'{table} {name}: a usergroup admin may only chown to members of that usergroup')
        if not dry:
            self._store(table, row, 'owners', ','.join(str(i) for i in new))
        return True, f'{table} {name} owners updated.'

    def _member_of_any(self, userid, usergroupids):
        if not usergroupids:
            return False
        rows = Database().get_record(table='usergroupmember',
                                     where=f"userid = '{userid}' AND usergroupid IN ({','.join(map(str, usergroupids))})")
        return bool(rows)
