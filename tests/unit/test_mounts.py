#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
# GPL-3.0-or-later

"""
The network mounts document (TRIX-1980): the grammar the daemon refuses at store
time, the three levels it resolves through, and the scope of the route a node
reads it from.

The accepted corpus is the example document from the design, verbatim, so a
grammar change that breaks the design's own example fails here first. Each
refusal rule has one case, keyed on the message the operator sees.
"""

import ast
import json
import os
from base64 import b64encode

import pytest

from utils import mounts

DAEMON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')

# the design's own example, TRIX-2094
CORPUS = {
    "version": 1,
    "comment": "cluster network mounts",
    "mounts": [
        {"path": "/trinity/home", "server": "controller",
         "export": {"options": "sync,no_subtree_check",
                    "clients": [{"to": "cluster", "options": "rw,no_root_squash"},
                                {"to": "ib", "options": "rw,no_root_squash"}]},
         "options": "nfsvers=4.2,rw,nconnect=16,retrans=4,_netdev,nofail",
         "comment": "home directories, served by the controller pair over both fabrics"},
        {"path": "/trinity/shared", "server": "controller",
         "export": {"options": "sync,no_subtree_check",
                    "clients": [{"to": "cluster", "options": "ro"},
                                {"to": "ib", "options": "ro"},
                                {"to": "10.20.0.0/16", "options": "ro"}]},
         "options": "nfsvers=4.2,ro,retrans=4,_netdev,nofail"},
        {"path": "/trinity/archive", "server": "controller", "source": "/srv/archive",
         "export": {"options": "sync,no_subtree_check",
                    "clients": [{"to": "cluster", "options": "ro"}]},
         "options": "nfsvers=4.2,ro,_netdev,nofail",
         "comment": "exported path differs from the mountpoint"},
        {"path": "/trinity/scratch", "server": "fileserver01.cluster",
         "export": {"options": "async,no_subtree_check",
                    "clients": [{"to": "cluster", "options": "rw"}]},
         "options": "nfsvers=4.2,rw,nconnect=16,_netdev,nofail",
         "owner": "root", "group": "users", "mode": "1777",
         "comment": "served by a node, not the controller"},
        {"path": "/home/corp", "server": "nas01.corp.example", "source": "/exports/users",
         "options": "nfsvers=4.2,rw,retrans=4,_netdev,nofail",
         "comment": "external. nothing here serves it, so no export block"},
        {"path": "/lustre/work", "type": "lustre",
         "server": "10.150.0.10@o2ib:10.150.0.11@o2ib", "source": "/workfs",
         "options": "flock,_netdev,nofail"},
        {"path": "/beegfs", "type": "beegfs", "server": "beegfs_nodev",
         "options": "cfgFile=/etc/beegfs/beegfs-client.conf,_netdev,nofail"},
        {"path": "/trinity/ohpc", "options": "nfsvers=4.2,ro,_netdev,nofail",
         "state": "present",
         "comment": "the cluster share at this path, written to fstab, mounted at next boot"},
        {"path": "/local/tmp", "type": "manual", "mode": "1777",
         "comment": "create the mountpoint, mount nothing"},
    ],
}
NODES = {"fileserver01", "node001"}


def _doc(**changes):
    doc = json.loads(json.dumps(CORPUS))
    doc.update(changes)
    return doc


def _entry(idx, **changes):
    doc = _doc()
    doc["mounts"][idx].update(changes)
    return doc


def _rejects(doc, needle, node_names=NODES):
    raw = doc if isinstance(doc, str) else json.dumps(doc)
    with pytest.raises(mounts.MountsInvalid) as err:
        mounts.validate(raw, node_names)
    assert needle in str(err.value), f"got: {err.value}"


# --- the validator -------------------------------------------------------------

def test_the_design_example_is_accepted():
    mounts.validate(json.dumps(CORPUS), NODES)


def test_empty_is_legal():
    mounts.validate("", NODES)
    mounts.validate("   ", NODES)
    mounts.validate(b"", NODES)


def test_no_mounts_declared_is_legal():
    mounts.validate(json.dumps({"version": 1, "mounts": []}), NODES)


def test_not_json():
    _rejects("{not json", "not valid JSON")


def test_not_object():
    _rejects("[1]", "must be an object")


def test_wrong_version():
    _rejects(_doc(version=2), "version must be 1")


def test_mounts_must_be_a_list():
    _rejects(_doc(mounts={}), "mounts must be an array")


def test_unknown_keys_at_every_level():
    _rejects(_doc(disabled=True), "top-level: unknown field 'disabled'")
    _rejects(_entry(0, remote="x"), "mounts[0]: unknown field 'remote'")
    doc = _doc(); doc["mounts"][0]["export"]["hosts"] = []
    _rejects(doc, "mounts[0].export: unknown field 'hosts'")
    doc = _doc(); doc["mounts"][0]["export"]["clients"][0]["rw"] = True
    _rejects(doc, "mounts[0].export.clients[0]: unknown field 'rw'")


def test_path_required_absolute_and_unique():
    doc = _doc(); del doc["mounts"][0]["path"]
    _rejects(doc, "mounts[0].path is required")
    _rejects(_entry(0, path="trinity/home"), "must be absolute")
    _rejects(_entry(1, path="/trinity/home"), "'/trinity/home' is already declared by mounts[0]")


def test_type_and_state_enumerations():
    _rejects(_entry(5, type="cephfs"), "type unsupported: 'cephfs'")
    _rejects(_entry(7, state="enabled"), "state unsupported: 'enabled'")
    mounts.validate(json.dumps(_entry(5, type="mmfs", export=None)), NODES)


def test_mode_is_octal_text():
    _rejects(_entry(3, mode="rwx"), "mode must be octal digits")
    _rejects(_entry(3, mode="17777"), "mode must be octal digits")
    _rejects(_entry(3, mode=1777), "mode must be text")


def test_export_only_on_nfs():
    doc = _entry(5, export={"clients": [{"to": "cluster"}]})
    _rejects(doc, "export is only valid on an nfs entry, not lustre")


def test_export_needs_a_server_that_can_render_it():
    doc = _doc(); del doc["mounts"][0]["server"]
    _rejects(doc, "needs a server to render on")
    _rejects(_entry(0, server="nas01.corp.example"),
             "server 'nas01.corp.example' is not a controller or a node")


def test_export_server_may_be_a_node_by_name_or_fqdn_or_a_reserved_word():
    for server in ("fileserver01", "fileserver01.cluster", "controller", "self"):
        mounts.validate(json.dumps(_entry(3, server=server)), NODES)


def test_export_server_check_is_skipped_without_names():
    mounts.validate(json.dumps(_entry(3, server="anything.at.all")), None)


def test_export_client_needs_a_target():
    doc = _doc(); doc["mounts"][0]["export"]["clients"].append({"options": "rw"})
    _rejects(doc, "clients[2].to is required")


def test_one_export_line_per_directory():
    # a second entry exporting the same directory from the same server
    doc = _doc()
    doc["mounts"].append({"path": "/trinity/archive-ro", "server": "controller",
                          "source": "/srv/archive", "export": {"clients": [{"to": "ib"}]}})
    _rejects(doc, "exports /srv/archive from controller which mounts[2] already exports")


def test_b64_transport_is_checked():
    _rejects_b64("not base64!", "must be base64-encoded JSON")
    mounts.validate_b64(b64encode(json.dumps(CORPUS).encode()).decode(), NODES)


def _rejects_b64(value, needle):
    with pytest.raises(mounts.MountsInvalid) as err:
        mounts.validate_b64(value, NODES)
    assert needle in str(err.value)


def test_known_servers_reads_node_rows():
    assert mounts.known_servers([{'name': 'a'}, {'name': ''}, {'id': 3}]) == {'a'}
    assert mounts.known_servers(None) == set()


# --- store time and resolution, against a real (SQLite) schema ------------------

@pytest.fixture
def db(tmp_path):
    """A fresh SQLite database with the tables the node/group/cluster reads touch."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'node', 'cluster', 'osimage', 'osimagetag', 'bmcsetup',
                  'redfishsetup', 'network', 'groupinterface', 'nodeinterface',
                  'ipaddress', 'monitor', 'queue', 'route', 'routemap',
                  'groupsecrets', 'nodesecrets', 'switch', 'cloud', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    from utils.helper import Helper
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    groupid = Database().insert('group', Helper().make_rows({'name': 'compute'}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    Database().insert('node', Helper().make_rows({'name': 'fileserver01', 'groupid': groupid}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _b64(doc):
    return b64encode(json.dumps(doc).encode()).decode()


GOOD = _b64(CORPUS)
BAD = _b64(_doc(version=9))
OTHER = _b64({"version": 1, "mounts": [{"path": "/only/here"}]})


def _set_cluster(value):
    # an accepted cluster update queues a dns reload through Service(), which
    # builds a real command; a unit test must not shell out
    from unittest.mock import patch
    from base.cluster import Cluster
    with patch('base.cluster.Service'):
        return Cluster().update_cluster({'config': {'cluster': {'mounts': value}}})


def _set_group(value):
    from base.group import Group
    return Group().update_group(name='compute', request_data={'config': {'group': {
        'compute': {'mounts': value}}}})


def _set_node(value):
    from base.node import Node
    return Node().update_node(name='node001', request_data={'config': {'node': {
        'node001': {'mounts': value}}}})


def _node_view():
    from base.node import Node
    _, single = Node().get_node(name='node001')
    entry = single['config']['node']['node001']
    return entry['mounts'], entry['_mounts_source']


def _group_view():
    from base.group import Group
    _, single = Group().get_group(name='compute')
    entry = single['config']['group']['compute']
    return entry['mounts'], entry['_mounts_source']


@pytest.mark.parametrize('setter', [_set_cluster, _set_group, _set_node])
def test_every_level_refuses_a_bad_document_at_store_time(db, setter):
    status, message = setter(BAD)
    assert status is False
    assert 'version must be 1' in message


@pytest.mark.parametrize('setter', [_set_cluster, _set_group, _set_node])
def test_every_level_refuses_an_export_from_an_unknown_server(db, setter):
    status, message = setter(_b64(_entry(3, server='nas01')))
    assert status is False
    assert "server 'nas01' is not a controller or a node" in message


@pytest.mark.parametrize('setter', [_set_cluster, _set_group, _set_node])
def test_every_level_accepts_the_design_example(db, setter):
    status, message = setter(GOOD)
    assert status is True, message


def test_resolution_is_strict_override_cluster_group_node(db):
    empty = b64encode(b'').decode()
    assert _node_view() == (empty, 'default')
    assert _group_view() == (empty, 'default')

    assert _set_cluster(GOOD)[0] is True
    assert _group_view() == (GOOD, 'cluster')
    assert _node_view() == (GOOD, 'cluster')

    assert _set_group(OTHER)[0] is True
    assert _group_view() == (OTHER, 'group')
    assert _node_view() == (OTHER, 'group')

    assert _set_node(GOOD)[0] is True
    assert _node_view() == (GOOD, 'node')
    assert _group_view() == (OTHER, 'group')


# --- the route a node reads it from ----------------------------------------------

def _decorators(module_path, func_name):
    with open(os.path.join(DAEMON, module_path), encoding='utf-8') as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return {(d.id if isinstance(d, ast.Name) else
                     d.func.id if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) else
                     None) for d in node.decorator_list}
    raise AssertionError(f'{func_name} not found in {module_path}')


def test_node_mounts_route_is_provision_scoped_like_disklayout():
    decs = _decorators('routes/config_node.py', 'config_node_mounts')
    assert 'provision_token_required' in decs
    assert 'token_required' not in decs
    assert 'validate_name' in decs


def test_group_and_cluster_mounts_routes_stay_admin_only():
    assert 'token_required' in _decorators('routes/config_group.py', 'config_group_mounts')
    assert 'token_required' in _decorators('routes/config_cluster.py', 'config_cluster_mounts')
