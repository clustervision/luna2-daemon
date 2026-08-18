#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
The token a node is handed must be scoped to that node, not the admin token.

Two paths mint a node's token: the boot script embeds one built in base/boot.py, and
the /tpm endpoint mints one in Authentication.node_token. The provision-scoped design
carries {node, scope:'provision'} and provision_token_required confines it to that
node's own endpoints. node_token used to mint {id: 0} - the same token the admin login
returns - so a node that authenticated held full cluster admin, and the node-match
check never fired because there was no scope to trigger it.

These guards keep the two honest: node_token mints a scoped token, and the endpoint a
node fetches with it (/boot/install) accepts a provision token (and enforces the node
match) rather than an admin-only token that would reject the scoped one.
"""

import ast
import os

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')


def _func(path, name):
    tree = ast.parse(open(path, encoding='utf-8').read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def test_node_token_is_scoped_not_admin():
    """The /tpm path must not mint a bare {id: 0} admin token; it must carry a scope."""
    fn = _func(os.path.join(DAEMON, 'base', 'authentication.py'), 'node_token')
    minted = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'encode':
            payload = node.args[0] if node.args else None
            if isinstance(payload, ast.Dict):
                keys = {k.value for k in payload.keys if isinstance(k, ast.Constant)}
                minted.append(keys)
    assert minted, "node_token should mint a token"
    for keys in minted:
        assert 'scope' in keys, f"node_token mints an unscoped token {keys} - a node would hold admin"
        assert 'node' in keys, f"a provision token must name its node; got {keys}"
        assert 'id' not in keys, f"node_token must not mint an id-based admin token; got {keys}"


def test_boot_install_accepts_a_provision_token():
    """/boot/install is what a node fetches with its token; it must accept the scoped one."""
    fn = _func(os.path.join(DAEMON, 'routes', 'boot.py'), 'boot_install')
    decs = {d.id if isinstance(d, ast.Name) else getattr(d, 'attr', None)
            for d in fn.decorator_list if not isinstance(d, ast.Call)}
    assert 'provision_token_required' in decs, \
        "boot_install must use @provision_token_required so a node's scoped token is not rejected"
    assert 'token_required' not in decs, \
        "boot_install carries @token_required, which rejects the scoped token a node now presents"
