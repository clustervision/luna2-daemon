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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
The warning an update answers with when it moves an install mode away from legacy while
what the classic installer used is still set: a prescript, partscript or postscript, or
a disk partitioning boot script. lpart runs pre/part/post before its own phases.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from base64 import b64decode
from utils.database import Database

LPART_MODES = ('auto', 'sync', 'full', 'local', 'memboot', 'sanitize')
SCRIPTS = ('prescript', 'partscript', 'postscript')
PARTITIONING = ('diskfull', 'raid1')
# a cluster warning names this many and counts the rest
NAMED = 5


def is_legacy(mode=None):
    """Unset is legacy: that is what a node resolves an empty install_mode to."""
    return (mode or 'legacy') not in LPART_MODES


def _filled(value=None):
    try:
        return bool(b64decode(value or '').decode('utf-8', 'replace').strip())
    except ValueError:
        return bool(value)


def leftovers(row=None):
    """What the classic installer used that a group or node still carries."""
    row = row or {}
    found = [key for key in SCRIPTS if _filled(row.get(key))]
    plugins = [name.strip() for name in (row.get('scripts') or '').split(',')]
    found += [f'disk partitioning script {name}' for name in plugins if name in PARTITIONING]
    return found


def warning(old_mode=None, new_mode=None, found=None):
    if not found or not is_legacy(old_mode) or is_legacy(new_mode):
        return ''
    listed = found[0] if len(found) == 1 else f"{', '.join(found[:-1])} and {found[-1]}"
    return (f"; warning: install_mode {old_mode or 'legacy'} -> {new_mode}, but {listed} "
            f"{'is' if len(found) == 1 else 'are'} still set")


def _cluster_mode():
    cluster = Database().get_record(table='cluster')
    return cluster[0]['install_mode'] if cluster else None


def _group(groupid=None):
    rows = Database().get_record(table='group', where=f"id = '{groupid}'") if groupid else None
    return rows[0] if rows else {}


def group_warning(old=None, data=None):
    """old is the group row before the update, data what the update writes."""
    if 'install_mode' not in (data or {}):
        return ''
    cluster = _cluster_mode()
    merged = {key: data.get(key, old.get(key)) for key in SCRIPTS + ('scripts',)}
    return warning(old.get('install_mode') or cluster, data['install_mode'] or cluster, leftovers(merged))


def node_warning(old=None, data=None):
    """old is the node row before the update; a node inherits from its group, then the cluster."""
    data = data or {}
    if 'install_mode' not in data and 'groupid' not in data:
        return ''
    cluster = _cluster_mode()
    old_group = _group(old.get('groupid'))
    new_group = _group(data.get('groupid', old.get('groupid')))
    merged = {key: data.get(key, old.get(key)) or new_group.get(key)
              for key in SCRIPTS + ('scripts',)}
    return warning(old.get('install_mode') or old_group.get('install_mode') or cluster,
                   data.get('install_mode', old.get('install_mode')) or
                   new_group.get('install_mode') or cluster, leftovers(merged))


def cluster_warning(old_mode=None, new_mode=None):
    """The groups and nodes that follow the cluster's mode and still carry legacy settings."""
    if not is_legacy(old_mode) or is_legacy(new_mode):
        return ''
    groups = {group['id']: group for group in Database().get_record(table='group') or []}
    names = [f"group {group['name']}" for group in groups.values()
             if not group['install_mode'] and leftovers(group)]
    names += [f"node {node['name']}" for node in Database().get_record(table='node') or []
              if not node['install_mode'] and not groups.get(node['groupid'], {}).get('install_mode')
              and leftovers(node)]
    if not names:
        return ''
    more = f' and {len(names) - NAMED} more' if len(names) > NAMED else ''
    return (f"; warning: install_mode {old_mode or 'legacy'} -> {new_mode}, but {', '.join(names[:NAMED])}"
            f"{more} still carry a prescript, partscript, postscript or disk partitioning script")
