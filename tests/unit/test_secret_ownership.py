#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
TRIX-1209 unit tests: secrets carry file ownership and permissions.

A secret is a file the installer writes into the image, and until now every one of
them landed as root 600. The owner/mode columns let a secret say whose file it is.
Two things make that harder than it looks, and these tests pin both:

* The installer's chroot cannot resolve directory (ldap/sssd) users -- there is no
  directory inside a half-built image. So the daemon resolves names to numbers on
  the controller (through glibc NSS, the same stack getent uses) and the installer
  chowns numerically. Resolution is cached in memory against install storms, and the
  last good answer is stored in ownercache so a directory outage at install time
  degrades to slightly-stale numbers instead of a failed chown.

* The install-time JSON parser is a positional token stream. It cannot carry empty
  values, so unset attributes travel as the defaults the installer would have applied
  anyway; and a loose key match would false-hit base64 content containing the key
  name, so the owner/mode extraction matches keys exactly.
"""

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
    """A fresh, isolated SQLite database with the secrets-relevant tables created."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    Helper.owner_cache = {}     # the 60s memory cache must not bleed between tests
    for table in ['node', 'group', 'nodesecrets', 'groupsecrets', 'ownercache']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None
    Helper.owner_cache = {}


@pytest.fixture
def seed(db):
    """A node in a group; returns their ids."""
    from utils.helper import Helper
    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    nodeid = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    return {'groupid': groupid, 'nodeid': nodeid}


def _post_node_secret(name, secret):
    from base.secret import Secret
    payload = {'config': {'secrets': {'node': {name: [secret]}}}}
    return Secret().update_node_secret(name, secret['name'], payload)


def test_secrets_tables_carry_the_same_file_attributes():
    """nodesecrets and groupsecrets describe the same thing scoped differently; their
    file attributes must never drift apart -- an owner settable on one scope only
    would be a false statement about what secrets can do."""
    from utils.dbstructure import DBStructure
    per_table = {}
    for table, ref in (('nodesecrets', 'nodeid'), ('groupsecrets', 'groupid')):
        layout = DBStructure().get_database_table_structure(table)
        per_table[table] = {c['column'] for c in layout} - {'id', ref}
    assert per_table['nodesecrets'] == per_table['groupsecrets']
    assert {'owner', 'mode'} <= per_table['nodesecrets']


def test_owner_and_mode_survive_the_round_trip(db, seed):
    from base.secret import Secret
    status, message = _post_node_secret('node001', {
        'name': 'keytab', 'content': 'c2VjcmV0', 'path': '/etc/krb5.keytab',
        'owner': 'root:root', 'mode': '640'})
    assert status, message
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    row = response['config']['secrets']['node']['node001'][0]
    assert row['owner'] == 'root:root'
    assert row['mode'] == '640'
    assert row['resolved_owner'] == '0:0'


def test_unset_attributes_travel_as_the_effective_defaults(db, seed):
    """The installer's parser cannot carry empty values, and unset means what it
    always meant: root's file, 600."""
    from base.secret import Secret
    status, message = _post_node_secret('node001', {
        'name': 'plain', 'content': 'c2VjcmV0', 'path': '/etc/plain'})
    assert status, message
    stored = db.get_record(table='nodesecrets', where='name = "plain"')[0]
    assert stored['owner'] is None and stored['mode'] is None, \
        'defaults must be applied at fetch time, never written into the row'
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    row = response['config']['secrets']['node']['node001'][0]
    assert (row['owner'], row['mode'], row['resolved_owner']) == ('root:root', '600', '0:0')


def test_group_secrets_get_the_same_treatment(db, seed):
    from base.secret import Secret
    payload = {'config': {'secrets': {'group': {'compute': [
        {'name': 'shared', 'content': 'c2VjcmV0', 'path': '/etc/shared',
         'owner': 'root', 'mode': '400'}]}}}}
    status, message = Secret().update_group_secret('compute', 'shared', payload)
    assert status, message
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    row = response['config']['secrets']['group']['compute'][0]
    assert (row['owner'], row['mode'], row['resolved_owner']) == ('root', '400', '0')


def test_resolve_owner_returns_numbers_for_known_names(db):
    from utils.helper import Helper
    assert Helper().resolve_owner('root:root') == '0:0'
    assert Helper().resolve_owner('root') == '0'
    assert Helper().resolve_owner('12:34') == '12:34'


def test_resolve_owner_falls_back_to_the_stored_resolution(db):
    """A directory outage at install time must degrade to the last known numbers,
    not to a chown that cannot work."""
    from utils.helper import Helper
    db.insert('ownercache', Helper().make_rows(
        {'name': 'ghostuser:ghostgroup', 'resolved': '4242:4242', 'updated': 'NOW'}))
    assert Helper().resolve_owner('ghostuser:ghostgroup') == '4242:4242'


def test_resolve_owner_passes_unknown_names_through(db):
    """Never resolved, nothing stored: the name itself is still the best answer --
    the image may know a local user the controller does not."""
    from utils.helper import Helper
    assert Helper().resolve_owner('ghostuser:ghostgroup') == 'ghostuser:ghostgroup'


def test_resolve_owner_corrects_a_stale_stored_resolution(db):
    """The stored value is a fallback, not an authority: a live answer wins and
    rewrites it (this is the write-on-change the housekeeper refresh relies on)."""
    from utils.helper import Helper
    db.insert('ownercache', Helper().make_rows(
        {'name': 'root:root', 'resolved': '999:999', 'updated': 'NOW'}))
    assert Helper().resolve_owner('root:root') == '0:0'
    stored = db.get_record(table='ownercache', where='name = "root:root"')
    assert stored[0]['resolved'] == '0:0'


def test_update_warns_when_an_owner_does_not_resolve(db, seed):
    """The typo is caught where the human is looking: in the API reply, at write
    time. Stored anyway -- the owner may exist only inside the image."""
    status, message = _post_node_secret('node001', {
        'name': 'typo', 'content': 'c2VjcmV0', 'path': '/etc/typo',
        'owner': 'ghostuser:ghostgroup', 'mode': '600'})
    assert status, message
    assert 'Warning' in message and 'ghostuser:ghostgroup' in message
    assert db.get_record(table='nodesecrets', where='name = "typo"'), \
        'an unresolvable owner is a warning, not a rejection'


def test_the_boundary_accepts_a_numeric_owner():
    """The documented escape hatch for a controller without directory access is to
    supply the ids directly - so the API boundary must let numbers through. It did
    not, and the warning pointed at an alternative the validation then rejected."""
    import re
    from common.validate_input import REG_EXP
    pattern = re.compile(REG_EXP['fileowner']['regexp'])
    for owner in ('1050', '1050:1051', 'ldapuser:1051', '1050:ldapgroup',
                  'ldapuser', 'ldapuser:ldapgroup', ''):
        assert pattern.match(owner), f'valid owner form rejected: {owner!r}'
    for owner in (':1051', '10.50', 'user:', '-user'):
        assert not pattern.match(owner), f'invalid owner form accepted: {owner!r}'


def test_numeric_owner_round_trip(db, seed):
    """A numeric owner needs no resolution anywhere: stored, emitted and chowned
    as the numbers the user supplied."""
    from base.secret import Secret
    status, message = _post_node_secret('node001', {
        'name': 'numeric', 'content': 'c2VjcmV0', 'path': '/etc/numeric',
        'owner': '1050:1051', 'mode': '640'})
    assert status, message
    assert 'Warning' not in message, 'numeric ids are never unresolvable'
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    row = response['config']['secrets']['node']['node001'][0]
    assert row['resolved_owner'] == '1050:1051'


def test_a_hanging_directory_does_not_hang_the_install(db, monkeypatch):
    """
    NSS has no timeout of its own, and this code runs while a node waits for its
    install payload. A directory that never answers must degrade to the stored
    resolution on a deadline, not block the fetch.
    """
    import time as timing
    from utils.helper import Helper

    def never_answers(_name):
        timing.sleep(30)

    monkeypatch.setattr(Helper, 'owner_lookup_timeout', 0.2)
    monkeypatch.setattr('utils.helper.pwd.getpwnam', never_answers)
    db.insert('ownercache', Helper().make_rows(
        {'name': 'slowuser', 'resolved': '7777', 'updated': 'NOW'}))
    started = timing.time()
    assert Helper().resolve_owner('slowuser') == '7777'
    assert timing.time() - started < 5, 'the lookup was not bounded by the deadline'
    # and the write-time check reports it as unresolvable rather than waiting either
    started = timing.time()
    assert Helper().check_owner('slowuser') is False
    assert timing.time() - started < 5


def test_update_stays_silent_for_a_resolvable_owner(db, seed):
    status, message = _post_node_secret('node001', {
        'name': 'fine', 'content': 'c2VjcmV0', 'path': '/etc/fine',
        'owner': 'root:root', 'mode': '600'})
    assert status, message
    assert 'Warning' not in message


# ---------------------------------------------------------------------------
# the install-time parser
# ---------------------------------------------------------------------------

def _template_function(name):
    """The body of a top-level bash function from the classic install template."""
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


def _run_bash(script):
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.skipif(shutil.which('bash') is None, reason='bash not available')
def test_exact_key_extraction_is_immune_to_content_collisions(tmp_path):
    """
    The token parser matches keys by grep. Loosely, a base64 content containing the
    literal characters 'mode' or 'owner' false-hits and shifts every later value one
    place -- the wrong mode on the wrong file, silently. The exact matcher cannot be
    fooled: base64 has no quotes, so a content token can never equal a bare key token.
    """
    payload = ('{"config": {"secrets": {"node": {"node001": ['
               '{"name": "s1", "content": "YWJjmodeZGVmowner", "path": "/etc/f1",'
               ' "owner": "root:root", "mode": "640", "resolved_owner": "0:0"},'
               '{"name": "s2", "content": "c2Vjb25k", "path": "/etc/f2",'
               ' "owner": "ldapuser", "mode": "400", "resolved_owner": "1000"}'
               ']}}}}')
    json_file = tmp_path / 'node.secrets.json'
    json_file.write_text(payload)
    script = (f'function get_json_segment {{\n{_template_function("get_json_segment")}\n}}\n'
              f'function get_json_exact {{\n{_template_function("get_json_exact")}\n}}\n')

    modes = _run_bash(script + f'get_json_exact {json_file} mode').split()
    assert modes == ['"640"', '"400"'], \
        f'exact mode extraction fooled by content containing "mode": {modes}'
    owners = _run_bash(script + f'get_json_exact {json_file} resolved_owner').split()
    assert owners == ['"0:0"', '"1000"']
    paths = _run_bash(script + f'get_json_segment {json_file} path').split()
    assert paths == ['"/etc/f1"', '"/etc/f2"']

    # and the reason the exact matcher exists: the loose one IS fooled by this payload
    loose = _run_bash(script + f'get_json_segment {json_file} mode').split()
    assert loose != modes, (
        'the loose matcher now survives key-in-content collisions; if that is real, '
        'get_json_exact is redundant and this test should be rethought'
    )


def test_installer_chowns_with_the_resolved_owner():
    """The chown must use the numeric resolved_owner -- a name would need the very
    directory the chroot does not have."""
    body = _template_function('node_secrets')
    assert "get_json_exact /lunatmp/node.secrets.json 'resolved_owner'" in body
    assert "get_json_exact /lunatmp/node.secrets.json 'mode'" in body
    assert 'chown' in body and 'chroot' in body
    assert 'chmod "${mode:-600}"' in body
