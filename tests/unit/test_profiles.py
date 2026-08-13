#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
TRIX-1968 unit tests: profiles.

A profile is the CM generic-role idea in Luna terms: a named bundle of files
(content, path, owner, mode) plus a service with an action, assigned to groups
and nodes. Profiles stack - a node applies its group's profiles plus its own,
additively - and are applied at install time: files written with the secrets
machinery's ownership handling, the service enabled (or disabled) in the image.

File contents travel base64 over the API and are stored through the same
encryption path as secrets. The service named in a profile is a unit on the
node; it has nothing to do with the daemon's own service handling.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates',
)


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the profile-relevant tables created."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    Helper.owner_cache = {}
    for table in ['node', 'group', 'profile', 'profilefile', 'ownercache', 'queue']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None
    Helper.owner_cache = {}


@pytest.fixture
def seed(db):
    """A group and a node in it."""
    from utils.helper import Helper
    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    nodeid = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    return {'groupid': groupid, 'nodeid': nodeid}


def _assign(db, table, rowid, *names):
    """Assign profiles the way the daemon stores them: by reference. The names go in at
    the API boundary, which has its own test - here we are past it."""
    from base.profile import Profile
    from utils.helper import Helper
    ids = Profile().to_profile_ids(','.join(names))
    db.update(table, Helper().make_rows({'profiles': ids}), [{"column": "id", "value": rowid}])


def _payload(name, **detail):
    return {'config': {'profiles': {name: detail}}}


def _make(name='munge', **overrides):
    detail = {
        'scope': 'static', 'service': 'munge', 'action': 'restart',
        'files': [{'name': 'key', 'content': 'bXVuZ2VrZXk=', 'path': '/etc/munge/munge.key',
                   'owner': 'root:root', 'mode': '400'}],
    }
    detail.update(overrides)
    return _payload(name, **detail)


def test_profile_round_trip(db):
    from base.profile import Profile
    status, message = Profile().update_profile('munge', _make())
    assert status, message
    assert 'created' in message
    status, response = Profile().get_profile('munge')
    assert status, response
    detail = response['config']['profiles']['munge']
    assert (detail['scope'], detail['service'], detail['action']) == ('static', 'munge', 'restart')
    assert len(detail['files']) == 1
    entry = detail['files'][0]
    assert (entry['name'], entry['path'], entry['owner'], entry['mode']) == \
        ('key', '/etc/munge/munge.key', 'root:root', '400')
    assert entry['content'] == 'bXVuZ2VrZXk='


def test_profile_content_is_encrypted_at_rest(db):
    """Same at-rest handling as secrets: the row never holds the plain base64."""
    from base.profile import Profile
    Profile().update_profile('munge', _make())
    stored = db.get_record(table='profilefile')[0]['content']
    assert stored != 'bXVuZ2VrZXk=', 'file content stored unencrypted'


def test_profile_update_upserts_files_by_name(db):
    from base.profile import Profile
    Profile().update_profile('munge', _make())
    status, message = Profile().update_profile('munge', _make(files=[
        {'name': 'key', 'content': 'bmV3a2V5', 'path': '/etc/munge/munge.key'},
        {'name': 'extra', 'content': 'ZXh0cmE=', 'path': '/etc/munge/extra'},
    ]))
    assert status, message
    assert len(db.get_record(table='profile')) == 1, 'update created a second profile'
    _, response = Profile().get_profile('munge')
    files = {f['name']: f for f in response['config']['profiles']['munge']['files']}
    assert set(files) == {'key', 'extra'}
    assert files['key']['content'] == 'bmV3a2V5'


def test_profile_file_requires_name_content_and_path(db):
    from base.profile import Profile
    status, message = Profile().update_profile('bad', _payload(
        'bad', files=[{'name': 'x', 'content': 'eA=='}]))
    assert not status
    assert 'path' in message


def test_profile_clone_copies_the_files(db):
    from base.profile import Profile
    Profile().update_profile('munge', _make())
    status, message = Profile().clone_profile('munge', _payload(
        'munge', newprofilename='munge2'))
    assert status, message
    _, response = Profile().get_profile('munge2')
    assert len(response['config']['profiles']['munge2']['files']) == 1
    status, _ = Profile().clone_profile('munge', _payload('munge', newprofilename='munge2'))
    assert not status, 'cloning onto an existing name must fail'


def test_profile_delete_takes_its_files_along(db):
    from base.profile import Profile
    Profile().update_profile('munge', _make())
    status, message = Profile().delete_profile('munge')
    assert status, message
    assert not db.get_record(table='profile')
    assert not db.get_record(table='profilefile'), 'orphaned profile files left behind'


def test_a_profile_in_use_cannot_be_deleted(db, seed):
    """Guarded like an osimage. Removing the assignment first is not busywork: that is
    what puts the files back on the nodes, and it can only be worked out while the
    profile still exists to say what should be undone."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('inuse', _make('inuse'))
    _assign(db, 'group', seed['groupid'], 'inuse')
    status, message = Profile().delete_profile('inuse')
    assert not status
    assert 'compute' in message and 'Remove it from them first' in message
    assert db.get_record(table='profile', where='name = "inuse"'), 'it was deleted anyway'

    db.update('group', Helper().make_rows({'profiles': ''}),
              [{"column": "id", "value": seed['groupid']}])
    status, message = Profile().delete_profile('inuse')
    assert status, message


def test_in_use_matches_whole_names_only(db, seed):
    """'gpu' must not be held in use by a node carrying 'gpu-extra'."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('gpu', _make('gpu'))
    _assign(db, 'node', seed['nodeid'], 'gpu-extra')
    assert Profile().assigned_to('gpu') == []


def test_profile_single_file_delete(db):
    from base.profile import Profile
    Profile().update_profile('munge', _make(files=[
        {'name': 'a', 'content': 'YQ==', 'path': '/etc/a'},
        {'name': 'b', 'content': 'Yg==', 'path': '/etc/b'},
    ]))
    status, message = Profile().delete_profile_file('munge', 'a')
    assert status, message
    _, response = Profile().get_profile('munge')
    assert [f['name'] for f in response['config']['profiles']['munge']['files']] == ['b']


def test_update_warns_when_a_file_owner_does_not_resolve(db):
    from base.profile import Profile
    status, message = Profile().update_profile('typo', _payload('typo', files=[
        {'name': 'x', 'content': 'eA==', 'path': '/etc/x', 'owner': 'ghostuser:ghostgroup'}]))
    assert status, message
    assert 'Warning' in message and 'ghostuser:ghostgroup' in message


def test_boot_profile_carries_the_installer_attributes(db):
    """What the node fetches: defaults filled in, owner resolved to numbers, the
    service and action it will apply."""
    from base.profile import Profile
    Profile().update_profile('munge', _make(files=[
        {'name': 'key', 'content': 'bXVuZ2VrZXk=', 'path': '/etc/munge/munge.key',
         'owner': 'root:root', 'mode': '400'},
        {'name': 'plain', 'content': 'cGxhaW4=', 'path': '/etc/plain'},
    ]))
    status, response = Profile().get_boot_profile('munge')
    assert status, response
    detail = response['profile']['munge']
    assert (detail['service'], detail['action']) == ('munge', 'restart')
    files = {f['name']: f for f in detail['files']}
    assert (files['key']['resolved_owner'], files['key']['mode']) == ('0:0', '400')
    # unset attributes travel as the profile-file defaults: root's file, 644
    assert (files['plain']['owner'], files['plain']['mode'],
            files['plain']['resolved_owner']) == ('root:root', '644', '0:0')


def test_profiles_stack_group_first_then_node(db, seed):
    """A node applies group ∪ own, deduplicated, group first - the additive
    exception to inheritance, same as secrets."""
    from base.profile import Profile
    from utils.helper import Helper
    for name in ('common', 'gpu', 'special'):
        Profile().update_profile(name, _make(name))
    _assign(db, 'group', seed['groupid'], 'common', 'gpu')
    _assign(db, 'node', seed['nodeid'], 'special', 'common')
    assert Profile().merged_profiles(seed['nodeid']) == 'common,gpu,special'


def test_a_node_without_a_group_still_gets_its_own_profiles(db):
    from base.profile import Profile
    from utils.helper import Helper
    nodeid = db.insert('node', Helper().make_rows({'name': 'lone'}))
    Profile().update_profile('solo', _make('solo'))
    _assign(db, 'node', nodeid, 'solo')
    assert Profile().merged_profiles(nodeid) == 'solo'


def test_a_node_fetches_its_whole_profile_set_by_name(db, seed):
    """One call, by node name, returns everything the node applies - the group's
    profiles and its own, apply-ready. This is what a node uses when it does not
    know its profile names."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('common', _make('common'))
    Profile().update_profile('special', _payload('special', service='sssd', action='reload',
        files=[{'name': 'x', 'content': 'eA==', 'path': '/etc/x'}]))
    _assign(db, 'group', seed['groupid'], 'common')
    _assign(db, 'node', seed['nodeid'], 'special')
    status, response = Profile().get_node_profiles('node001')
    assert status, response
    profiles = response['config']['profiles']
    assert list(profiles.keys()) == ['common', 'special'], 'group profiles come first'
    assert profiles['special']['action'] == 'reload'
    assert profiles['common']['files'][0]['resolved_owner'] == '0:0'


def test_a_dangling_profile_assignment_does_not_break_the_rest(db, seed):
    """A profile deleted after assignment: the node still gets every profile that
    exists; the gap is logged, never silently fatal."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('real', _make('real'))
    _assign(db, 'node', seed['nodeid'], 'ghost', 'real')
    status, response = Profile().get_node_profiles('node001')
    assert status, response
    assert list(response['config']['profiles'].keys()) == ['real']


def test_an_ordinary_node_update_does_not_raise(db, seed):
    """A plain change to a node must survive the profile trigger. The name of a renamed
    node is only bound on the rename path, so reading it unconditionally raises on every
    update that is not a rename - and it raises inside the update, after writes."""
    from base.node import Node
    status, message = Node().update_node('node001', {'config': {'node': {
        'node001': {'comment': 'still here'}}}})
    assert status, message


def test_assigning_an_unknown_profile_is_rejected(db, seed):
    """The parallel list that must not silently drift: a profiles column may only
    name profiles that exist - same standard as roles' plugin check."""
    from base.group import Group
    status, message = Group().update_group('compute', {'config': {'group': {
        'compute': {'profiles': 'ghostprofile'}}}})
    assert not status
    assert 'ghostprofile' in message


# ---------------------------------------------------------------------------
# the install-time contract
# ---------------------------------------------------------------------------

def _template_function(name):
    with open(os.path.join(TEMPLATES, 'templ_install.cfg'), encoding='utf-8') as handle:
        lines = handle.read().splitlines()
    for index, line in enumerate(lines):
        if re.match(rf'^function {name}\s*\{{', line):
            body = []
            for following in lines[index + 1:]:
                if following == '}':
                    break
                body.append(following)
            return '\n'.join(body)
    raise AssertionError(f'{name} not found in templ_install.cfg')


@pytest.mark.skipif(shutil.which('bash') is None, reason='bash not available')
def test_installer_parse_extracts_profile_files_and_service(db, tmp_path):
    """The real boot payload through the real template extraction: files aligned,
    service and action recovered exactly."""
    from base.profile import Profile
    Profile().update_profile('munge', _make(files=[
        {'name': 'key', 'content': 'bXVuZ2VrZXk=', 'path': '/etc/munge/munge.key',
         'owner': 'root:root', 'mode': '400'},
        {'name': 'cfg', 'content': 'Y2ZnZGF0YQ==', 'path': '/etc/munge/cfg'},
    ]))
    status, response = Profile().get_boot_profile('munge')
    assert status, response
    json_file = tmp_path / 'node.profile.json'
    json_file.write_text(json.dumps(response))

    script = (f'function get_json_segment {{\n{_template_function("get_json_segment")}\n}}\n'
              f'function get_json_exact {{\n{_template_function("get_json_exact")}\n}}\n')

    def run(call):
        result = subprocess.run(['bash', '-c', script + call],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.split()

    # files come back ordered by the (profileid, name) index, not insertion order;
    # what matters is that path, owner and mode stay PAIRED row for row
    paths = run(f'get_json_segment {json_file} path')
    owners = run(f'get_json_exact {json_file} resolved_owner')
    modes = run(f'get_json_exact {json_file} mode')
    rows = set(zip(paths, owners, modes))
    assert rows == {('"/etc/munge/munge.key"', '"0:0"', '"400"'),
                    ('"/etc/munge/cfg"', '"0:0"', '"644"')}
    assert run(f'get_json_exact {json_file} service') == ['"munge"']
    assert run(f'get_json_exact {json_file} action') == ['"restart"']


def test_installer_applies_the_service_action():
    """The profile's service is a unit on the node: enabled in the image chroot,
    disabled for action 'stop', untouched for 'none'."""
    body = _template_function('node_profiles')
    assert 'systemctl enable ${SERVICE}' in body
    assert 'systemctl disable ${SERVICE}' in body
    assert re.search(r'none\)\s*\n\s*;;', body), "action 'none' must do nothing"
    assert 'chroot "/${rootmnt}"' in body


# ---------------------------------------------------------------------------
# live apply: enabled, the digest, and the three-state payload
# ---------------------------------------------------------------------------

def test_a_profile_with_no_enabled_value_is_enabled(db):
    """The column arrives NULL on every row that predates it. Read as disabled, an
    upgrade would freeze every existing profile in the cluster - and freezing is silent
    by design, so nothing would report that convergence had stopped."""
    from base.profile import Profile
    Profile().update_profile('legacy', _make('legacy'))
    row = db.get_record(table='profile', where='name = "legacy"')[0]
    assert row['enabled'] is None, 'this test is meaningless if the row carries a value'
    assert Profile().is_enabled(row) is True


def test_disabled_profile_travels_as_a_name_only(db, seed):
    """It must not simply vanish: the applier reclaims a path by finding it in its
    manifest and not in the payload, so silence would revert exactly the files that
    disabling is meant to leave alone."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('frozen', _make('frozen'))
    Profile().update_profile('live', _payload('live', service='sshd', action='reload',
        files=[{'name': 'x', 'content': 'eA==', 'path': '/etc/x'}]))
    _assign(db, 'node', seed['nodeid'], 'frozen', 'live')
    db.update('profile', Helper().make_rows({'enabled': 0}),
              [{"column": "name", "value": 'frozen'}])

    status, payload = Profile().node_payload('node001')
    assert status, payload
    assert [entry['name'] for entry in payload['profiles']] == ['live']
    assert payload['frozen'] == ['frozen']


def test_editing_a_disabled_profile_moves_nothing(db, seed):
    """No trigger when disabled: the digest carries a disabled profile's name, never its
    content, so changing what it holds cannot cause a delivery."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('frozen', _make('frozen'))
    _assign(db, 'node', seed['nodeid'], 'frozen')
    db.update('profile', Helper().make_rows({'enabled': 0}),
              [{"column": "name", "value": 'frozen'}])

    before = Profile().node_digest('node001')
    Profile().update_profile('frozen', _make('frozen', files=[
        {'name': 'key', 'content': 'Y29tcGxldGVseS1kaWZmZXJlbnQ=', 'path': '/etc/munge/munge.key'}]))
    assert Profile().node_digest('node001') == before


def test_flipping_enabled_does_move_the_digest(db, seed):
    """One delivery follows, which is what teaches the node to freeze those paths
    instead of reclaiming them on the next sweep."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    enabled = Profile().node_digest('node001')
    db.update('profile', Helper().make_rows({'enabled': 0}),
              [{"column": "name", "value": 'p'}])
    assert Profile().node_digest('node001') != enabled


def test_the_digest_is_stable_and_content_sensitive(db, seed):
    """Stable across calls, or every sweep would deliver to every node; sensitive to
    content, or an edit would never arrive."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    first = Profile().node_digest('node001')
    assert first == Profile().node_digest('node001')
    Profile().update_profile('p', _make('p', files=[
        {'name': 'key', 'content': 'bmV3Y29udGVudA==', 'path': '/etc/munge/munge.key'}]))
    assert Profile().node_digest('node001') != first


def test_order_is_part_of_the_digest(db, seed):
    """Order decides which profile wins a shared path, so swapping it is a real change."""
    from base.profile import Profile
    from utils.helper import Helper
    for name in ('a', 'b'):
        Profile().update_profile(name, _payload(name, service='', action='none',
            files=[{'name': 'f', 'content': 'eA==', 'path': '/etc/shared'}]))
    _assign(db, 'node', seed['nodeid'], 'a', 'b')
    one = Profile().node_digest('node001')
    _assign(db, 'node', seed['nodeid'], 'b', 'a')
    assert Profile().node_digest('node001') != one


def test_queueing_collapses_repeats(db, seed):
    """A change touching one node many times is one delivery: the queue returns the
    existing task for an identical task and param."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    for _ in range(5):
        Profile().queue_node('node001')
    queued = db.get_record(table='queue', where='subsystem = "profile"')
    assert len(queued) == 1, f'expected one task, found {len(queued)}'
    assert queued[0]['param'] == str(seed['nodeid'])


def test_queueing_a_profile_reaches_the_nodes_that_apply_it(db, seed):
    """Assignment is a comma list, so the match must be on the merged set: 'gpu' must
    not pick up a node carrying 'gpu-extra'."""
    from base.profile import Profile
    from utils.helper import Helper
    for name in ('gpu', 'gpu-extra'):
        Profile().update_profile(name, _make(name))
    other = db.insert('node', Helper().make_rows(
        {'name': 'node002', 'groupid': seed['groupid']}))
    _assign(db, 'node', other, 'gpu-extra')
    _assign(db, 'node', seed['nodeid'], 'gpu')
    Profile().queue_profile('gpu')
    queued = [row['param'] for row in db.get_record(table='queue', where='subsystem = "profile"')]
    assert queued == [str(seed['nodeid'])], f'queued {queued}'


def test_member_lists_who_applies_a_profile(db, seed):
    """The same question the deletion guard asks, answered for a human: an operator who
    cannot delete a profile should be able to see what is holding it."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('shared', _make('shared'))
    _assign(db, 'group', seed['groupid'], 'shared')
    lone = db.insert('node', Helper().make_rows(
        {'name': 'node009', 'groupid': seed['groupid'], 'profiles': 'shared'}))
    status, response = Profile().get_profile_member('shared')
    assert status, response
    members = response['config']['profiles']['shared']['members']
    assert members['groups'] == ['compute']
    assert members['nodes'] == ['node009']


def test_member_on_an_unknown_profile_says_so(db):
    from base.profile import Profile
    status, message = Profile().get_profile_member('ghost')
    assert not status
    assert 'not available' in message


def test_changing_one_file_attribute_keeps_the_rest(db):
    """A change carries only what is changing. Demanding the content back just to alter
    a mode makes every caller re-send a secret it had no reason to touch."""
    from base.profile import Profile
    Profile().update_profile('p', _make('p', files=[
        {'name': 'key', 'content': 'a2VlcG1l', 'path': '/etc/key', 'mode': '644'}]))
    status, message = Profile().update_profile('p', _payload('p', files=[
        {'name': 'key', 'mode': '600'}]))
    assert status, message
    _, response = Profile().get_profile('p')
    entry = response['config']['profiles']['p']['files'][0]
    assert entry['mode'] == '600'
    assert entry['content'] == 'a2VlcG1l', 'the untouched content did not survive'
    assert entry['path'] == '/etc/key'


def test_a_new_file_still_needs_content_and_path(db):
    """Tolerating a partial change must not let a file be created empty."""
    from base.profile import Profile
    Profile().update_profile('p', _make('p'))
    status, message = Profile().update_profile('p', _payload('p', files=[
        {'name': 'brandnew', 'mode': '600'}]))
    assert not status
    assert 'not complete' in message


def test_a_finished_install_does_not_block_delivery(db, seed):
    """install.booted and install.success are where an install STOPS, and they stay on
    the record for the rest of the node's life. Testing the 'install.' prefix alone
    excludes every successfully installed node in the cluster - quietly, because the
    node simply never gets delivered to."""
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    from utils.dbstructure import DBStructure
    db.create('monitor', DBStructure().get_database_table_structure('monitor'))
    for state, blocked in (('install.booted', False), ('install.success', False),
                           ('install.unpack', True), ('install.profiles', True)):
        db.delete_row('monitor', [{"column": "tablerefid", "value": seed['nodeid']}])
        db.insert('monitor', Helper().make_rows(
            {'tableref': 'node', 'tablerefid': seed['nodeid'], 'state': state}))
        reason = ProfileSync().skip_reason('node001')
        assert bool(reason) is blocked, f'{state} gave {reason!r}'


def test_a_node_with_no_profiles_still_gets_a_payload(db, seed):
    """The most important delivery of all: unassigning the last profile is exactly when
    the node has to be told, so it can put back what the profile displaced. Treating an
    empty set as nothing-to-do leaves those files on the node for good."""
    from base.profile import Profile
    status, payload = Profile().node_payload('node001')
    assert status, 'a node with no profiles must still be deliverable'
    assert payload['profiles'] == [] and payload['frozen'] == []
    assert Profile().node_digest('node001'), 'an empty set still needs a digest'


def test_the_empty_digest_differs_from_a_populated_one(db, seed):
    from base.profile import Profile
    from utils.helper import Helper
    empty = Profile().node_digest('node001')
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    assert Profile().node_digest('node001') != empty


def test_the_delivery_transport_bounds_itself(db):
    """Helper().runcommand takes a timeout, but it runs under a shell and kills only
    that shell: an rsync and its ssh child outlive it, hold the pipes open, and the read
    that was meant to be bounded blocks anyway. Verified against a black-holed address -
    the kill left both processes running. So the transport carries its own limits.

    --contimeout is deliberately absent: it applies only to an rsync daemon and is a
    usage error over ssh, which would fail every delivery instantly."""
    import os
    plugin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'daemon', 'plugins', 'profile', 'delivery', 'default.py')
    with open(plugin, encoding='utf-8') as handle:
        source = handle.read()
    assert 'ConnectTimeout' in source, 'nothing bounds the connect phase'
    assert '--timeout=' in source, 'nothing bounds a stalled transfer'
    assert 'ServerAliveInterval' in source, 'nothing notices a peer that goes quiet'
    assert '--contimeout=' not in source, \
        '--contimeout is an rsync-daemon option; over ssh it is a usage error'
    assert 'BatchMode=yes' in source, 'a prompt would hang the worker'


# ---------------------------------------------------------------------------
# phase two: the reconciler
# ---------------------------------------------------------------------------

def _reconcile_db(db):
    """The tables the sweep reads."""
    from utils.dbstructure import DBStructure
    for table in ['monitor']:
        db.create(table, DBStructure().get_database_table_structure(table))


def test_a_cluster_with_no_profiles_is_left_alone(db, seed):
    """The trap in a sweep like this: a node that has never been delivered to differs
    from an empty digest, so every node in a cluster where nobody uses profiles would
    look out of line - and the sweep would connect to all of them to deliver nothing."""
    from utils.profile_sync import ProfileSync
    _reconcile_db(db)
    assert ProfileSync().nodes_behind() == []


def test_a_node_with_a_profile_and_no_delivery_is_behind(db, seed):
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001']


def test_a_node_already_in_line_is_not_touched(db, seed):
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    db.update('node', Helper().make_rows(
        {'profiles_digest': Profile().node_digest('node001')}),
        [{"column": "id", "value": seed['nodeid']}])
    assert ProfileSync().nodes_behind() == []


def test_a_node_whose_profile_changed_falls_behind_again(db, seed):
    """The sweep is what notices a delivery that never happened - an edit made while a
    node was unreachable, for instance."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    db.update('node', Helper().make_rows(
        {'profiles_digest': Profile().node_digest('node001')}),
        [{"column": "id", "value": seed['nodeid']}])
    Profile().update_profile('p', _make('p', files=[
        {'name': 'key', 'content': 'Y2hhbmdlZA==', 'path': '/etc/munge/munge.key'}]))
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001']


def test_a_node_that_had_profiles_removed_is_behind_until_told(db, seed):
    """Unassigning is a change like any other: the node holds files it should not, and
    it stays out of line until it has been told to put them back."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    db.update('node', Helper().make_rows(
        {'profiles': 'p', 'profiles_digest': 'whatever-it-had'}),
        [{"column": "id", "value": seed['nodeid']}])
    db.update('node', Helper().make_rows({'profiles': ''}),
              [{"column": "id", "value": seed['nodeid']}])
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001']


def test_an_installing_node_is_not_queued_by_the_sweep(db, seed):
    """It would be skipped at delivery anyway; queueing it only churns."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    db.insert('monitor', Helper().make_rows(
        {'tableref': 'node', 'tablerefid': seed['nodeid'], 'state': 'install.unpack'}))
    assert ProfileSync().nodes_behind() == []


def test_the_sweep_queues_what_it_finds(db, seed):
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    assert [name for _, name in ProfileSync().reconcile()] == ['node001']
    queued = db.get_record(table='queue', where='subsystem = "profile"')
    assert [row['param'] for row in queued] == [str(seed['nodeid'])], \
        'the task must carry the id: a name can change before the delivery runs'


def test_a_rename_between_queueing_and_delivery_still_lands(db, seed):
    """The reason the task carries an id. A node can be renamed while a delivery is
    queued - or during the five minutes before a retry - and a task naming the old name
    would look for a node that no longer answers to it."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    from utils.dbstructure import DBStructure
    db.create('monitor', DBStructure().get_database_table_structure('monitor'))
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    Profile().queue_node('node001')
    queued = db.get_record(table='queue', where='subsystem = "profile"')[0]

    db.update('node', Helper().make_rows({'name': 'renamed001'}),
              [{"column": "id", "value": seed['nodeid']}])

    assert queued['param'] != 'node001', 'the task carried a name, which can change'
    # the task still identifies the node, under whatever name it now has
    found = db.get_record(table='node', where=f'id = "{queued["param"]}"')
    assert found and found[0]['name'] == 'renamed001'
    # and a delivery driven from that task gets past resolution rather than failing on it
    status, message = ProfileSync().deliver_node(queued['param'])
    assert 'is not available' not in str(message), \
        f'the queued task could not find the renamed node: {message}'


# ---------------------------------------------------------------------------
# phase three: the status view
# ---------------------------------------------------------------------------

def _status_db(db):
    from utils.dbstructure import DBStructure
    for table in ['monitor']:
        db.create(table, DBStructure().get_database_table_structure(table))


def test_status_says_not_applied_for_an_uninvolved_node(db, seed):
    from base.profile import Profile
    _status_db(db)
    status, response = Profile().status()
    assert status, response
    assert response['config']['profiles']['status']['node001']['state'] == 'not applied'


def test_status_says_behind_then_in_sync(db, seed):
    from base.profile import Profile
    from utils.helper import Helper
    _status_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    _, response = Profile().status('node001')
    assert response['config']['profiles']['status']['node001']['state'] == 'behind'

    db.update('node', Helper().make_rows(
        {'profiles_digest': Profile().node_digest('node001')}),
        [{"column": "id", "value": seed['nodeid']}])
    _, response = Profile().status('node001')
    entry = response['config']['profiles']['status']['node001']
    assert entry['state'] == 'in sync'
    assert entry['profiles'] == 'p'


def test_status_reports_a_failure_with_its_reason(db, seed):
    """A sweep failing quietly on a dozen nodes is worse than no sweep. The reason has
    to be answerable without reading a log."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _status_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    ProfileSync().record_outcome(seed['nodeid'], False, 'could not copy the bundle: timed out')
    _, response = Profile().status('node001')
    entry = response['config']['profiles']['status']['node001']
    assert entry['state'] == 'failed'
    assert 'timed out' in entry['detail']
    assert entry['since']


def test_a_success_clears_a_previous_failure(db, seed):
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _status_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    ProfileSync().record_outcome(seed['nodeid'], False, 'boom')
    ProfileSync().record_outcome(seed['nodeid'], True, 'delivered')
    db.update('node', Helper().make_rows(
        {'profiles_digest': Profile().node_digest('node001')}),
        [{"column": "id", "value": seed['nodeid']}])
    _, response = Profile().status('node001')
    assert response['config']['profiles']['status']['node001']['state'] == 'in sync'


def test_status_marks_a_node_carrying_a_frozen_profile(db, seed):
    """In sync, but holding files Luna no longer manages. That is neither drift nor an
    error, and an operator should not have to remember it."""
    from base.profile import Profile
    from utils.helper import Helper
    _status_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    db.update('profile', Helper().make_rows({'enabled': 0}),
              [{"column": "name", "value": 'p'}])
    db.update('node', Helper().make_rows(
        {'profiles_digest': Profile().node_digest('node001')}),
        [{"column": "id", "value": seed['nodeid']}])
    entry = Profile().status('node001')[1]['config']['profiles']['status']['node001']
    assert entry['state'] == 'frozen'
    assert entry['frozen'] == 'p'


def test_a_node_that_just_failed_is_left_alone_for_a_while(db, seed):
    """Measured on a live pair: a thousand unreachable nodes take about twelve minutes
    to work through. Re-queueing them every five would leave the worker permanently
    busy, and a legitimate delivery would wait behind a cluster that is switched off."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001']

    ProfileSync().record_outcome(seed['nodeid'], False, 'could not reach it')
    assert ProfileSync().nodes_behind() == [], 'a node that just failed was queued again'


def test_a_node_that_succeeded_is_not_held_back(db, seed):
    """The cool-off applies to failures only: a node that was delivered to and has since
    drifted must be picked up at once."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    ProfileSync().record_outcome(seed['nodeid'], True, 'delivered')
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001']


def test_a_node_that_is_installing_has_not_failed(db, seed):
    """It is not ready, which is not the same as broken. Recording it as a failure puts
    it in the failed column of the status view and sends somebody chasing a problem that
    does not exist - and on a cluster mid-boot that is most of the cluster."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    db.insert('monitor', Helper().make_rows(
        {'tableref': 'node', 'tablerefid': seed['nodeid'], 'state': 'install.unpack'}))
    status, message = ProfileSync().deliver_node(seed['nodeid'])
    assert status is None, 'a deferred delivery must not read as a failure'
    assert 'installing' in message


def test_a_profile_with_neither_files_nor_a_service_is_rejected(db):
    """It would write nothing and act on nothing, while sitting in the assignment lists
    looking like configuration."""
    from base.profile import Profile
    status, message = Profile().update_profile('empty', _payload('empty', scope='static'))
    assert not status
    assert 'needs either a service' in message
    assert not db.get_record(table='profile', where='name = "empty"'), \
        'the profile the rejection says should not exist was created anyway'


def test_a_service_only_profile_is_allowed(db):
    """A profile can be nothing but a service to act on."""
    from base.profile import Profile
    status, message = Profile().update_profile('justaservice', _payload(
        'justaservice', service='sshd', action='restart'))
    assert status, message


def test_a_file_only_profile_is_allowed(db):
    """And it can be files with no service at all."""
    from base.profile import Profile
    status, message = Profile().update_profile('justfiles', _payload('justfiles', files=[
        {'name': 'f', 'content': 'eA==', 'path': '/etc/f'}]))
    assert status, message


def test_adding_a_service_later_to_a_file_only_profile_still_works(db):
    """The check must look at what the profile WILL be, not only at what the request
    carries: a change that supplies a service alone is fine when files already exist."""
    from base.profile import Profile
    Profile().update_profile('p', _payload('p', files=[
        {'name': 'f', 'content': 'eA==', 'path': '/etc/f'}]))
    status, message = Profile().update_profile('p', _payload('p', service='cron'))
    assert status, message


def _seed_failures(db, nodeid, count):
    """A node that has failed `count` times running, with its cool-off already expired so
    only the give-up decision is under test."""
    from datetime import datetime, timedelta
    from utils.helper import Helper
    from utils.profile_sync import ProfileSync
    ProfileSync().record_outcome(nodeid, False, 'could not reach it')
    old = (datetime.utcnow() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    db.update('monitor', Helper().make_rows({'state': f'failed {count}', 'updated': old}),
              [{"column": "tableref", "value": 'nodeprofile'},
               {"column": "tablerefid", "value": nodeid}])


def _owes_a_profile(db, seed):
    """A node with a profile assigned and nothing delivered: behind, by definition."""
    from base.profile import Profile
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')


def test_a_node_that_keeps_failing_is_eventually_given_up_on(db, seed):
    """Retrying something that has refused for a day costs a worker slot every five
    minutes forever and buries the nodes that can still be fixed."""
    from base.profile import Profile, MAX_ATTEMPTS
    from utils.profile_sync import ProfileSync
    _owes_a_profile(db, seed)
    _seed_failures(db, seed['nodeid'], MAX_ATTEMPTS)
    assert Profile().given_up(seed['nodeid']) == MAX_ATTEMPTS
    assert ProfileSync().nodes_behind() == [], 'a node we gave up on was queued again'


def test_giving_up_takes_a_whole_day_of_attempts(db, seed):
    """One attempt short it is an ordinary failure and must keep being retried."""
    from base.profile import Profile, MAX_ATTEMPTS
    from utils.profile_sync import ProfileSync
    _owes_a_profile(db, seed)
    _seed_failures(db, seed['nodeid'], MAX_ATTEMPTS - 1)
    assert not Profile().given_up(seed['nodeid'])
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001'], \
        'a node still inside the day was written off early'


def test_a_day_is_what_the_retry_interval_makes_it(db):
    """The count is only a stand-in for time. If the retry interval changes and the count
    does not follow it, the day quietly becomes a week."""
    from base.profile import GIVE_UP_HOURS, MAX_ATTEMPTS, RETRY_SECONDS
    assert MAX_ATTEMPTS * RETRY_SECONDS == GIVE_UP_HOURS * 3600


def test_each_failure_counts_and_a_success_forgets_them_all(db, seed):
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    _reconcile_db(db)
    for expected in (1, 2, 3):
        ProfileSync().record_outcome(seed['nodeid'], False, 'could not reach it')
        assert Profile().failed_attempts(seed['nodeid']) == expected
    ProfileSync().record_outcome(seed['nodeid'], True, 'delivered')
    assert Profile().failed_attempts(seed['nodeid']) == 0, \
        'the count outlived the failures it was counting'


def test_changing_a_profile_gives_a_given_up_node_another_chance(db, seed):
    """Otherwise a node written off yesterday would ignore everything asked of it today,
    and the only way back would be a reboot."""
    from base.profile import Profile, MAX_ATTEMPTS
    from utils.profile_sync import ProfileSync
    _owes_a_profile(db, seed)
    # written off, and inside a fresh cool-off: clearing only one of the two would leave
    # it sitting there just as quietly
    _seed_failures(db, seed['nodeid'], MAX_ATTEMPTS)
    ProfileSync().record_outcome(seed['nodeid'], False, 'still cannot reach it')
    Profile().queue_node(nodeid=seed['nodeid'])
    assert not Profile().given_up(seed['nodeid'])
    assert [name for _, name in ProfileSync().nodes_behind()] == ['node001'], \
        'the node stayed written off after somebody changed what it should have'


def test_a_given_up_node_is_not_delivered_to(db, seed):
    """A task queued before we gave up can still be claimed afterwards, and it must not
    turn into a connection attempt."""
    from base.profile import MAX_ATTEMPTS
    from utils.profile_sync import ProfileSync
    _owes_a_profile(db, seed)
    _seed_failures(db, seed['nodeid'], MAX_ATTEMPTS)
    status, message = ProfileSync().deliver_node(seed['nodeid'])
    assert status is None, 'giving up must not read as a fresh failure'
    assert 'given up' in message


def test_a_given_up_node_says_so_and_says_how_often_it_tried(db, seed):
    """Silence would be the worst outcome of the whole feature: a node that is not being
    chased and does not look any different from one that is."""
    from base.profile import Profile, MAX_ATTEMPTS
    _status_db(db)
    _owes_a_profile(db, seed)
    _seed_failures(db, seed['nodeid'], MAX_ATTEMPTS)
    _, response = Profile().status('node001')
    entry = response['config']['profiles']['status']['node001']
    assert entry['state'] == 'given up'
    assert entry['attempts'] == MAX_ATTEMPTS
    assert 'could not reach it' in entry['detail']


def test_a_pending_retry_delivers_the_profile_as_it_is_now(db, seed):
    """A retry queued yesterday for a node that was down must carry today's profile. The
    task holds an id and nothing else, so the payload is built at delivery time - if it
    ever carried the content instead, a node coming back would be handed the very state
    the operator has since changed."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('p', _make('p'))
    _assign(db, 'node', seed['nodeid'], 'p')
    Profile().queue_node(nodeid=seed['nodeid'])
    stale = Profile().node_digest('node001')

    Profile().update_profile('p', _payload('p', files=[
        {'name': 'f', 'content': 'Y2hhbmdlZAo=', 'path': '/etc/f'}]))
    bundle, digest = ProfileSync().build_bundle('node001')
    assert digest != stale, 'the delivery would have carried the superseded profile'
    assert digest == Profile().node_digest('node001')
    import json, os, shutil
    with open(os.path.join(bundle, 'payload.json'), encoding='utf-8') as handle:
        payload = json.load(handle)
    shutil.rmtree(bundle, ignore_errors=True)
    contents = [entry['content'] for profile in payload['profiles']
                for entry in profile['files']]
    import base64
    assert any(b'changed' in base64.b64decode(item) for item in contents)


def test_deleting_a_node_takes_its_delivery_record_with_it(db, seed):
    """Nothing will ever read it again, and it would refer to a node that is gone for the
    life of the cluster."""
    from base.profile import Profile
    from utils.profile_sync import ProfileSync
    _reconcile_db(db)
    ProfileSync().record_outcome(seed['nodeid'], False, 'could not reach it')
    Profile().clear_outcome(seed['nodeid'])
    assert not db.get_record(table='monitor',
                             where=f'tablerefid = "{seed["nodeid"]}" AND '
                                   'tableref = "nodeprofile"')


def test_removing_the_last_file_of_a_service_less_profile_is_refused(db):
    """It would leave a profile that writes nothing and acts on nothing - the very state
    the create path refuses - still sitting in the assignment lists looking like
    configuration. The invariant has to hold from both directions."""
    from base.profile import Profile
    Profile().update_profile('lonely', _payload('lonely', scope='static', files=[
        {'name': 'only', 'content': 'eA==', 'path': '/etc/only'}]))
    status, message = Profile().delete_profile_file('lonely', 'only')
    assert not status
    assert 'last file' in message
    assert db.get_record(table='profilefile', where='name = "only"'), 'it was deleted anyway'


def test_the_last_file_can_go_when_a_service_remains(db):
    """With a service to act on, a profile with no files is still a profile."""
    from base.profile import Profile
    Profile().update_profile('svc', _payload('svc', scope='static', service='cron',
                                             action='reload', files=[
        {'name': 'only', 'content': 'eA==', 'path': '/etc/only'}]))
    status, message = Profile().delete_profile_file('svc', 'only')
    assert status, message
    assert not db.get_record(table='profilefile', where='name = "only"')


def test_a_service_can_be_cleared_while_files_remain(db):
    """Clearing the service is a legitimate change - it just cannot be the last thing the
    profile had."""
    from base.profile import Profile
    Profile().update_profile('both', _payload('both', scope='static', service='cron',
                                              action='reload', files=[
        {'name': 'f', 'content': 'eA==', 'path': '/etc/f'}]))
    status, message = Profile().update_profile('both', _payload('both', service='', action=''))
    assert status, message
    row = db.get_record(table='profile', where='name = "both"')[0]
    assert not row['service'] and not row['action']


def test_clearing_the_service_of_a_file_less_profile_is_refused(db):
    """Nothing would be left. Same invariant, reached from the other side."""
    from base.profile import Profile
    Profile().update_profile('svconly', _payload('svconly', scope='static',
                                                 service='cron', action='reload'))
    status, message = Profile().update_profile('svconly', _payload('svconly', service=''))
    assert not status
    assert 'needs either a service' in message
    assert db.get_record(table='profile', where='name = "svconly"')[0]['service'] == 'cron', \
        'the service was cleared anyway'


def test_renaming_a_profile_carries_its_assignments(db, seed):
    """A profile is named in node.profiles and group.profiles rather than linked by id -
    the one place Luna stores a name as the reference - so a rename that does not move
    the assignments leaves every one of them pointing at nothing."""
    from base.profile import Profile
    from utils.helper import Helper
    Profile().update_profile('ntp', _make('ntp'))
    _assign(db, 'group', seed['groupid'], 'ntp')
    _assign(db, 'node', seed['nodeid'], 'ntp')

    before = db.get_record(table='group', where=f'id = "{seed["groupid"]}"')[0]['profiles']
    assert before and before.isdigit(), 'the assignment should hold a reference, not a name'
    status, message = Profile().update_profile('ntp', _payload('ntp', newprofilename='chrony'))
    assert status, message
    assert db.get_record(table='profile', where='name = "chrony"')
    assert not db.get_record(table='profile', where='name = "ntp"')
    # the assignment is untouched, which is the whole point: it never held the name
    assert db.get_record(table='group', where=f'id = "{seed["groupid"]}"')[0]['profiles'] == before
    assert Profile().merged_profiles(seed['nodeid']) == 'chrony'
    assert Profile().assigned_to('chrony') == ['compute', 'node001']


def test_a_rename_leaves_the_other_assignments_alone(db, seed):
    """The reassignment rewrites a list that holds other profiles too, and a whole-name
    match is the only thing standing between 'gpu' and a node carrying 'gpu-extra'."""
    from base.profile import Profile
    from utils.helper import Helper
    for profile in ('gpu', 'gpu-extra', 'munge'):
        Profile().update_profile(profile, _make(profile))
    _assign(db, 'node', seed['nodeid'], 'munge', 'gpu', 'gpu-extra')
    status, message = Profile().update_profile('gpu', _payload('gpu', newprofilename='nvidia'))
    assert status, message
    assert Profile().merged_profiles(seed['nodeid']) == 'munge,nvidia,gpu-extra', \
        'the rename disturbed a neighbour it should not have touched'
    assert Profile().assigned_to('gpu-extra') == ['node001'], 'a lookalike lost its assignment'


def test_renaming_onto_an_existing_profile_is_refused(db):
    """Two profiles of one name is not a state the assignment lists can express."""
    from base.profile import Profile
    Profile().update_profile('one', _make('one'))
    Profile().update_profile('two', _make('two'))
    status, message = Profile().update_profile('one', _payload('one', newprofilename='two'))
    assert not status
    assert 'already present' in message
    assert db.get_record(table='profile', where='name = "one"'), 'the source was renamed anyway'


def test_renaming_something_that_does_not_exist_says_so(db):
    """It must not create, and it must not blame the caller for a create they did not
    ask for: a rename of a mistyped name should point at the name that is missing."""
    from base.profile import Profile
    status, message = Profile().update_profile('ghost', _payload(
        'ghost', scope='static', service='cron', action='reload', newprofilename='spectre'))
    assert not status
    assert message == 'Profile ghost is not available'
    assert not db.get_record(table='profile'), 'a profile was created by a rename'


def test_a_renamed_profile_is_redelivered(db, seed):
    """The node-side manifest records which profile each file came from, so a rename is a
    real change on the node even though no content moved."""
    from base.profile import Profile
    from utils.helper import Helper
    _reconcile_db(db)
    Profile().update_profile('ntp', _make('ntp'))
    _assign(db, 'node', seed['nodeid'], 'ntp')
    before = Profile().node_digest('node001')
    Profile().update_profile('ntp', _payload('ntp', newprofilename='chrony'))
    assert Profile().node_digest('node001') != before
    queued = db.get_record(table='queue', where='subsystem = "profile"')
    assert [row['param'] for row in queued] == [str(seed['nodeid'])]


def test_the_api_takes_names_and_stores_references(db, seed):
    """Names belong at the boundary: a human types 'ntp', and what is stored is the
    profile it meant. Storing the name is what made a rename a bookkeeping exercise
    across every node and group that carried it."""
    from base.node import Node
    from base.profile import Profile
    Profile().update_profile('ntp', _make('ntp'))
    profileid = db.get_record(table='profile', where='name = "ntp"')[0]['id']

    status, message = Node().update_node('node001', {'config': {'node': {'node001': {
        'profiles': 'ntp'}}}})
    assert status, message
    stored = db.get_record(table='node', where=f'id = "{seed["nodeid"]}"')[0]['profiles']
    assert stored == str(profileid), f'the assignment stored {stored!r}, not the reference'


def test_what_a_node_reports_is_names_not_numbers(db, seed):
    """And the other direction: an operator reading 'luna node show' must see what the
    profile is called, not the number it is stored as."""
    from base.node import Node
    from base.profile import Profile
    Profile().update_profile('ntp', _make('ntp'))
    Node().update_node('node001', {'config': {'node': {'node001': {'profiles': 'ntp'}}}})
    status, response = Node().get_node('node001')
    assert status, response
    assert response['config']['node']['node001']['profiles'] == 'ntp'


def test_profile_work_queued_on_a_non_master_is_dropped(db, seed):
    """The journal replays the requests that queue this work, so tasks land on the
    secondary too - where the mother must not act on them. Left alone they are never
    claimed, never reaped and never expire: the selection window stops them being
    picked up, it does not remove them. They would sit in the table for the life of
    the cluster, one per node per change."""
    from utils.profile_sync import ProfileSync
    from utils.queue import Queue
    _reconcile_db(db)
    Queue().add_task_to_queue(task='sync_profiles', param=str(seed['nodeid']),
                              subsystem='profile')
    assert db.get_record(table='queue', where='subsystem = "profile"')
    ProfileSync().drop_queued()
    assert not db.get_record(table='queue', where='subsystem = "profile"'), \
        'work the controller must not do was left in its queue'


def test_dropping_leaves_other_subsystems_alone(db, seed):
    """It is one queue table shared by every subsystem."""
    from utils.profile_sync import ProfileSync
    from utils.queue import Queue
    _reconcile_db(db)
    Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper')
    Queue().add_task_to_queue(task='sync_profiles', param=str(seed['nodeid']),
                              subsystem='profile')
    ProfileSync().drop_queued()
    remaining = db.get_record(table='queue')
    assert [row['subsystem'] for row in remaining] == ['housekeeper']
