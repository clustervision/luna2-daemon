#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
# GPL-3.0-or-later

"""
What the mounts document means for a machine (TRIX-2131): who mounts what, who
exports what, the lines the two templates lay out, the managed fstab block, the
clash check across documents, and the hand-over to a booting node.

The corpus is the design's example document, read from the validator's test so
the two files can never disagree about it.
"""

import json
import os
from base64 import b64decode, b64encode

import pytest

from utils import mounts
from utils import mountsrender
from utils.mountsrender import MountsRender, fstab_rows, export_rows, export_clashes
from test_mounts import CORPUS, NODES, _doc, _entry, db  # noqa: F401 - db is a fixture

DAEMON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')
ENTRIES = CORPUS['mounts']
CONTROLLER = {'controller', 'self', 'ctrl1', 'ctrl1.cluster'}
ADDRESSES = {'controller': '10.141.255.254', 'self': '10.141.255.252'}
NETWORKS = {'cluster': ['10.141.0.0/16', 'fd00:141::/64'], 'ib': ['10.149.0.0/16']}


@pytest.fixture(autouse=True)
def _templates():
    """Point the render at the daemon's own templates."""
    import common.constant as constant
    previous = constant.CONSTANT['TEMPLATES'].get('TEMPLATE_FILES')
    constant.CONSTANT['TEMPLATES']['TEMPLATE_FILES'] = os.path.join(DAEMON, 'templates')
    yield
    constant.CONSTANT['TEMPLATES']['TEMPLATE_FILES'] = previous


def _by_path(entries, path):
    return next(entry for entry in entries if entry['path'] == path)


# --- who serves, who mounts --------------------------------------------------------

def test_a_controller_serves_the_shares_that_name_it_and_mounts_the_rest():
    serving = [e['path'] for e in ENTRIES if mounts.serves(e, CONTROLLER)]
    mounting = [e['path'] for e in ENTRIES if mounts.mounts(e, CONTROLLER)]
    assert serving == ['/trinity/home', '/trinity/shared', '/trinity/archive']
    # not scratch (node003 serves it), not ohpc (no server = the controller's own share)
    assert mounting == ['/trinity/scratch', '/home/corp', '/lustre/work', '/beegfs', '/local/tmp']


def test_a_node_mounts_everything_it_does_not_serve():
    names = {'node001'}
    assert not [e for e in ENTRIES if mounts.serves(e, names)]
    assert [e['path'] for e in ENTRIES if mounts.mounts(e, names)] == [e['path'] for e in ENTRIES]


def test_the_serving_node_exports_its_share_and_does_not_mount_it():
    names = {'fileserver01'}
    assert [e['path'] for e in ENTRIES if mounts.serves(e, names)] == ['/trinity/scratch']
    assert '/trinity/scratch' not in [e['path'] for e in ENTRIES if mounts.mounts(e, names)]
    assert mounts.server_matches('fileserver01.cluster', names)
    assert not mounts.server_matches('fileserver011', names)


def test_reserved_words_resolve_and_names_pass_through():
    assert mounts.resolve_server(None, ADDRESSES) == '10.141.255.254'
    assert mounts.resolve_server('controller', ADDRESSES) == '10.141.255.254'
    assert mounts.resolve_server('self', ADDRESSES) == '10.141.255.252'
    assert mounts.resolve_server('nas01.corp.example', ADDRESSES) == 'nas01.corp.example'
    assert mounts.client_specs('cluster', NETWORKS) == ['10.141.0.0/16', 'fd00:141::/64']
    assert mounts.client_specs('10.20.0.0/16', NETWORKS) == ['10.20.0.0/16']


# --- the rows and the templates ------------------------------------------------------

def test_fstab_rows_carry_the_device_per_type_and_the_mountpoints():
    rows, dirs = fstab_rows([e for e in ENTRIES if mounts.mounts(e, {'node001'})], ADDRESSES)
    devices = {row['path']: (row['device'], row['fstype'], row['options']) for row in rows}
    assert devices['/trinity/home'] == ('10.141.255.254:/trinity/home', 'nfs',
                                        'nfsvers=4.2,rw,nconnect=16,retrans=4,_netdev,nofail')
    assert devices['/trinity/archive'][0] == '10.141.255.254:/srv/archive'
    assert devices['/trinity/scratch'][0] == 'fileserver01.cluster:/trinity/scratch'
    assert devices['/home/corp'][0] == 'nas01.corp.example:/exports/users'
    assert devices['/lustre/work'] == ('10.150.0.10@o2ib:10.150.0.11@o2ib:/workfs', 'lustre', 'flock,_netdev,nofail')
    assert devices['/beegfs'][:2] == ('beegfs_nodev', 'beegfs')
    assert devices['/trinity/ohpc'][0] == '10.141.255.254:/trinity/ohpc'
    assert '/local/tmp' not in devices                      # manual: a mountpoint, no line
    assert ('/local/tmp', '-', '-', '1777') in dirs
    assert ('/trinity/scratch', 'root', 'users', '1777') in dirs


def test_an_absent_entry_writes_neither_a_line_nor_a_mountpoint():
    rows, dirs = fstab_rows([dict(_by_path(ENTRIES, '/home/corp'), state='absent')], ADDRESSES)
    assert rows == [] and dirs == []


def test_export_rows_expand_a_network_per_family_and_join_the_options():
    rows = export_rows([e for e in ENTRIES if mounts.serves(e, CONTROLLER)], NETWORKS)
    by_path = {row['path']: row['clients'] for row in rows}
    assert by_path['/trinity/home'] == [
        '10.141.0.0/16(sync,no_subtree_check,rw,no_root_squash)',
        'fd00:141::/64(sync,no_subtree_check,rw,no_root_squash)',
        '10.149.0.0/16(sync,no_subtree_check,rw,no_root_squash)']
    assert by_path['/trinity/shared'][-1] == '10.20.0.0/16(sync,no_subtree_check,ro)'
    assert '/srv/archive' in by_path                        # exported by its source path


def test_an_export_naming_no_client_renders_nothing():
    entry = dict(_by_path(ENTRIES, '/trinity/home'), export={'options': 'rw'})
    assert export_rows([entry], NETWORKS) == []


def test_the_templates_lay_the_rows_out():
    render = MountsRender()
    exports = render.render_exports([e for e in ENTRIES if mounts.serves(e, CONTROLLER)], NETWORKS)
    lines = [line for line in exports.splitlines() if line and not line.startswith('#')]
    assert lines[0].startswith('/trinity/home 10.141.0.0/16(')
    assert len(lines) == 3
    rows, _ = fstab_rows([_by_path(ENTRIES, '/home/corp')], ADDRESSES)
    block = render.render_fstab(rows)
    assert block.splitlines() == [mountsrender.FSTAB_BEGIN,
                                  'nas01.corp.example:/exports/users /home/corp nfs '
                                  'nfsvers=4.2,rw,retrans=4,_netdev,nofail 0 0',
                                  mountsrender.FSTAB_END]
    assert render.render_fstab([]) == ''


def test_the_managed_block_replaces_itself_and_leaves_the_rest_alone(tmp_path):
    etc = tmp_path / 'etc'
    etc.mkdir()
    (etc / 'fstab').write_text('UUID=1 / xfs defaults 0 0\n# BEGIN luna mounts\nold line\n'
                               '# END luna mounts\n/dev/sdb1 /data xfs defaults 0 0\n')
    render = MountsRender()
    rows, _ = fstab_rows([_by_path(ENTRIES, '/home/corp')], ADDRESSES)
    assert render.write_fstab(render.render_fstab(rows), root=str(tmp_path))[0] is True
    text = (etc / 'fstab').read_text()
    assert 'old line' not in text
    assert text.startswith('UUID=1 / xfs defaults 0 0\n/dev/sdb1 /data xfs defaults 0 0\n# BEGIN luna mounts\n')
    assert text.count('# BEGIN luna mounts') == 1
    # an empty render clears the block and keeps the rest
    assert render.write_fstab('', root=str(tmp_path))[0] is True
    assert (etc / 'fstab').read_text() == 'UUID=1 / xfs defaults 0 0\n/dev/sdb1 /data xfs defaults 0 0\n'


# --- clashes ------------------------------------------------------------------------

def test_the_same_directory_exported_twice_alike_is_not_a_clash():
    home = _by_path(ENTRIES, '/trinity/home')
    assert export_clashes([('cluster', [home]), ('group g1', [json.loads(json.dumps(home))])]) == []


def test_the_same_directory_exported_differently_is_a_clash_and_says_who():
    home = _by_path(ENTRIES, '/trinity/home')
    other = dict(home, export={'clients': [{'to': 'ib'}]})
    problems = export_clashes([('cluster', [home]), ('group g1', [other])])
    assert problems == ['/trinity/home on controller is exported by group g1 and by cluster '
                        'with different export blocks']
    # a different server is a different directory
    assert export_clashes([('cluster', [home]), ('node n1', [dict(other, server='n1')])]) == []


# --- the node hand-over -----------------------------------------------------------------

def test_render_node_hands_over_fstab_dirs_and_exports_only_where_they_apply(db):
    render = MountsRender()
    client = render.render_node('node001', b64encode(json.dumps(CORPUS).encode()).decode(), ADDRESSES)
    block = b64decode(client['mounts_fstab']).decode()
    assert '10.141.255.254:/trinity/home /trinity/home nfs' in block
    assert 'fileserver01.cluster:/trinity/scratch /trinity/scratch nfs' in block
    assert client['mounts_exports'] == ''
    dirs = b64decode(client['mounts_dirs']).decode().splitlines()
    assert '/trinity/scratch root users 1777' in dirs and '/local/tmp - - 1777' in dirs
    server = render.render_node('fileserver01', b64encode(json.dumps(CORPUS).encode()).decode(), ADDRESSES)
    exports = b64decode(server['mounts_exports']).decode()
    assert exports.splitlines()[-1].startswith('/trinity/scratch 10.141.0.0/16(async,no_subtree_check,rw)')
    assert '/trinity/scratch' not in b64decode(server['mounts_fstab']).decode()
    assert MountsRender().render_node('node001', '', ADDRESSES) == {
        'mounts_fstab': '', 'mounts_exports': '', 'mounts_dirs': ''}


# --- the controller, against a real schema ---------------------------------------------

def test_render_controller_exports_from_every_document_and_mounts_from_the_cluster(db, monkeypatch):
    from base.cluster import Cluster
    from base.group import Group
    from unittest.mock import patch
    with patch('base.cluster.Service'):
        assert Cluster().update_cluster({'config': {'cluster': {
            'mounts': b64encode(json.dumps(CORPUS).encode()).decode()}}})[0] is True
    group_doc = {'version': 1, 'mounts': [
        {'path': '/trinity/group', 'server': 'self', 'export': {'clients': [{'to': 'cluster'}]}},
        {'path': '/trinity/scratch', 'server': 'fileserver01',
         'export': {'options': 'async,no_subtree_check', 'clients': [{'to': 'cluster', 'options': 'rw'}]}}]}
    with patch('base.group.Service'):
        assert Group().update_group(name='compute', request_data={'config': {'group': {'compute': {
            'mounts': b64encode(json.dumps(group_doc).encode()).decode()}}}})[0] is True

    written = {}
    render = MountsRender()
    monkeypatch.setattr(render, 'my_names', lambda: CONTROLLER)
    monkeypatch.setattr(render, 'write_exports', lambda text: written.setdefault('exports', text) and (True, 'ok'))
    monkeypatch.setattr(render, 'write_fstab', lambda block, root='/': written.setdefault('fstab', block) and (True, 'ok'))
    monkeypatch.setattr(render, 'make_dirs', lambda dirs, root='/': written.setdefault('dirs', dirs))
    monkeypatch.setattr(render, 'mount', lambda entries: written.setdefault('mount', [e['path'] for e in entries]) and (True, 'ok'))
    status, message = render.render_controller()
    assert status is True, message
    paths = [line.split()[0] for line in written['exports'].splitlines() if line and not line.startswith('#')]
    assert paths == ['/trinity/home', '/trinity/shared', '/srv/archive', '/trinity/group']
    assert 'ctrl1' not in written['exports'] and 'fileserver01' not in written['exports']
    fstab_paths = [line.split()[1] for line in written['fstab'].splitlines() if not line.startswith('#')]
    assert fstab_paths == ['/trinity/scratch', '/home/corp', '/lustre/work', '/beegfs']
    assert written['mount'] == ['/trinity/scratch', '/home/corp', '/lustre/work', '/beegfs', '/local/tmp']
    assert ('/local/tmp', '-', '-', '1777') in written['dirs']


def test_a_clashing_export_is_refused_at_store_time(db):
    from base.cluster import Cluster
    from base.group import Group
    from base.node import Node
    from unittest.mock import patch
    with patch('base.cluster.Service'):
        assert Cluster().update_cluster({'config': {'cluster': {
            'mounts': b64encode(json.dumps(CORPUS).encode()).decode()}}})[0] is True
    clashing = {'version': 1, 'mounts': [dict(_by_path(ENTRIES, '/trinity/home'),
                                              export={'clients': [{'to': 'ib', 'options': 'ro'}]})]}
    value = b64encode(json.dumps(clashing).encode()).decode()
    with patch('base.group.Service'):
        status, message = Group().update_group(name='compute', request_data={'config': {'group': {
            'compute': {'mounts': value}}}})
    assert status is False
    assert '/trinity/home on controller is exported by' in message
    assert 'cluster' in message and 'group compute' in message
    with patch('base.node.Service'):
        status, message = Node().update_node(name='node001', request_data={'config': {'node': {
            'node001': {'mounts': value}}}})
    assert status is False and 'with different export blocks' in message
    # replacing the cluster document itself is not a clash with its own old version
    with patch('base.cluster.Service'):
        assert Cluster().update_cluster({'config': {'cluster': {'mounts': value}}})[0] is True


def test_a_write_carrying_mounts_queues_the_controller_render(db):
    from base.node import Node
    from unittest.mock import patch
    with patch('base.node.Service') as service:
        Node().update_node(name='node001', request_data={'config': {'node': {
            'node001': {'mounts': b64encode(json.dumps(CORPUS).encode()).decode()}}}})
        service.return_value.queue.assert_any_call('mounts', 'render')
    with patch('base.node.Service') as service:
        Node().update_node(name='node001', request_data={'config': {'node': {'node001': {'comment': 'x'}}}})
        assert ('mounts', 'render') not in [call.args for call in service.return_value.queue.call_args_list]


# --- the install templates ---------------------------------------------------------------

@pytest.mark.parametrize('template', ['templ_install.cfg', 'templ_install_lpart.cfg'])
def test_both_installers_carry_the_step_after_the_post_phase(template):
    with open(os.path.join(DAEMON, 'templates', template), encoding='utf-8') as handle:
        body = handle.read()
    assert 'function node_mounts {' in body
    assert body.index('postscript\n') < body.index('\nnode_mounts\n') < body.index('node_roles\n{% endif %}')
    for variable in ('LUNA_MOUNTS_FSTAB_B64', 'LUNA_MOUNTS_EXPORTS_B64', 'LUNA_MOUNTS_DIRS_B64'):
        assert variable in body


def test_the_boot_route_hands_the_three_variables_to_the_installer():
    with open(os.path.join(DAEMON, 'routes', 'boot.py'), encoding='utf-8') as handle:
        body = handle.read()
    for variable in ('LUNA_MOUNTS_FSTAB_B64', 'LUNA_MOUNTS_EXPORTS_B64', 'LUNA_MOUNTS_DIRS_B64'):
        assert body.count(variable) == 1, f'{variable} belongs to the install route only, not kickstart'
