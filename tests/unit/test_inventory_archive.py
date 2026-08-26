#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2024: the inventory archive has to survive a restore.

nodeinventory keeps the whole submitted snapshot in a column of its own, so that
the detail we did not promote to a scalar is still there when somebody eventually
wants it. Nothing reads that column today, which is exactly why it was worth
fixing now: the day something does, the rows a customer restored from backup are
the ones it will meet.

/config/cluster/import carries @input_filter, whose filter_data strips every
quote from every text value and writes the cleaned copy back into request.data.
Stored JSON therefore comes back with all of its quotes deleted - it restores,
it reports success, and it is no longer parseable. base64 has no quotes in its
alphabet, so the archive survives.

The restore is simulated here rather than driven through the import endpoint,
because what has to be pinned is the property (the stored form survives quote
removal), not the one route that happens to destroy it today.
"""

import json
from base64 import b64decode

from base.nodeinventory import NodeInventory
from utils.database import Database
from utils.helper import Helper


# every value below carries a quote of one kind or the other, which is the whole
# point: a snapshot of plain integers would survive the bug being tested for
SNAPSHOT = {
    'source': 'redfish',
    'manufacturer': 'Contoso "Server" Inc.',
    'product': "PowerThing R'750",
    'serial': 'ABC123',
    'cpu_count': 2,
    'memory_mb': 262144,
    'disks': [{'name': 'Disk 0', 'size_gb': 1920, 'type': 'SSD',
               'model': 'Model "X"', 'serial': "S'1"}],
    'gpus': [],
    'nics': [{'name': 'NIC.1', 'mac': 'aa:bb:cc:dd:ee:ff', 'speed_mbps': 25000,
              'capabilities': 'Ethernet, "RDMA"'}],
}


def restored(value):
    """
    What a text value looks like after coming back through the import endpoint.

    filter_data does exactly this, unconditionally, to every string in the body:
        data = data.replace("'", "")
        data = data.replace('"', "")
    """
    return str(value).replace("'", "").replace('"', "")


def stored_archive(name='node001'):
    """Put a snapshot through the real path and hand back the row it wrote."""
    Database().insert('node', Helper().make_rows({'name': name}))
    status, message = NodeInventory().update_inventory(
        name=name, request_data={'config': {'node': {name: {'inventory': SNAPSHOT}}}})
    assert status is True, f'the snapshot was not stored at all: {message}'
    rows = Database().get_record(table='nodeinventory', where=f"source = 'redfish'")
    assert rows, 'update_inventory reported success and wrote no row'
    return rows[0]


def test_the_archive_survives_the_restore_that_strips_quotes(sqlite_db):
    """
    The fix. Without it the stored value is raw JSON, the restore deletes every
    quote in it, and what comes back cannot be parsed at all.
    """
    row = stored_archive()
    assert restored(row['inventory']) == row['inventory'], (
        'the stored archive loses characters when restored through import'
    )
    assert json.loads(b64decode(restored(row['inventory']))) == SNAPSHOT


def test_the_archive_is_always_encoded_never_sometimes(sqlite_db):
    """
    A field that is sometimes encoded pushes a guess onto every reader, and the
    guess is made by pattern-matching the content - which is how a value that
    merely looks like base64 gets decoded into nonsense. One shape, always.
    """
    row = stored_archive()
    assert not row['inventory'].startswith('{'), 'the archive was stored as raw JSON'
    assert json.loads(b64decode(row['inventory'])) == SNAPSHOT


def test_the_change_hash_is_over_the_json_not_over_the_encoding(sqlite_db):
    """
    The hash answers 'has this node's hardware changed'. It must not move because
    we changed how the same answer is written down - otherwise every node in the
    cluster reads as changed once, for no reason anyone can see.
    """
    import hashlib
    row = stored_archive()
    assert row['hash'] == hashlib.sha256(json.dumps(SNAPSHOT).encode()).hexdigest()


def test_the_scalars_and_children_are_unaffected(sqlite_db):
    """
    Encoding the archive must not change what the API actually serves, which is
    built from the scalar columns and the child rows and never from the archive.
    """
    stored_archive()
    status, response = NodeInventory().get_inventory('node001')
    assert status is True
    snapshot = response['config']['node']['node001']['inventory'][0]
    assert snapshot['manufacturer'] == SNAPSHOT['manufacturer']
    assert snapshot['disk_count'] == 1
    assert snapshot['nics'][0]['mac'] == 'aa:bb:cc:dd:ee:ff'
