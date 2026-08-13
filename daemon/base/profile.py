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
Profile class handles all profile related operations.

A profile is a named bundle of files plus a service with an action, assigned to
groups and nodes. Profiles stack: a node applies its group's profiles plus its
own, additively. File contents travel base64 over the API and are stored through
the same encryption path as secrets.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import hashlib
from json import dumps
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.queue import Queue


class Profile():
    """
    This class is responsible for all operations for profiles.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def is_enabled(self, profile):
        """
        A profile with no enabled value is enabled. The column arrives NULL on every row
        that predates it, and reading that as disabled would freeze every existing profile
        the moment the daemon is upgraded - silently, since freezing changes nothing on a
        node and simply stops the cluster converging.
        """
        return profile['enabled'] is None or Helper().make_bool(profile['enabled'])


    def _profile_with_files(self, profile):
        """One profile row plus its files, in response shape."""
        detail = {
            'scope': profile['scope'] or 'static',
            'service': profile['service'],
            'action': profile['action'] or 'none',
            'enabled': self.is_enabled(profile),
            'files': []
        }
        where = f'profileid = "{profile["id"]}"'
        for record in Database().get_record(table='profilefile', where=where) or []:
            del record['id']
            del record['profileid']
            record['content'] = Helper().decrypt_string(record['content'])
            detail['files'].append(record)
        return detail


    def get_all_profiles(self):
        """
        This method will return all profiles in detailed format.
        """
        status=False
        profiles = Database().get_record(table='profile')
        if profiles:
            response = {'config': {'profiles': {} }}
            for profile in profiles:
                response['config']['profiles'][profile['name']] = self._profile_with_files(profile)
            status=True
        else:
            self.logger.warning('no profiles available')
            response = 'No profiles available'
            status=False
        return status, response


    def get_profile(self, name=None):
        """
        This method will return a requested profile in detailed format.
        """
        status=False
        profile = Database().get_record(table='profile', where=f'name = "{name}"')
        if profile:
            response = {'config': {'profiles': {name: self._profile_with_files(profile[0])} }}
            status=True
        else:
            response = f'Profile {name} is not available'
            status=False
        return status, response


    def update_profile(self, name=None, request_data=None):
        """
        This method will create or update a profile and its files.
        Files present in the request are created or updated by name; files not
        named are left as they are - removal goes through delete_profile_file.
        """
        status=False
        response="Internal error"
        unresolvable = []
        if request_data:
            data = request_data['config']['profiles'][name]
            files = data.pop('files', None)
            profile = Database().get_record(table='profile', where=f'name = "{name}"')
            profile_columns = Database().get_columns('profile')
            column_check = Helper().compare_list(data, profile_columns)
            if not column_check:
                return False, 'Invalid request: Supplied columns do not match the requirements'
            if profile:
                profileid = profile[0]['id']
                if data:
                    where = [{"column": "id", "value": profileid}]
                    row = Helper().make_rows(data)
                    Database().update('profile', row, where)
                response = f'Profile {name} updated'
            else:
                data['name'] = name
                row = Helper().make_rows(data)
                profileid = Database().insert('profile', row)
                if not profileid:
                    response = f'Internal error: profile {name} create failed'
                    self.logger.error(response)
                    return False, response
                response = f'Profile {name} created'
            status=True
            if files:
                file_columns = Database().get_columns('profilefile')
                for entry in files:
                    if 'name' not in entry.keys():
                        return False, 'Invalid request: file information not complete, name is required'
                    if not Helper().compare_list(entry, file_columns):
                        return False, 'Invalid request: Supplied file columns do not match the requirements'
                    if entry.get('owner') and not Helper().check_owner(entry['owner']):
                        unresolvable.append(f"{entry['name']}: {entry['owner']}")
                    file_name = entry['name']
                    where = f'profileid = "{profileid}" AND name = "{file_name}"'
                    existing = Database().get_record(table='profilefile', where=where)
                    # a change carries only what is changing: 'give this file mode 600'
                    # says nothing about its content, and demanding one would make the
                    # caller send the content back to leave it alone
                    if not existing:
                        for item in ['content', 'path']:
                            if not entry.get(item):
                                return False, f'Invalid request: file information not complete, {item} is required'
                    if 'content' in entry:
                        entry['content'] = Helper().encrypt_string(entry['content'])
                    if existing:
                        where = [
                            {"column": "profileid", "value": profileid},
                            {"column": "name", "value": file_name}
                        ]
                        row = Helper().make_rows(entry)
                        Database().update('profilefile', row, where)
                    else:
                        entry['profileid'] = profileid
                        row = Helper().make_rows(entry)
                        Database().insert('profilefile', row)
            if status is True and unresolvable:
                response += '. Warning: owner not currently resolvable (a numeric uid:gid works without a directory): ' + ', '.join(unresolvable)
            if status is True:
                self.queue_profile(name)
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def clone_profile(self, name=None, request_data=None):
        """
        This method will clone a requested profile including its files.
        """
        status=False
        response="Internal error"
        if request_data:
            data = request_data['config']['profiles'][name]
            profile = Database().get_record(table='profile', where=f'name = "{name}"')
            if profile:
                if 'newprofilename' in data:
                    newname = data['newprofilename']
                    existing = Database().get_record(table='profile', where=f'name = "{newname}"')
                    if existing:
                        response = f'Invalid request: Profile {newname} already present'
                        status=False
                    else:
                        profileid = profile[0]['id']
                        newprofile = dict(profile[0])
                        del newprofile['id']
                        newprofile['name'] = newname
                        row = Helper().make_rows(newprofile)
                        new_profileid = Database().insert('profile', row)
                        where = f'profileid = "{profileid}"'
                        for record in Database().get_record(table='profilefile', where=where) or []:
                            del record['id']
                            record['profileid'] = new_profileid
                            row = Helper().make_rows(record)
                            Database().insert('profilefile', row)
                        response = f'Profile {name} cloned to {newname}'
                        status=True
                else:
                    response = 'Invalid request: New profile name not provided'
                    status=False
            else:
                response = f'Profile {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_profile(self, name=None):
        """
        This method will delete a requested profile and its files.
        """
        status=False
        profile = Database().get_record(table='profile', where=f'name = "{name}"')
        if profile:
            profileid = profile[0]['id']
            # in use means still assigned somewhere, exactly as an osimage is guarded.
            # unassigning first is not busywork: it is what puts the files back on the
            # nodes, and it happens while the profile still exists to say what to undo
            inuse = self.assigned_to(name)
            if inuse:
                listed = ', '.join(inuse[:10])
                more = ' ...' if len(inuse) > 10 else ''
                return False, (f'Invalid request: profile {name} is currently applied by '
                               f'{listed}{more}. Remove it from them first')
            Database().delete_row('profilefile', [{"column": "profileid", "value": profileid}])
            Database().delete_row('profile', [{"column": "id", "value": profileid}])
            response = f'Profile {name} removed'
            status=True
        else:
            response = f'Profile {name} is not available'
            status=False
        return status, response


    def delete_profile_file(self, name=None, filename=None):
        """
        This method will delete one file of a profile.
        """
        status=False
        profile = Database().get_record(table='profile', where=f'name = "{name}"')
        if profile:
            profileid = profile[0]['id']
            where = f'profileid = "{profileid}" AND name = "{filename}"'
            existing = Database().get_record(table='profilefile', where=where)
            if existing:
                where = [
                    {"column": "profileid", "value": profileid},
                    {"column": "name", "value": filename}
                ]
                Database().delete_row('profilefile', where)
                self.queue_profile(name)
                response = f'File {filename} deleted from profile {name}'
                status=True
            else:
                response = f'File {filename} is unavailable for profile {name}'
                status=False
        else:
            response = f'Profile {name} is not available'
            status=False
        return status, response


    def merged_profiles(self, nodeid=None):
        """
        The profiles a node applies: its group's plus its own, additively and
        deduplicated, group first. Profiles stack - this is deliberately not the
        inheritance-resolved single value that roles use.
        """
        merged = []
        rows = Database().get_record_join(
            ['group.profiles as group_profiles', 'node.profiles as node_profiles'],
            ['group.id=node.groupid'], [f"node.id='{nodeid}'"])
        if not rows:
            rows = Database().get_record(table='node', where=f'id = "{nodeid}"')
            if rows:
                rows = [{'group_profiles': None, 'node_profiles': rows[0]['profiles']}]
        for row in rows or []:
            for scoped in [row['group_profiles'], row['node_profiles']]:
                for entry in (scoped or "").split(','):
                    entry = entry.strip()
                    if entry and entry not in merged:
                        merged.append(entry)
        return ','.join(merged)


    def _boot_detail(self, profile):
        """A profile in apply-ready shape: files with content, defaults filled in,
        owners resolved to numbers on the controller since the applying side (the
        installer's chroot) cannot resolve directory users."""
        detail = self._profile_with_files(profile)
        for record in detail['files']:
            record['owner'] = record['owner'] or 'root:root'
            record['mode'] = record['mode'] or '644'
            record['resolved_owner'] = Helper().resolve_owner(record['owner'])
        detail['service'] = detail['service'] or ''
        return detail


    def get_boot_profile(self, name=None):
        """
        This method returns what a node needs to apply one profile at install time.
        """
        status=False
        profile = Database().get_record(table='profile', where=f'name = "{name}"')
        if profile:
            response = {'profile': {name: self._boot_detail(profile[0])}}
            status=True
        else:
            response = f'Profile {name} is not available'
            status=False
        return status, response


    def queue_node(self, name=None):
        """
        Ask for a node to be brought into line. Identical requests collapse: the queue
        returns the existing task for the same task+param inside its own window, so a
        change touching one node five times is one delivery.
        """
        if not name:
            return False
        Queue().add_task_to_queue(task='sync_profiles', param=name, subsystem='profile')
        return True


    def queue_nodes(self, names=None):
        """The same, for a group's worth of nodes."""
        for name in names or []:
            self.queue_node(name)
        return True


    def queue_group(self, name=None):
        """Every node in a group, by group name."""
        nodes = Database().get_record_join(['node.name as nodename'], ['group.id=node.groupid'],
                                           [f'`group`.name="{name}"'])
        return self.queue_nodes([node['nodename'] for node in nodes or []])


    def assigned_to(self, name=None):
        """
        Everything that still applies a profile: the groups naming it and the nodes
        naming it themselves. Matching is done on the split list rather than in SQL so
        a name can never be matched as part of a longer one.
        """
        status, response = self.get_profile_member(name)
        if not status:
            return []
        members = response['config']['profiles'][name]['members']
        return members['groups'] + members['nodes']


    def get_profile_member(self, name=None):
        """
        Who applies this profile: the groups that name it, and the nodes that name it
        themselves. The same question the deletion guard asks, answered for a human -
        an operator who cannot delete a profile should be able to see what is holding it.
        """
        status=False
        profile = Database().get_record(table='profile', where=f'name = "{name}"')
        if not profile:
            return status, f'Profile {name} is not available'
        members = {'groups': [], 'nodes': []}
        for table, key in (('group', 'groups'), ('node', 'nodes')):
            for row in Database().get_record(table=table) or []:
                assigned = [entry.strip() for entry in (row['profiles'] or '').split(',')]
                if name in assigned:
                    members[key].append(row['name'])
        # a node inside a group that applies it is covered by the group, and listing it
        # again would suggest an assignment it does not have
        response = {'config': {'profiles': {name: {'members': members}} }}
        status=True
        return status, response


    def queue_profile(self, name=None):
        """
        Every node that applies a profile, by profile name. Assignment is a comma list on
        the node and on its group, so the match is done on the merged set rather than in
        SQL - the list is small and this cannot get the boundaries wrong ('gpu' must not
        match 'gpu-extra').
        """
        nodes = Database().get_record_join(['node.name as nodename', 'node.id as nodeid'],
                                           ['group.id=node.groupid'])
        if not nodes:
            nodes = [{'nodename': node['name'], 'nodeid': node['id']}
                     for node in Database().get_record(table='node') or []]
        for node in nodes or []:
            merged = self.merged_profiles(node['nodeid'])
            if name in (merged.split(',') if merged else []):
                self.queue_node(node['nodename'])
        return True


    def node_payload(self, name=None):
        """
        Everything a node needs to bring itself into line, in three states:

          enabled + assigned   full detail, the node manages these
          disabled + assigned  name only, the node freezes what it already has for them
          neither              absent, so the node reverts whatever it still holds

        A disabled profile has to travel as a name rather than vanish: the applier reclaims
        a path by finding it in its manifest and not in the payload, so silence would revert
        exactly the files that disabling is supposed to leave alone.
        """
        status=False
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return False, f'Node {name} is not available'
        payload = {'node': name, 'profiles': [], 'frozen': []}
        merged = self.merged_profiles(node[0]['id'])
        for profile_name in merged.split(',') if merged else []:
            profile = Database().get_record(table='profile', where=f'name = "{profile_name}"')
            if not profile:
                # assigned but since deleted: the rest still applies, and this one's files
                # are reclaimed like any other removal
                self.logger.warning(f"profile {profile_name} is assigned to {name} but does not exist")
                continue
            if self.is_enabled(profile[0]):
                detail = self._boot_detail(profile[0])
                detail['name'] = profile_name
                payload['profiles'].append(detail)
            else:
                payload['frozen'].append(profile_name)
            status=True
        return status, payload


    def node_digest(self, name=None):
        """
        A stable fingerprint of what a node's profiles should be. Two rules give the
        disabled state the behaviour it is supposed to have:

          * a disabled profile contributes its NAME ONLY, so editing it moves nothing and
            triggers no delivery at all;
          * the flag itself is part of the fingerprint, so flipping it does move the digest
            and the node gets told once - which is what stops a later sweep reclaiming the
            paths it is now meant to leave alone.

        Order is significant and preserved: it decides which profile wins a shared path.
        """
        status, payload = self.node_payload(name)
        if not status:
            return None
        material = {
            'profiles': [
                {
                    'name': profile['name'],
                    'service': profile['service'],
                    'action': profile['action'],
                    'files': [
                        {
                            'name': entry['name'],
                            'path': entry['path'],
                            'owner': entry['owner'],
                            'mode': entry['mode'],
                            'content': hashlib.sha256(
                                (entry['content'] or '').encode()).hexdigest(),
                        }
                        for entry in profile['files']
                    ],
                }
                for profile in payload['profiles']
            ],
            'frozen': payload['frozen'],
        }
        return hashlib.sha256(
            dumps(material, sort_keys=False, separators=(',', ':')).encode()).hexdigest()


    def get_node_profiles(self, name=None):
        """
        This method returns every profile a node applies - its group's plus its
        own, stacked - in apply-ready shape, fetched by node name. This is the
        one call a node needs to apply its profiles without knowing their names.
        """
        status=False
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            response = {'config': {'profiles': {} }}
            merged = self.merged_profiles(node[0]['id'])
            for profile_name in merged.split(',') if merged else []:
                profile = Database().get_record(table='profile', where=f'name = "{profile_name}"')
                if profile:
                    response['config']['profiles'][profile_name] = self._boot_detail(profile[0])
                else:
                    # assigned but since deleted: apply the rest, say so loudly
                    self.logger.warning(f"profile {profile_name} is assigned to {name} but does not exist")
            if response['config']['profiles']:
                status=True
            else:
                response = f'No profiles available for node {name}'
                status=False
        else:
            response = f'Node {name} is not available'
            status=False
        return status, response
