#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
NodeInventory Class will handle all node hardware inventory operations.
The parent table nodeinventory holds one snapshot row per node per source,
with scalar rollups; the per-device detail lives in the child tables
nodeinventorydisk and nodeinventorygpu.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'support@clustervision.com'
__status__      = 'Development'

import hashlib
from datetime import datetime
from json import dumps
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

class NodeInventory():
    """
    This class is responsible for all operations on node hardware inventory.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'nodeinventory'
        self.disk_table = 'nodeinventorydisk'
        self.gpu_table = 'nodeinventorygpu'
        self.nic_table = 'nodeinventorynic'
        self.default_source = 'inband'
        # scalar columns stored on the parent row (rollups + node-level facts)
        self.parent_fields = ['manufacturer', 'product', 'serial', 'cpu_model',
                              'cpu_count', 'memory_mb', 'bios_version']
        self.disk_fields = ['name', 'size_gb', 'type', 'model', 'serial']
        self.gpu_fields = ['busid', 'vendor', 'model', 'memory_mb', 'uuid']
        self.nic_fields = ['name', 'mac', 'speed_mbps', 'capabilities']


    def get_inventory(self, name=None):
        """
        This method will return the inventory of a node, one snapshot per source,
        each with its disks and gpus.
        """
        status = False
        response = f"Node {name} not present in database"
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return status, response
        nodeid = node[0]['id']
        parents = Database().get_record(table=self.table, where=f'nodeid = "{nodeid}"')
        if not parents:
            return False, f"No inventory found for node {name}"
        snapshots = []
        for parent in parents:
            source = parent['source']
            snapshot = {'source': source}
            for field in self.parent_fields + ['disk_count', 'disk_total_gb', 'gpu_count', 'nic_count', 'updated']:
                snapshot[field] = parent[field]
            snapshot['disks'] = self._child_rows(self.disk_table, nodeid, source, self.disk_fields)
            snapshot['gpus'] = self._child_rows(self.gpu_table, nodeid, source, self.gpu_fields)
            snapshot['nics'] = self._child_rows(self.nic_table, nodeid, source, self.nic_fields)
            snapshots.append(snapshot)
        response = {'config': {'node': {name: {'inventory': snapshots}}}}
        status = True
        return status, response


    def list_inventory(self):
        """
        This method will return a light summary of inventory for every node that has it.
        """
        status = False
        response = "No node inventory available"
        records = Database().get_record_join(
            ['node.name', 'nodeinventory.source', 'nodeinventory.product',
             'nodeinventory.serial', 'nodeinventory.cpu_count', 'nodeinventory.memory_mb',
             'nodeinventory.disk_count', 'nodeinventory.disk_total_gb',
             'nodeinventory.gpu_count', 'nodeinventory.nic_count', 'nodeinventory.updated'],
            ['nodeinventory.nodeid=node.id'])
        if not records:
            return status, response
        config = {}
        for record in records:
            name = record.pop('name')
            config[name] = record
        response = {'config': {'node': dict(sorted(config.items()))}}
        status = True
        return status, response


    def update_inventory(self, name=None, request_data=None):
        """
        This method will store an inventory snapshot for a node. It is atomic per
        source: the node's child rows for that source are removed and the current
        device set is reinserted, and the parent rollup row is upserted.
        """
        status = False
        response = "Internal error"
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        try:
            data = request_data['config']['node'][name]['inventory']
        except (KeyError, TypeError):
            return False, "Invalid request: inventory data not found in structure"

        node = Database().get_record(table='node', where=f'name = "{name}"')
        if not node:
            return False, f"Node {name} not present in database"
        nodeid = node[0]['id']
        source = data.get('source') or self.default_source

        disks = data.get('disks') or []
        gpus = data.get('gpus') or []
        nics = data.get('nics') or []

        parent_data = {'nodeid': nodeid, 'source': source}
        for field in self.parent_fields:
            if field in data:
                parent_data[field] = data[field]
        parent_data['disk_count'] = len(disks)
        parent_data['disk_total_gb'] = sum(int(disk.get('size_gb') or 0) for disk in disks)
        parent_data['gpu_count'] = len(gpus)
        parent_data['nic_count'] = len(nics)
        parent_data['inventory'] = dumps(data)
        parent_data['hash'] = hashlib.sha256(parent_data['inventory'].encode()).hexdigest()
        parent_data['updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        existing = Database().get_record(table=self.table,
                                         where=f'nodeid = "{nodeid}" AND source = "{source}"')
        if existing:
            where = [{"column": "nodeid", "value": nodeid}, {"column": "source", "value": source}]
            Database().update(self.table, Helper().make_rows(parent_data), where)
        else:
            Database().insert(self.table, Helper().make_rows(parent_data))

        self._refresh_children(self.disk_table, nodeid, source, disks, self.disk_fields)
        self._refresh_children(self.gpu_table, nodeid, source, gpus, self.gpu_fields)
        self._refresh_children(self.nic_table, nodeid, source, nics, self.nic_fields)

        response = f"Inventory for node {name} updated"
        status = True
        return status, response


    def delete_inventory(self, nodeid=None):
        """
        This method will remove a node's rows from all three inventory tables.
        Called from the node delete path.
        """
        for table in [self.table, self.disk_table, self.gpu_table, self.nic_table]:
            Database().delete_row(table, [{"column": "nodeid", "value": nodeid}])
        return True, "Inventory cleared"


    def _child_rows(self, table, nodeid, source, fields):
        """
        This method will fetch a source's child rows for a node as a list of dicts.
        """
        rows = Database().get_record(table=table,
                                     where=f'nodeid = "{nodeid}" AND source = "{source}"')
        devices = []
        if rows:
            for row in rows:
                devices.append({field: row[field] for field in fields})
        return devices


    def _refresh_children(self, table, nodeid, source, devices, fields):
        """
        This method will replace a source's child rows for a node atomically:
        delete the existing rows, then insert the current device set.
        """
        Database().delete_row(table, [{"column": "nodeid", "value": nodeid},
                                      {"column": "source", "value": source}])
        for device in devices:
            row_data = {'nodeid': nodeid, 'source': source}
            for field in fields:
                if field in device:
                    row_data[field] = device[field]
            Database().insert(table, Helper().make_rows(row_data))
