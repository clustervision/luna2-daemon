#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
The node-side profile applier.

This one runs ON the node, so it is the half of the feature the daemon's own tests cannot
reach: it is executed here as a subprocess against a real filesystem, with its state
directory pointed somewhere disposable, because everything it does is filesystem
behaviour and mocking that would only test the mock.

The three properties worth the most:

  * it acts on a service only when a file actually changed. A sweep that restarts
    unconditionally restarts sshd and slurmd across a whole cluster at once.
  * it never removes a path it did not create.
  * it puts the original back when the profile that took a path over goes away - and the
    file it is putting back over is frequently mode 400, which is why the restore cannot
    simply copy onto it.
"""

import base64
import json
import os
import subprocess
import sys

import pytest

APPLIER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'nodescripts', 'apply_profiles.py')


def _applier(tmp_path):
    """A copy of the applier with its state directory pointed at the tmp tree."""
    with open(APPLIER, encoding='utf-8') as handle:
        source = handle.read()
    state = tmp_path / 'state'
    source = source.replace("STATE = '/var/lib/luna/profiles'", f"STATE = {str(state)!r}")
    local = tmp_path / 'apply_profiles.py'
    local.write_text(source)
    return local, state


def _run(tmp_path, payload):
    """Run the applier over a payload; returns (returncode, stdout)."""
    local, _ = _applier(tmp_path)
    bundle = tmp_path / 'bundle'
    bundle.mkdir(exist_ok=True)
    (bundle / 'payload.json').write_text(json.dumps(payload))
    result = subprocess.run([sys.executable, str(local), str(bundle)],
                            capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout


def _file(path, content='x', **extra):
    entry = {'name': 'f', 'path': str(path),
             'content': base64.b64encode(content.encode()).decode()}
    entry.update(extra)
    return entry


def _payload(target, digest='d1', **overrides):
    profile = {'name': 'p', 'service': '', 'action': 'none', 'files': [target]}
    profile.update(overrides)
    return {'node': 'node001', 'profiles': [profile], 'frozen': [], 'digest': digest}


def test_writes_the_file_with_its_mode(tmp_path):
    target = tmp_path / 'etc' / 'thing.conf'
    code, out = _run(tmp_path, _payload(_file(target, 'hello', mode='400')))
    assert code == 0, out
    assert 'DIGEST d1' in out
    assert target.read_text() == 'hello'
    assert oct(target.stat().st_mode & 0o777) == '0o400'


def test_a_second_run_changes_nothing_and_touches_no_service(tmp_path):
    """The property that keeps a re-apply from restarting the cluster."""
    target = tmp_path / 'etc' / 'thing.conf'
    payload = _payload(_file(target, 'hello', mode='644'), service='sshd', action='restart')
    code, out = _run(tmp_path, payload)
    assert code == 0, out
    assert 'systemctl restart sshd' in out, 'the first write should act on the service'
    code, out = _run(tmp_path, payload)
    assert code == 0, out
    assert 'systemctl' not in out, 'an unchanged profile must not touch the service'


def test_a_changed_file_acts_on_the_service_again(tmp_path):
    target = tmp_path / 'etc' / 'thing.conf'
    _run(tmp_path, _payload(_file(target, 'one'), service='sshd', action='restart'))
    code, out = _run(tmp_path, _payload(_file(target, 'two', ), digest='d2',
                                        service='sshd', action='restart'))
    assert code == 0, out
    assert target.read_text() == 'two'
    assert 'systemctl restart sshd' in out


def test_the_original_is_preserved_and_put_back(tmp_path):
    """The whole reason the backup is local rather than taken from the osimage: this is
    the state the node was actually in, which the image may never have held."""
    target = tmp_path / 'etc' / 'thing.conf'
    target.parent.mkdir(parents=True)
    target.write_text('the original')
    os.chmod(target, 0o664)

    code, out = _run(tmp_path, _payload(_file(target, 'from the profile', mode='400')))
    assert code == 0, out
    assert target.read_text() == 'from the profile'

    # the profile no longer applies to this node
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert 'RESTORED' in out
    assert target.read_text() == 'the original'
    assert oct(target.stat().st_mode & 0o777) == '0o664', 'the original mode came back too'


def test_restore_works_over_a_read_only_file(tmp_path):
    """A profile file is routinely mode 400. Copying onto it fails on its own mode, so
    the restore has to write beside it and rename."""
    target = tmp_path / 'etc' / 'secret'
    target.parent.mkdir(parents=True)
    target.write_text('original')
    _run(tmp_path, _payload(_file(target, 'managed', mode='400')))
    assert oct(target.stat().st_mode & 0o777) == '0o400'
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert target.read_text() == 'original'


def test_a_file_that_did_not_exist_is_removed_again(tmp_path):
    target = tmp_path / 'etc' / 'new.conf'
    _run(tmp_path, _payload(_file(target, 'made by the profile')))
    assert target.exists()
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert 'REMOVED' in out
    assert not target.exists(), 'a path the profile created should not survive its removal'


def test_a_frozen_profile_is_left_exactly_as_it_is(tmp_path):
    """Disabling changes nothing on the node: the file stays, and it is not reclaimed."""
    target = tmp_path / 'etc' / 'thing.conf'
    _run(tmp_path, _payload(_file(target, 'managed'), service='sshd', action='restart'))
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': ['p'],
                                'digest': 'frozen'})
    assert code == 0, out
    assert target.exists(), 'a frozen profile must not have its files reclaimed'
    assert target.read_text() == 'managed'
    assert 'systemctl' not in out, 'freezing must not touch the service'
    assert 'REMOVED' not in out and 'RESTORED' not in out


def test_a_frozen_profile_is_still_reclaimed_once_actually_removed(tmp_path):
    """Removed is removed; disabled is not. A profile that was frozen and is then
    unassigned reverts like any other."""
    target = tmp_path / 'etc' / 'thing.conf'
    _run(tmp_path, _payload(_file(target, 'managed')))
    _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': ['p'], 'digest': 'f'})
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert not target.exists()


def test_nothing_outside_the_manifest_is_ever_touched(tmp_path):
    """A path the applier never wrote is not its business, however tempting."""
    stranger = tmp_path / 'etc' / 'not-ours.conf'
    stranger.parent.mkdir(parents=True)
    stranger.write_text('somebody else wrote this')
    target = tmp_path / 'etc' / 'ours.conf'
    _run(tmp_path, _payload(_file(target, 'ours')))
    _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [], 'digest': 'gone'})
    assert stranger.read_text() == 'somebody else wrote this'


def test_a_broken_payload_reports_no_digest(tmp_path):
    """The caller records what the node reports. Reporting a digest for a run that did
    not happen would mark the node in line on a guess."""
    local, _ = _applier(tmp_path)
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'payload.json').write_text('this is not json')
    result = subprocess.run([sys.executable, str(local), str(bundle)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'DIGEST' not in result.stdout


def test_the_manifest_records_what_it_needs_for_removal(tmp_path):
    """Service and action are recorded per path: when the profile is later removed it is
    gone from the payload, and the service still has to be told."""
    target = tmp_path / 'etc' / 'thing.conf'
    _, state = _applier(tmp_path)
    _run(tmp_path, _payload(_file(target, 'x'), service='munge', action='restart'))
    manifest = json.loads((state / 'manifest.json').read_text())
    record = manifest[str(target)]
    assert record['profile'] == 'p'
    assert record['service'] == 'munge'
    assert record['action'] == 'restart'
    assert record['existed_before'] is False


def test_removal_acts_on_the_service_it_recorded(tmp_path):
    target = tmp_path / 'etc' / 'thing.conf'
    _run(tmp_path, _payload(_file(target, 'x'), service='munge', action='restart'))
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert 'systemctl restart munge' in out, \
        'a service whose configuration was just taken away was never told'


# ---------------------------------------------------------------------------
# the handover: a manifest written by the installer's bash, consumed by the applier
# ---------------------------------------------------------------------------

def _installer_seeded(tmp_path, path, existed_before):
    """The manifest the installer's node_profiles() writes, in its exact shape."""
    state = tmp_path / 'state'
    (state / 'backup' / path.parent.relative_to(path.anchor)).mkdir(parents=True, exist_ok=True)
    manifest = {str(path): {'profile': 'p', 'existed_before': existed_before,
                            'service': 'chronyd', 'action': 'restart'}}
    state.mkdir(parents=True, exist_ok=True)
    (state / 'manifest.json').write_text(json.dumps(manifest))
    return state


def test_the_installers_manifest_is_understood(tmp_path):
    """The installer seeds the record in bash and the applier maintains it from there.
    If the two ever disagree about its shape, a freshly installed node quietly keeps the
    profile's own output as the thing to restore."""
    target = tmp_path / 'etc' / 'chrony.conf'
    target.parent.mkdir(parents=True)
    target.write_text('written by the installer')

    _applier(tmp_path)                                  # creates the state dir path
    state = _installer_seeded(tmp_path, target, existed_before=True)
    backup = state / 'backup' / str(target).lstrip('/')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text('the original from the image')
    os.chmod(backup, 0o640)

    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert target.read_text() == 'the original from the image'
    assert oct(target.stat().st_mode & 0o777) == '0o640', \
        'cp -a preserved the mode on the backup, and the restore must use it'
    assert 'systemctl restart chronyd' in out, \
        'the service named in the installer-written manifest was never told'


def test_a_seeded_entry_that_never_existed_is_removed(tmp_path):
    target = tmp_path / 'etc' / 'brandnew.conf'
    target.parent.mkdir(parents=True)
    target.write_text('written by the installer')
    _applier(tmp_path)
    _installer_seeded(tmp_path, target, existed_before=False)
    code, out = _run(tmp_path, {'node': 'node001', 'profiles': [], 'frozen': [],
                                'digest': 'gone'})
    assert code == 0, out
    assert not target.exists()


def test_a_slow_service_is_given_room(tmp_path):
    """A service can legitimately take minutes to come back - a database, a filesystem
    client, anything with state to settle. The bound exists to stop a hung unit holding
    the node forever, not to express an expectation about how fast a service restarts."""
    with open(APPLIER, encoding='utf-8') as handle:
        source = handle.read()
    assert 'SERVICE_TIMEOUT = 300' in source, \
        'the service action bound is short enough to kill a slow but healthy restart'
    assert 'timeout=SERVICE_TIMEOUT' in source


def test_a_stale_backup_does_not_resurrect_a_file(tmp_path):
    """Found on a live node. A path taken over, reclaimed (deleted, because nothing was
    there before), then taken over again: if a leftover backup counts as proof the file
    existed, removing the profile the second time restores a file that was not there -
    and it survives a cleanup that was supposed to leave nothing behind."""
    target = tmp_path / 'etc' / 'thing.conf'
    target.parent.mkdir(parents=True)
    target.write_text('an original, from long ago')

    # cycle one: taken over, then reclaimed - the original goes back, backup consumed
    _run(tmp_path, _payload(_file(target, 'managed')))
    _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g'})
    assert target.read_text() == 'an original, from long ago'

    # the file is removed by hand, and the profile applies again
    target.unlink()
    _run(tmp_path, _payload(_file(target, 'managed again'), digest='d2'))

    # cycle two: nothing was there this time, so removal must take it away
    code, out = _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g2'})
    assert code == 0, out
    assert not target.exists(), 'a stale backup put back a file that did not exist'


def test_reclaiming_by_deletion_forgets_the_backup(tmp_path):
    """Otherwise the leftover is waiting to be believed on the next cycle."""
    import os as _os
    target = tmp_path / 'etc' / 'thing.conf'
    _, state = _applier(tmp_path)
    _run(tmp_path, _payload(_file(target, 'managed')))
    _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g'})
    leftovers = []
    for root, _dirs, files in _os.walk(state / 'backup'):
        leftovers += [f for f in files]
    assert leftovers == [], f'backups left behind: {leftovers}'


def test_two_profiles_claiming_one_path(tmp_path):
    """Stacking allows it, and the later one wins. What must not happen is the second
    one recording the FIRST one's output as the original: removing every profile would
    then put our own writing back and leave it there for good."""
    target = tmp_path / 'etc' / 'shared.conf'
    payload = {'node': 'n', 'frozen': [], 'digest': 'd', 'profiles': [
        {'name': 'base', 'service': '', 'action': 'none',
         'files': [_file(target, 'from-base', mode='644')]},
        {'name': 'override', 'service': '', 'action': 'none',
         'files': [_file(target, 'from-override', mode='600')]},
    ]}
    code, out = _run(tmp_path, payload)
    assert code == 0, out
    assert target.read_text() == 'from-override', 'the later profile should win'
    assert oct(target.stat().st_mode & 0o777) == '0o600'

    code, out = _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g'})
    assert code == 0, out
    assert not target.exists(), \
        'nothing was there before the profiles, so nothing should be left after them'


def test_the_loser_takes_the_path_back_when_the_winner_goes(tmp_path):
    """The path is still claimed, just by somebody else - it is not a removal."""
    target = tmp_path / 'etc' / 'shared.conf'
    both = {'node': 'n', 'frozen': [], 'digest': 'd', 'profiles': [
        {'name': 'base', 'service': '', 'action': 'none',
         'files': [_file(target, 'from-base')]},
        {'name': 'override', 'service': '', 'action': 'none',
         'files': [_file(target, 'from-override')]},
    ]}
    _run(tmp_path, both)
    only_base = dict(both, digest='d2', profiles=[both['profiles'][0]])
    code, out = _run(tmp_path, only_base)
    assert code == 0, out
    assert target.read_text() == 'from-base'
    assert 'REMOVED' not in out and 'RESTORED' not in out


def test_a_profile_with_no_files_still_acts_on_its_service(tmp_path):
    """A profile can be nothing but a service and an action. With no file to compare,
    the profile itself is what changed - or did not."""
    payload = {'node': 'n', 'frozen': [], 'digest': 'd', 'profiles': [
        {'name': 'justaservice', 'service': 'sshd', 'action': 'restart', 'files': []},
    ]}
    code, out = _run(tmp_path, payload)
    assert code == 0, out
    assert 'systemctl restart sshd' in out, 'a service-only profile did nothing at all'

    code, out = _run(tmp_path, payload)
    assert code == 0, out
    assert 'systemctl' not in out, 'an unchanged service-only profile acted again'

    changed = {'node': 'n', 'frozen': [], 'digest': 'd2', 'profiles': [
        {'name': 'justaservice', 'service': 'sshd', 'action': 'reload', 'files': []},
    ]}
    code, out = _run(tmp_path, changed)
    assert 'systemctl reload sshd' in out, 'a changed service-only profile did nothing'


def test_directories_we_made_are_given_back(tmp_path):
    """A profile file often lands somewhere that does not exist yet. Removing the file
    and leaving the tree behind is litter, and on a cluster with any churn it
    accumulates - a cleanup that leaves something behind is not a cleanup."""
    target = tmp_path / 'etc' / 'newdir' / 'deeper' / 'thing.conf'
    (tmp_path / 'etc').mkdir()
    _run(tmp_path, _payload(_file(target, 'x')))
    assert target.exists()
    code, out = _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g'})
    assert code == 0, out
    assert not (tmp_path / 'etc' / 'newdir').exists(), 'the tree we created was left behind'
    assert (tmp_path / 'etc').exists(), 'a directory that was already there is not ours'


def test_a_directory_someone_else_uses_is_left_alone(tmp_path):
    """Only the ones we made, and only while empty."""
    shared = tmp_path / 'etc' / 'shared'
    shared.mkdir(parents=True)
    target = shared / 'ours.conf'
    _run(tmp_path, _payload(_file(target, 'x')))
    (shared / 'someone-elses.conf').write_text('not ours')
    code, out = _run(tmp_path, {'node': 'n', 'profiles': [], 'frozen': [], 'digest': 'g'})
    assert code == 0, out
    assert shared.exists() and (shared / 'someone-elses.conf').exists()


def test_a_path_with_spaces_survives(tmp_path):
    """The applier is python and handles it; the point is that nothing downstream
    re-splits the path on whitespace."""
    target = tmp_path / 'etc' / 'luna demo' / 'nested file.conf'
    code, out = _run(tmp_path, _payload(_file(target, 'spaced')))
    assert code == 0, out
    assert target.read_text() == 'spaced'


def test_binary_content_survives_byte_for_byte(tmp_path):
    """The reason content travels base64 and the record is a manifest rather than a
    marker comment: a keytab cannot carry a header, and must not be mangled."""
    import base64 as _b64
    raw = bytes(range(256))
    target = tmp_path / 'etc' / 'thing.key'
    entry = {'name': 'k', 'path': str(target),
             'content': _b64.b64encode(raw).decode(), 'mode': '400'}
    code, out = _run(tmp_path, _payload(entry))
    assert code == 0, out
    assert target.read_bytes() == raw


def test_the_resolved_owner_is_what_gets_applied(tmp_path):
    """The controller resolves the owner against the directory precisely because the node
    may have none, and sends the numbers alongside the name. Applying the name instead
    leaves the file root-owned on exactly the clusters that resolution exists for - while
    the installer path, which uses the resolved value, gets it right. The same profile,
    applied two different ways, is the bug this pins."""
    target = tmp_path / 'owned.conf'
    entry = _file(target, 'x', owner='a-directory-user:a-directory-group',
                  resolved_owner=f'{os.getuid()}:{os.getgid()}', mode='644')
    code, out = _run(tmp_path, _payload(entry))
    assert code == 0, out
    assert 'could not be resolved' not in out, \
        'the name was used and failed, while the resolved number was sitting in the payload'
    assert target.stat().st_uid == os.getuid()


def test_a_name_is_still_honoured_when_the_controller_sent_no_number(tmp_path):
    """A user that exists on the node but not on the controller still works: the name is
    the fallback, not the other way round."""
    target = tmp_path / 'named.conf'
    entry = _file(target, 'x', owner=f'{os.getuid()}:{os.getgid()}', mode='644')
    code, out = _run(tmp_path, _payload(entry))
    assert code == 0, out
    assert 'could not be resolved' not in out
    assert target.stat().st_uid == os.getuid()


def test_an_owner_nobody_can_resolve_is_reported_not_silently_dropped(tmp_path):
    target = tmp_path / 'unknown.conf'
    entry = _file(target, 'x', owner='nobody-anywhere:nobody-anywhere', mode='644')
    code, out = _run(tmp_path, _payload(entry))
    assert code == 0, out
    assert 'could not be resolved' in out
