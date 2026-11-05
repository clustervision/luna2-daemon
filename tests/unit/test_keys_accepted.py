#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2354: GET /config/<type>/_keys answers the keys a change of that type accepts, in
the names the API answers them under.

Both halves are derived, so the next column added is covered without anybody remembering
this file: every key answered is taken by the type's update, and every column of the
type's layout is answered under the name the type's show uses, or excluded with a reason.
The show is the authority on the API's names: the update also takes a bare id column.
"""

import os
from base64 import b64encode

import pytest

from base.bmcsetup import BMCSetup
from base.cluster import Cluster
from base.group import Group
from base.keys import EXCLUDED, KEYS, Keys
from base.network import Network
from base.node import Node
from base.osimage import OSImage
from base.otherdev import OtherDev
from base.switch import Switch
from common import constant
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.helper import Helper
from utils.queue import Queue
from utils.service import Service

DAEMON = os.path.join(os.path.dirname(__file__), '..', '..', 'daemon')

# The object each type is probed on, and the calls that change and show it.
NAMES = {'node': 'n1', 'group': 'g1', 'osimage': 'o1', 'network': 'net1', 'switch': 's1',
         'otherdev': 'd1', 'bmcsetup': 'b1', 'cluster': 'cluster'}
CALLS = {
    'node': (Node, 'update_node', 'get_node'), 'group': (Group, 'update_group', 'get_group'),
    'osimage': (OSImage, 'update_osimage', 'get_osimage'), 'network': (Network, 'update_network', 'get_network'),
    'switch': (Switch, 'update_switch', 'get_switch'), 'otherdev': (OtherDev, 'update_otherdev', 'get_otherdev'),
    'bmcsetup': (BMCSetup, 'update_bmcsetup', 'get_bmcsetup'),
}

# Values the update checks; any other key is sent 'probe', or '1' for an integer column.
VALUES = {
    'ipxe_kernel': 'default', 'install_mode': 'full', 'unmanaged_bmc_users': 'disable',
    'provision_method': 'kickstart', 'provision_fallback': 'http', 'roles': 'bond',
    'scripts': 'default', 'profiles': 'p1', 'mounts': b64encode(b'{"version": 1, "mounts": []}').decode(),
    'group': 'g1', 'osimage': 'o1', 'switch': 's1', 'bmcsetup': 'b1', 'bmcsetupname': 'b1',
    'biosconfig': 'bc1', 'cloud': 'c1', 'redfishsetup': 'r1', 'redfishsetupname': 'r1', 'osimagetag': 't1',
    'network': '10.141.0.0/16', 'gateway': '10.141.0.1', 'nameserver_ip': '10.141.0.2',
    'ntp_server': '10.141.0.3', 'zone': 'internal', 'type': 'ethernet', 'non_authoritative': 'y',
    'dhcp': 'y', 'dhcp_nodes_in_pool': 'y', 'dhcp_nodes_only': 'n',
    'dhcp_range_begin': '10.141.160.1', 'dhcp_range_end': '10.141.160.9', 'shared': '',
    'dhcp_relay': '', 'dhcp_link_subnet': '', 'forwardserver_ip': '10.141.0.4',
    'domain_search': 'example.com', 'controller': '10.141.255.254', 'controller_network': 'net1',
    'interfaces': [], 'macaddress': '00:11:22:33:44:55', 'clear': 'ipv6',
}
# An address of a switch or other device is a network name and an address together.
DEVICE = {'network': 'net1', 'ipaddress': '10.141.1.5', 'nonetwork': 'y'}
TOGETHER = {'network': 'ipaddress', 'ipaddress': 'network', 'nonetwork': 'ipaddress'}
# What a value is stored as, where the update rewrites it.
STORED = {'profiles': '1', 'non_authoritative': '1', 'dhcp': '1', 'dhcp_nodes_in_pool': '1',
          'dhcp_nodes_only': '0', 'network': '10.141.0.0'}
# Keys the update takes and keeps somewhere else than the column of that name.
NOT_IN_ITS_COLUMN = {('switch', 'macaddress'): 'kept on the management interface'}


@pytest.fixture
def stubbed(monkeypatch):
    """The tree's own plugins; nothing a change queues leaves the test."""
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setattr(Service, '__init__', lambda self: None)
    monkeypatch.setattr(Service, 'queue', lambda self, *args, **kwargs: None)
    monkeypatch.setattr(Queue, 'add_task_to_queue', lambda *args, **kwargs: (1, 'stubbed'))
    monkeypatch.setattr(Queue, 'next_task_in_queue', lambda *args, **kwargs: None)


def _seed():
    """One object of every type, and what they point at."""
    db = Database()
    clusterid = db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    networkid = db.insert('network', Helper().make_rows({
        'name': 'net1', 'network': '10.141.0.0', 'subnet': '16', 'network_ipv6': 'fd00::', 'subnet_ipv6': '64',
        'dhcp': '1', 'non_authoritative': '1',
        'dhcp_range_begin': '10.141.160.1', 'dhcp_range_end': '10.141.160.9'}))
    controllerid = db.insert('controller', Helper().make_rows({'hostname': 'ctl1', 'beacon': 1, 'clusterid': clusterid}))
    db.insert('ipaddress', Helper().make_rows({'ipaddress': '10.141.255.254', 'tableref': 'controller',
                                               'tablerefid': controllerid, 'networkid': networkid}))
    osimageid = db.insert('osimage', Helper().make_rows({'name': 'o1'}))
    db.insert('osimagetag', Helper().make_rows({'name': 't1', 'osimageid': osimageid}))
    groupid = db.insert('group', Helper().make_rows({'name': 'g1', 'osimageid': osimageid}))
    db.insert('node', Helper().make_rows({'name': 'n1', 'groupid': groupid, 'osimageid': osimageid}))
    for table, name in [('switch', 's1'), ('otherdevices', 'd1'), ('bmcsetup', 'b1'), ('profile', 'p1'),
                        ('biosconfig', 'bc1'), ('cloud', 'c1'), ('redfishsetup', 'r1')]:
        db.insert(table, Helper().make_rows({'name': name}))


def _change(segment, key, value):
    name = NAMES[segment]
    if segment == 'cluster':
        return Cluster().update_cluster({'config': {'cluster': {key: value}}})
    body = {'name': name, key: value}
    if segment in ('switch', 'otherdev') and key in TOGETHER:
        body[TOGETHER[key]] = DEVICE[TOGETHER[key]]
    kind, update, _ = CALLS[segment]
    return getattr(kind(), update)(name, {'config': {segment: {name: body}}})


def _shown(segment):
    """The keys the type's show answers for its probe object."""
    if segment == 'cluster':
        status, response = Cluster().information()
    else:
        kind, _, show = CALLS[segment]
        status, response = getattr(kind(), show)(NAMES[segment])
    assert status, response
    body = response['config'][segment]
    if segment != 'cluster':
        body = body[NAMES[segment]]
    return {key for key in body if not key.startswith('_')}


@pytest.mark.parametrize('segment', sorted(KEYS))
def test_every_key_is_taken_and_every_column_is_answered(sqlite_db, stubbed, segment):
    """A key the update refuses, or a column the form cannot reach, is the class this closes."""
    _seed()
    found = KEYS[segment]
    shown = _shown(segment)
    keys = Keys().get_keys(segment)['keys']
    columns = {entry['column']: entry.get('datatype', '')
               for entry in DBStructure().get_database_table_structure(found['table'])}
    assert len(keys) > 3, 'the table did not enumerate'

    refused = []
    for key in keys:
        value = VALUES.get(key, '1' if 'INT' in columns.get(key, '').upper() else 'probe')
        if key == 'name' or key.startswith('new'):
            value = NAMES[segment]
        elif segment in ('switch', 'otherdev') and key in DEVICE:
            value = DEVICE[key]
        status, message = _change(segment, key, value)
        if 'Columns are incorrect' in str(message):
            refused.append(f'{key}: refused with {message}')
        elif key in columns and (segment, key) not in NOT_IN_ITS_COLUMN:
            record = Database().get_record(table=found['table'], where=f"name = '{NAMES[segment]}'")
            stored = record[0][key] if record else None
            if str(stored) != STORED.get(key, str(value)):
                refused.append(f'{key}: sent {value}, stored {stored} ({message})')
    assert not refused, f'{segment}: keys _keys answers that the update does not take:\n  ' + '\n  '.join(refused)

    unanswered = []
    excluded = {**EXCLUDED, **found['excluded']}
    for column in columns:
        if excluded.get(column):
            continue
        name = found['renamed'].get(column, column)
        if name not in keys or name not in shown:
            unanswered.append(f'{column}: answered as {name}, which the show does not answer')
    stale = (set(found['renamed']) | set(found['excluded'])) - set(columns)
    assert not unanswered and not stale, (
        f'{segment}: layout columns _keys does not answer in the API\'s names:\n  ' + '\n  '.join(unanswered)
        + f'\nentries that name no column: {sorted(stale)}'
        + '\nA column no change carries belongs in the excluded table of base/keys.py with its reason.')
