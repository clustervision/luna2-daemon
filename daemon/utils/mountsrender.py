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
What the mounts documents mean for a machine, and the files that follow from it,
in the shape of the dhcp and dns renderers: the rows are computed here, the two
templates lay out the text, and this module writes, reloads and mounts.

The controller renders its exports from every document and its fstab from the
cluster document. A booting node gets its fstab block, the exports it serves and
its mountpoints rendered for the address it boots from, and the install template
writes them into the image root.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import grp
import pwd
import json
import socket
import subprocess
from base64 import b64encode
from jinja2 import Environment, FileSystemLoader
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.controller import Controller
from utils.mounts import (entries_from_b64, mount_type, serves, mounts, resolve_server,
                          client_specs, known_servers, RESERVED_SERVERS)

EXPORTS_FILE = '/etc/exports.d/luna.exports'
FSTAB_FILE = '/etc/fstab'
FSTAB_BEGIN = '# BEGIN luna mounts'
FSTAB_END = '# END luna mounts'
COMMAND_TIMEOUT = 60
PROC_MOUNTS = '/proc/mounts'

# the fstab type per document type. manual has no line: it is a mountpoint only
FSTYPES = {'nfs': 'nfs', 'lustre': 'lustre', 'beegfs': 'beegfs', 'gpfs': 'gpfs', 'panfs': 'panfs'}
# the types whose device carries a path, and where that path defaults to the mountpoint
PATH_DEFAULTS_TO_MOUNTPOINT = {'nfs', 'lustre'}
# a directory on one of these is never exported: re-exporting a network filesystem is
# unsupported, and an nfs one deadlocks mountd against the server it is a client of
NETWORK_FSTYPES = {'nfs', 'nfs4'} | set(FSTYPES.values())


def exported_path(entry):
    return entry.get('source') or entry['path']


def network_mountpoints():
    """The mountpoints on this machine that sit on a network filesystem."""
    try:
        with open(PROC_MOUNTS, 'r', encoding='utf-8') as handle:
            rows = [line.split() for line in handle]
    except OSError:
        return set()
    return {row[1] for row in rows if len(row) > 2 and row[2] in NETWORK_FSTYPES}


def on_network_filesystem(path, mountpoints):
    """Whether path is, or lies under, one of the mountpoints."""
    path = path.rstrip('/') or '/'
    return any(path == mp or path.startswith(mp.rstrip('/') + '/') for mp in mountpoints)


def device(entry, server):
    """The fstab device column: the resolved server alone, or server:source where
    a path applies."""
    source = entry.get('source')
    if mount_type(entry) in PATH_DEFAULTS_TO_MOUNTPOINT:
        source = source or entry['path']
    return f'{server}:{source}' if source else server


def fstab_rows(entries, addresses):
    """The rows the fstab template lays out and the mountpoints beside them, for
    the entries a machine mounts. An absent entry contributes to neither: its line
    is exactly what must not be there."""
    rows, dirs = [], []
    for entry in entries:
        if entry.get('state') == 'absent':
            continue
        dirs.append((entry['path'], entry.get('owner') or '-', entry.get('group') or '-',
                     entry.get('mode') or '-'))
        fstype = FSTYPES.get(mount_type(entry))
        if fstype:
            rows.append({'device': device(entry, resolve_server(entry.get('server'), addresses)),
                         'path': entry['path'], 'fstype': fstype,
                         'options': entry.get('options') or 'defaults'})
    return rows, dirs


def export_rows(entries, networks, logger=None):
    """The rows the exports template lays out: the directory and one client
    specification per client, each carrying the export's default options followed
    by its own. A block naming no client exports to nobody, and says so rather
    than to everybody."""
    rows = []
    for entry in entries:
        export = entry.get('export') or {}
        clients = []
        for client in export.get('clients') or []:
            options = ','.join(part for part in (export.get('options'), client.get('options')) if part)
            for spec in client_specs(client['to'], networks):
                clients.append(f'{spec}({options})' if options else spec)
        if clients:
            rows.append({'path': exported_path(entry), 'clients': clients})
        elif logger:
            logger.warning(f"export {exported_path(entry)} names no client and renders nothing")
    return rows


def export_clashes(documents):
    """The same directory on the same server exported by two documents with two
    different blocks. documents is [(origin, entries)]; one message per clash."""
    seen, problems = {}, []
    for origin, entries in documents:
        for entry in entries:
            if entry.get('export') is None or mount_type(entry) != 'nfs':
                continue
            key = (entry.get('server') or 'controller', exported_path(entry))
            block = json.dumps(entry.get('export'), sort_keys=True)
            if key in seen and seen[key][1] != block:
                problems.append(f"{key[1]} on {key[0]} is exported by {origin} and by "
                                f"{seen[key][0]} with different export blocks")
            seen.setdefault(key, (origin, block))
    return problems


class MountsRender():
    """
    This class reads the documents and renders what they mean for a machine.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self._env = None

    @property
    def env(self):
        # built on first render only: the store-time clash check needs no template
        if self._env is None:
            self._env = Environment(loader=FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]),
                                    trim_blocks=True, lstrip_blocks=True)
        return self._env

    def server_names(self):
        """Every name an export block may carry as its server on this cluster."""
        return known_servers(Database().get_record(table='node'),
                             Database().get_record(table='controller'))

    def documents(self, exclude=None):
        """Every stored document as (origin, entries), skipping the origin being
        replaced when a store-time check supplies one."""
        documents = []
        cluster = Database().get_record(table='cluster')
        if cluster and exclude != ('cluster', None):
            documents.append(('cluster', entries_from_b64(cluster[0].get('mounts'))))
        for table in ('group', 'node'):
            rows = Database().get_record(table=table, where="mounts IS NOT NULL AND mounts != ''") or []
            for row in rows:
                if exclude != (table, row['name']):
                    documents.append((f"{table} {row['name']}", entries_from_b64(row.get('mounts'))))
        return documents

    def networks(self):
        """A Luna network name to the client specifications it stands for, one
        per family the network has."""
        result = {}
        for network in Database().get_record(table='network') or []:
            specs = []
            if network.get('network') and network.get('subnet'):
                specs.append(f"{network['network']}/{network['subnet']}")
            if network.get('network_ipv6') and network.get('subnet_ipv6'):
                specs.append(f"{network['network_ipv6']}/{network['subnet_ipv6']}")
            if specs:
                result[network['name']] = specs
        return result

    def my_addresses(self):
        """What the reserved words resolve to in this controller's own fstab: the
        beacon name, the name every machine mounts the cluster shares through."""
        return {'controller': Controller().get_beacon(), 'self': socket.gethostname()}

    def my_names(self):
        """The names this controller answers to as a server: the reserved words,
        its own hostname short and full, and the beacon name."""
        hostname = socket.gethostname()
        names = set(RESERVED_SERVERS) | {hostname, hostname.split('.', 1)[0], Controller().get_beacon()}
        return {name for name in names if name}

    def clash(self, origin, value):
        """A store-time answer: the message when the document at origin would export
        a directory another document already exports differently, else None.
        origin is ('cluster', None), ('group', name) or ('node', name)."""
        documents = [(f"{origin[0]} {origin[1] or ''}".strip(), entries_from_b64(value))]
        documents.extend(self.documents(exclude=origin))
        problems = export_clashes(documents)
        return '; '.join(problems) if problems else None

    def render_exports(self, entries, networks):
        return self.env.get_template('templ_exports.cfg').render(
            EXPORTS=export_rows(entries, networks, self.logger))

    def render_fstab(self, rows):
        return self.env.get_template('templ_fstab.cfg').render(MOUNTS=rows) if rows else ''

    def write_exports(self, text):
        """Write the exports file and reload the export table."""
        try:
            os.makedirs(os.path.dirname(EXPORTS_FILE), exist_ok=True)
            with open(EXPORTS_FILE + '.luna-tmp', 'w', encoding='utf-8') as handle:
                handle.write(text)
            os.replace(EXPORTS_FILE + '.luna-tmp', EXPORTS_FILE)
        except OSError as exp:
            return False, f'could not write {EXPORTS_FILE}: {exp}'
        try:
            result = subprocess.run(['exportfs', '-ra'], capture_output=True, text=True,
                                    timeout=COMMAND_TIMEOUT, check=False)
        except (OSError, subprocess.TimeoutExpired) as exp:
            return False, f'{EXPORTS_FILE} written, exportfs failed: {exp}'
        if result.returncode != 0:
            return False, f'{EXPORTS_FILE} written, exportfs refused it: {result.stderr.strip()}'
        return True, f'{EXPORTS_FILE} written and exported'

    def write_fstab(self, block, root='/'):
        """Write the managed block into <root>/etc/fstab, replacing what a previous
        render left there and touching nothing outside the markers."""
        fstab = os.path.join(root, FSTAB_FILE.lstrip('/'))
        try:
            with open(fstab, 'r', encoding='utf-8') as handle:
                current = handle.read().splitlines()
        except FileNotFoundError:
            current = []
        kept, inside = [], False
        for line in current:
            if line == FSTAB_BEGIN:
                inside = True
                continue
            if line == FSTAB_END:
                inside = False
                continue
            if not inside:
                kept.append(line)
        text = '\n'.join(kept).rstrip('\n')
        text = (text + '\n' if text else '') + block
        try:
            with open(fstab + '.luna-tmp', 'w', encoding='utf-8') as handle:
                handle.write(text)
            os.replace(fstab + '.luna-tmp', fstab)
        except OSError as exp:
            return False, f'could not write {fstab}: {exp}'
        if root == '/':
            # systemd generates its mount units from fstab and keeps the old set until told
            try:
                subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, text=True,
                               timeout=COMMAND_TIMEOUT, check=False)
            except (OSError, subprocess.TimeoutExpired) as exp:
                self.logger.warning(f"mounts: {fstab} written, systemd not reloaded: {exp}")
        return True, f'{fstab} written'

    def make_dirs(self, dirs, root='/'):
        """Create the mountpoints with the owner, group and mode the document gives
        them. An unknown owner or group is logged and skipped, never fatal."""
        for path, owner, group, mode in dirs:
            target = os.path.join(root, path.lstrip('/'))
            os.makedirs(target, exist_ok=True)
            try:
                uid = pwd.getpwnam(owner).pw_uid if owner != '-' else -1
                gid = grp.getgrnam(group).gr_gid if group != '-' else -1
            except KeyError as exp:
                self.logger.error(f"mountpoint {path}: unknown owner or group, left as is: {exp}")
                continue
            if uid != -1 or gid != -1:
                os.chown(target, uid, gid)
            if mode != '-':
                os.chmod(target, int(mode, 8))

    def mount(self, entries):
        """Mount the entries that ask to be mounted now and are not, each under a
        timeout so one dead server cannot hold the rest."""
        mounted = set()
        try:
            with open('/proc/mounts', 'r', encoding='utf-8') as handle:
                mounted = {line.split()[1] for line in handle if len(line.split()) > 1}
        except OSError:
            pass
        failed = []
        for entry in entries:
            if entry.get('state', 'mounted') != 'mounted' or not FSTYPES.get(mount_type(entry)):
                continue
            if entry['path'] in mounted:
                continue
            try:
                result = subprocess.run(['mount', entry['path']], capture_output=True, text=True,
                                        timeout=COMMAND_TIMEOUT, check=False)
                if result.returncode != 0:
                    failed.append(f"{entry['path']}: {result.stderr.strip() or result.returncode}")
            except (OSError, subprocess.TimeoutExpired) as exp:
                failed.append(f"{entry['path']}: {exp}")
        if failed:
            return False, 'not mounted: ' + '; '.join(failed)
        return True, 'mounts applied'

    def render_controller(self):
        """Render and apply this controller's exports from every document and its
        fstab from the cluster document. Returns (status, message)."""
        names = self.my_names()
        documents = self.documents()
        for problem in export_clashes(documents):
            self.logger.error(f"mounts: {problem}; the first one wins")
        serving, seen = [], set()
        for _, entries in documents:
            for entry in entries:
                key = (entry.get('server') or 'controller', exported_path(entry))
                if serves(entry, names) and key not in seen:
                    seen.add(key)
                    serving.append(entry)
        remote = network_mountpoints()
        refused = [exported_path(entry) for entry in serving
                   if on_network_filesystem(exported_path(entry), remote)]
        for directory in refused:
            self.logger.error(f"mounts: {directory} is a network mount on this controller and "
                              "is not exported; name the directory behind it as source")
        serving = [entry for entry in serving if exported_path(entry) not in refused]
        estatus, emessage = self.write_exports(self.render_exports(serving, self.networks()))
        if refused:
            estatus, emessage = False, f"{emessage}, not exported: {', '.join(refused)}"
        cluster_entries = next((entries for name, entries in documents if name == 'cluster'), [])
        mine = [entry for entry in cluster_entries if mounts(entry, names)]
        rows, dirs = fstab_rows(mine, self.my_addresses())
        self.make_dirs(dirs)
        fstatus, fmessage = self.write_fstab(self.render_fstab(rows))
        mstatus, mmessage = self.mount(mine)
        summary = f"{len(serving)} exports, {len(rows)} mounts: {emessage}; {fmessage}; {mmessage}"
        if estatus and fstatus and mstatus:
            self.logger.info(f"mounts: {summary}")
        else:
            self.logger.error(f"mounts: {summary}")
        return estatus and fstatus and mstatus, summary

    def render_node(self, name, value, addresses):
        """What a booting node writes: its fstab block, the exports it serves and
        its mountpoints, each base64 for the install template and empty when none.
        addresses maps the reserved servers to the addresses this node reaches."""
        entries = entries_from_b64(value)
        names = {name}
        rows, dirs = fstab_rows([entry for entry in entries if mounts(entry, names)], addresses)
        serving = [entry for entry in entries if serves(entry, names)]
        block = self.render_fstab(rows)
        exports = self.render_exports(serving, self.networks()) if serving else ''
        dir_lines = ''.join(f"{path} {owner} {group} {mode}\n" for path, owner, group, mode in dirs)
        encode = lambda text: b64encode(text.encode()).decode('ascii') if text else ''
        return {'mounts_fstab': encode(block), 'mounts_exports': encode(exports),
                'mounts_dirs': encode(dir_lines)}
