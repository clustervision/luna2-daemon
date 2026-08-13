#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
TRIX-1713 unit tests: cluster-scope secrets.

A secret needed by many groups (an IPA-CLIENT password, say) used to be created once
per group and changed once per group, forever. A cluster secret is stored once and
applies to every node.

Secrets are the exception to Luna's inheritance: they stack. A node receives its own
secrets, its group's, and the cluster's - additively, never overriding. The one place
order matters is a shared path: the installer writes the sections in JSON order, so
the cluster section is emitted first and a node or group secret naming the same path
is written later and wins.
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
    """A fresh, isolated SQLite database with the secrets-relevant tables created."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    Helper.owner_cache = {}
    for table in ['node', 'group', 'cluster', 'nodesecrets', 'groupsecrets',
                  'clustersecrets', 'ownercache']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None
    Helper.owner_cache = {}


@pytest.fixture
def seed(db):
    """A cluster, a group and a node in it."""
    from utils.helper import Helper
    clusterid = db.insert('cluster', Helper().make_rows({'name': 'democluster'}))
    groupid = db.insert('group', Helper().make_rows({'name': 'compute'}))
    nodeid = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    return {'clusterid': clusterid, 'groupid': groupid, 'nodeid': nodeid}


def _cluster_payload(*secrets):
    return {'config': {'secrets': {'cluster': list(secrets)}}}


def test_secrets_tables_carry_the_same_file_attributes():
    """clustersecrets is the third scope of the same thing; it must never drift from
    the other two."""
    from utils.dbstructure import DBStructure
    per_table = {}
    for table, ref in (('nodesecrets', 'nodeid'), ('groupsecrets', 'groupid'),
                       ('clustersecrets', 'clusterid')):
        layout = DBStructure().get_database_table_structure(table)
        per_table[table] = {c['column'] for c in layout} - {'id', ref}
    assert per_table['clustersecrets'] == per_table['nodesecrets'] == per_table['groupsecrets']


def test_cluster_secret_round_trip(db, seed):
    from base.secret import Secret
    status, message = Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'ipa', 'content': 'aXBhLXB3', 'path': '/etc/ipa.pw',
         'owner': 'root:root', 'mode': '400'}))
    assert status, message
    assert 'created' in message
    status, response = Secret().get_cluster_secret('ipa')
    assert status, response
    row = response['config']['secrets']['cluster'][0]
    assert (row['name'], row['path'], row['owner'], row['mode']) == \
        ('ipa', '/etc/ipa.pw', 'root:root', '400')
    assert row['content'] == 'aXBhLXB3'


def test_cluster_secret_updates_in_place(db, seed):
    """The whole point of the ticket: change it once, not once per group."""
    from base.secret import Secret
    Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'ipa', 'content': 'b2xk', 'path': '/etc/ipa.pw'}))
    status, message = Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'ipa', 'content': 'bmV3', 'path': '/etc/ipa.pw'}))
    assert status, message
    assert 'updated' in message
    rows = db.get_record(table='clustersecrets')
    assert len(rows) == 1, 'an update must never create a second copy'
    _, response = Secret().get_cluster_secret('ipa')
    assert response['config']['secrets']['cluster'][0]['content'] == 'bmV3'


def test_secrets_stack_across_all_three_scopes(db, seed):
    """A node receives cluster + group + node secrets together - the stated
    exception to inheritance-overriding."""
    from base.secret import Secret
    Secret().update_node_secret('node001', 'n1', {'config': {'secrets': {'node': {
        'node001': [{'name': 'n1', 'content': 'bm9kZQ==', 'path': '/etc/n1'}]}}}})
    Secret().update_group_secret('compute', 'g1', {'config': {'secrets': {'group': {
        'compute': [{'name': 'g1', 'content': 'Z3JvdXA=', 'path': '/etc/g1'}]}}}})
    Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'c1', 'content': 'Y2x1c3Rlcg==', 'path': '/etc/c1'}))

    status, response = Secret().get_node_secrets('node001')
    assert status, response
    secrets = response['config']['secrets']
    assert [r['name'] for r in secrets['cluster']] == ['c1']
    assert [r['name'] for r in secrets['node']['node001']] == ['n1']
    assert [r['name'] for r in secrets['group']['compute']] == ['g1']
    # the cluster section is first in emission order: on a shared path the more
    # specific scopes are written later by the installer and win
    assert list(secrets.keys())[0] == 'cluster'


def test_cluster_secrets_get_the_installer_attributes(db, seed):
    """Same owner/mode treatment as the other scopes: defaults coalesced, owner
    resolved to numbers for the chroot."""
    from base.secret import Secret
    Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'plain', 'content': 'eA==', 'path': '/etc/plain'},
        {'name': 'owned', 'content': 'eQ==', 'path': '/etc/owned',
         'owner': 'root:root', 'mode': '440'}))
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    rows = {r['name']: r for r in response['config']['secrets']['cluster']}
    assert (rows['plain']['owner'], rows['plain']['mode'],
            rows['plain']['resolved_owner']) == ('root:root', '600', '0:0')
    assert (rows['owned']['owner'], rows['owned']['mode'],
            rows['owned']['resolved_owner']) == ('root:root', '440', '0:0')


def test_cluster_update_warns_when_an_owner_does_not_resolve(db, seed):
    from base.secret import Secret
    status, message = Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'typo', 'content': 'eA==', 'path': '/etc/typo',
         'owner': 'ghostuser:ghostgroup'}))
    assert status, message
    assert 'Warning' in message and 'ghostuser:ghostgroup' in message
    assert db.get_record(table='clustersecrets', where='name = "typo"'), \
        'an unresolvable owner is a warning, not a rejection'


def test_cluster_secret_clone_and_delete(db, seed):
    from base.secret import Secret
    Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'orig', 'content': 'eA==', 'path': '/etc/orig'}))
    status, message = Secret().clone_cluster_secret('orig', _cluster_payload(
        {'name': 'orig', 'content': 'eA==', 'path': '/etc/copy', 'newsecretname': 'copy'}))
    assert status, message
    names = {r['name'] for r in db.get_record(table='clustersecrets')}
    assert names == {'orig', 'copy'}
    status, message = Secret().delete_cluster_secret('orig')
    assert status, message
    names = {r['name'] for r in db.get_record(table='clustersecrets')}
    assert names == {'copy'}
    status, message = Secret().delete_cluster_secret('orig')
    assert not status, 'deleting a deleted secret must fail loudly'


def test_update_without_a_cluster_row_fails_loudly(db):
    """A cluster row exists on any installed system; a missing one is a broken
    database, not a place to invent an id."""
    from base.secret import Secret
    status, message = Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'x', 'content': 'eA==', 'path': '/etc/x'}))
    assert not status
    assert 'Cluster is not available' in message


# ---------------------------------------------------------------------------
# the install-time contract: cluster secrets reach the node with ZERO template
# changes, because the parser walks the whole JSON
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
def test_installer_parse_carries_cluster_secrets_aligned(db, seed, tmp_path):
    """The real GET response for a node with secrets at all three scopes, run through
    the real template extraction: one aligned row per secret, cluster rows first."""
    from base.secret import Secret
    Secret().update_cluster_secrets(_cluster_payload(
        {'name': 'c1', 'content': 'Y2x1c3Rlcg==', 'path': '/etc/c1', 'mode': '444'}))
    Secret().update_node_secret('node001', 'n1', {'config': {'secrets': {'node': {
        'node001': [{'name': 'n1', 'content': 'bm9kZQ==', 'path': '/etc/n1',
                     'owner': 'root:root', 'mode': '640'}]}}}})
    status, response = Secret().get_node_secrets('node001')
    assert status, response
    json_file = tmp_path / 'node.secrets.json'
    json_file.write_text(json.dumps(response))

    script = (f'function get_json_segment {{\n{_template_function("get_json_segment")}\n}}\n'
              f'function get_json_exact {{\n{_template_function("get_json_exact")}\n}}\n')

    def run(call):
        result = subprocess.run(['bash', '-c', script + call],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.split()

    paths = run(f'get_json_segment {json_file} path')
    owners = run(f'get_json_exact {json_file} resolved_owner')
    modes = run(f'get_json_exact {json_file} mode')
    assert paths == ['"/etc/c1"', '"/etc/n1"'], 'cluster row must come first'
    assert owners == ['"0:0"', '"0:0"']
    assert modes == ['"444"', '"640"']
