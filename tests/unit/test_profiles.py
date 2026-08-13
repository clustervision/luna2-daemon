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
    for table in ['node', 'group', 'profile', 'profilefile', 'ownercache']:
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
        Profile().update_profile(name, _payload(name, service='', action='none'))
    db.update('group', Helper().make_rows({'profiles': 'common,gpu'}),
              [{"column": "id", "value": seed['groupid']}])
    db.update('node', Helper().make_rows({'profiles': 'special,common'}),
              [{"column": "id", "value": seed['nodeid']}])
    assert Profile().merged_profiles(seed['nodeid']) == 'common,gpu,special'


def test_a_node_without_a_group_still_gets_its_own_profiles(db):
    from base.profile import Profile
    from utils.helper import Helper
    nodeid = db.insert('node', Helper().make_rows({'name': 'lone', 'profiles': 'solo'}))
    Profile().update_profile('solo', _payload('solo', service='', action='none'))
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
    db.update('group', Helper().make_rows({'profiles': 'common'}),
              [{"column": "id", "value": seed['groupid']}])
    db.update('node', Helper().make_rows({'profiles': 'special'}),
              [{"column": "id", "value": seed['nodeid']}])
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
    db.update('node', Helper().make_rows({'profiles': 'ghost,real'}),
              [{"column": "id", "value": seed['nodeid']}])
    status, response = Profile().get_node_profiles('node001')
    assert status, response
    assert list(response['config']['profiles'].keys()) == ['real']


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
