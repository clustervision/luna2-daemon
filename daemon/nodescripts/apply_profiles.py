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
Applies a node's profiles. Runs ON THE NODE, not on the controller, and travels with the
payload it applies - so there is nothing installed on a node to keep in step with the
daemon, and no version skew to carry forever.

Standard library only, and no imports from the daemon: a node has neither.

Three things it must get right, in order of how much they would cost to get wrong:

  * act on a service only if a file actually changed. A sweep that restarts unconditionally
    restarts sshd and slurmd across the whole cluster at once.
  * never delete a path it did not create. What we wrote is recorded in the manifest, and
    nothing outside it is ever touched.
  * back up the original the first time a path is taken over, and put it back when the
    profile that owned it goes away. Restoring from the osimage instead would put the node
    into a state it was never in.

Usage: apply_profiles.py <bundle directory>
Prints DIGEST <digest> on success. The caller records that, and treats its absence as a
failure rather than assuming the applier did what it was told.
"""

import base64
import grp
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys

STATE = '/var/lib/luna/profiles'
MANIFEST = os.path.join(STATE, 'manifest.json')
BACKUP = os.path.join(STATE, 'backup')
DIGEST_FILE = os.path.join(STATE, 'digest')


def read_manifest():
    """What we have written to this node before, if anything."""
    try:
        with open(MANIFEST, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError):
        return {}


def write_manifest(manifest):
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    tmp = MANIFEST + '.new'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    os.replace(tmp, MANIFEST)


def file_hash(path):
    """The hash of a file on disk, or None when it is not there."""
    try:
        with open(path, 'rb') as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (IOError, OSError):
        return None


def backup_path(path):
    return os.path.join(BACKUP, path.lstrip('/'))


def preserve(path):
    """
    Keep the original the FIRST time we take a path over, and never again: a second copy
    would record a previous profile's output as the thing to restore.
    Returns True when the path existed before we touched it.
    """
    target = backup_path(path)
    if os.path.exists(target):
        return True
    if not os.path.exists(path):
        return False
    os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
    shutil.copy2(path, target)
    stat = os.stat(path)
    with open(target + '.meta', 'w', encoding='utf-8') as handle:
        json.dump({'uid': stat.st_uid, 'gid': stat.st_gid, 'mode': oct(stat.st_mode & 0o7777)},
                  handle)
    return True


def restore(path):
    """Put back what was there before a profile took the path over."""
    source = backup_path(path)
    if not os.path.exists(source):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # write and rename rather than copy onto the target: a profile file is frequently
    # mode 400, and copying opens the destination for writing, which its own mode forbids
    tmp = path + '.luna.restore'
    shutil.copyfile(source, tmp)
    os.replace(tmp, path)
    try:
        with open(source + '.meta', 'r', encoding='utf-8') as handle:
            meta = json.load(handle)
    except (IOError, OSError, ValueError):
        # no sidecar: the installer seeds its backups with cp -a, which preserves owner
        # and mode on the copy itself, so the backup is its own record
        stat = os.stat(source)
        meta = {'uid': stat.st_uid, 'gid': stat.st_gid, 'mode': oct(stat.st_mode & 0o7777)}
    try:
        os.chown(path, meta['uid'], meta['gid'])
        os.chmod(path, int(meta['mode'], 8))
    except (OSError, ValueError, KeyError):
        pass
    os.remove(source)
    if os.path.exists(source + '.meta'):
        os.remove(source + '.meta')
    return True


def resolve_owner(owner):
    """
    'user', 'user:group', numeric or named, to (uid, gid). The controller normally sends
    numbers already, because it can resolve a directory user and this node may not be
    able to. Names are still accepted for a user that exists only here.
    """
    if not owner:
        return None, None
    user, _, group = owner.partition(':')
    uid = gid = None
    if user:
        try:
            uid = int(user) if user.isdigit() else pwd.getpwnam(user).pw_uid
        except (KeyError, ValueError):
            uid = None
    if group:
        try:
            gid = int(group) if group.isdigit() else grp.getgrnam(group).gr_gid
        except (KeyError, ValueError):
            gid = None
    return uid, gid


def write_file(entry):
    """
    Write one profile file if it differs from what is on disk. Returns True when anything
    actually changed - which is what decides whether the service is touched.
    """
    path = entry['path']
    content = base64.b64decode(entry.get('content') or '')
    changed = False

    if file_hash(path) != hashlib.sha256(content).hexdigest():
        os.makedirs(os.path.dirname(path) or '/', exist_ok=True)
        tmp = path + '.luna.new'
        with open(tmp, 'wb') as handle:
            handle.write(content)
        os.replace(tmp, path)
        changed = True

    mode = entry.get('mode') or '644'
    try:
        wanted = int(str(mode), 8)
        if (os.stat(path).st_mode & 0o7777) != wanted:
            os.chmod(path, wanted)
            changed = True
    except (ValueError, OSError) as exp:
        print(f"WARNING could not set mode {mode} on {path}: {exp}")

    uid, gid = resolve_owner(entry.get('owner'))
    if uid is not None:
        try:
            stat = os.stat(path)
            if stat.st_uid != uid or (gid is not None and stat.st_gid != gid):
                os.chown(path, uid, gid if gid is not None else -1)
                changed = True
        except OSError as exp:
            print(f"WARNING could not set owner {entry.get('owner')} on {path}: {exp}")
    elif entry.get('owner'):
        print(f"WARNING owner {entry['owner']} for {path} cannot be resolved on this node")

    return changed


def act_on_service(service, action):
    """
    Only ever called when something changed. 'none' is a real answer and means leave the
    service alone; anything unrecognised is treated that way too rather than guessed at.
    """
    if not service or action in (None, '', 'none'):
        return
    if action not in ('restart', 'stop', 'reload', 'start'):
        print(f"WARNING unknown action {action} for service {service}; doing nothing")
        return
    command = ['systemctl', action, service]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120, check=False)
        if result.returncode != 0:
            print(f"WARNING {' '.join(command)} exited {result.returncode}: "
                  f"{result.stderr.decode(errors='replace').strip()}")
        else:
            print(f"OK {' '.join(command)}")
    except (OSError, subprocess.SubprocessError) as exp:
        print(f"WARNING could not run {' '.join(command)}: {exp}")


def apply_payload(payload):
    """
    Bring this node into line with the payload. Returns the new manifest.
    """
    manifest = read_manifest()
    new_manifest = {}
    touched_services = {}

    # what is ours to manage this time round
    for profile in payload.get('profiles') or []:
        for entry in profile.get('files') or []:
            path = entry['path']
            existed = manifest.get(path, {}).get('existed_before')
            if existed is None:
                existed = preserve(path)
            if write_file(entry):
                touched_services[profile['name']] = (profile.get('service'),
                                                     profile.get('action'))
            # service and action are recorded per path, not just held in the payload:
            # when the profile is later removed it is gone from the payload, and the
            # service still has to be told that its configuration went away
            new_manifest[path] = {
                'profile': profile['name'],
                'existed_before': existed,
                'owner': entry.get('owner'),
                'mode': entry.get('mode'),
                'service': profile.get('service'),
                'action': profile.get('action'),
            }

    # what a disabled profile owns: left exactly as it is, and kept in the manifest so
    # nothing below reclaims it. this is the whole of what disabling does.
    frozen = payload.get('frozen') or []
    for path, record in manifest.items():
        if path in new_manifest:
            continue
        if record.get('profile') in frozen:
            record['frozen'] = True
            new_manifest[path] = record

    # what nobody owns any more: put it back, or take it away
    for path, record in manifest.items():
        if path in new_manifest:
            continue
        if record.get('existed_before'):
            restored = restore(path)
            print(f"{'RESTORED' if restored else 'MISSING BACKUP FOR'} {path}")
        else:
            try:
                os.remove(path)
                print(f"REMOVED {path}")
            except OSError as exp:
                print(f"WARNING could not remove {path}: {exp}")
        owner = record.get('profile')
        if owner and owner not in touched_services:
            touched_services[owner] = (record.get('service'), record.get('action'))

    # once per profile, whatever it was that changed under it
    for service, action in touched_services.values():
        act_on_service(service, action)

    return new_manifest


def main():
    if len(sys.argv) < 2:
        print('ERROR no bundle directory given')
        return 2
    bundle = sys.argv[1]
    try:
        with open(os.path.join(bundle, 'payload.json'), 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (IOError, OSError, ValueError) as exp:
        print(f'ERROR could not read the payload: {exp}')
        return 2

    try:
        manifest = apply_payload(payload)
        write_manifest(manifest)
    except Exception as exp:                                    # noqa: BLE001
        # a half-applied node must not report a digest: that would mark it in line
        print(f'ERROR applying profiles: {exp}')
        return 1

    digest = payload.get('digest') or ''
    with open(DIGEST_FILE, 'w', encoding='utf-8') as handle:
        handle.write(digest)
    print(f'DIGEST {digest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
