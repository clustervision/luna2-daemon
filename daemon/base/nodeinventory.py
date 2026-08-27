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
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'support@clustervision.com'
__status__      = 'Development'

import hashlib
from time import time
from random import randint
from os import getpid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from base64 import b64encode
from json import dumps
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.redfish import Redfish, RedfishAccess, LOGIN
from utils.status import Status
from common.constant import CONSTANT

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
        self.firmware_table = 'nodeinventoryfirmware'
        self.default_source = 'inband'
        # scalar columns stored on the parent row (rollups + node-level facts)
        self.parent_fields = ['manufacturer', 'product', 'serial', 'cpu_model',
                              'cpu_count', 'memory_mb', 'bios_version',
                              'bios_digest', 'bios_config', 'bios_config_digest']
        self.disk_fields = ['name', 'size_gb', 'type', 'model', 'serial']
        self.gpu_fields = ['busid', 'vendor', 'model', 'memory_mb', 'uuid']
        self.nic_fields = ['name', 'mac', 'speed_mbps', 'capabilities']
        # A machine's firmware component set is implementation-defined: two boards from
        # one vendor list different things, and a flash can change the list. So these are
        # the fields a SoftwareInventory resource carries, not a list of components we
        # expect - the components themselves are whatever the machine reports.
        self.firmware_fields = ['name', 'component', 'version', 'updateable',
                                'manufacturer', 'release_date', 'software_id', 'related_item']


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
            snapshot['firmware'] = self._child_rows(self.firmware_table, nodeid, source,
                                                    self.firmware_fields)
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
        firmware = data.get('firmware') or []

        parent_data = {'nodeid': nodeid, 'source': source}
        for field in self.parent_fields:
            if field in data:
                parent_data[field] = data[field]
        parent_data['disk_count'] = len(disks)
        parent_data['disk_total_gb'] = sum(int(disk.get('size_gb') or 0) for disk in disks)
        parent_data['gpu_count'] = len(gpus)
        parent_data['nic_count'] = len(nics)
        # The archive is stored base64, as this daemon carries every other piece of
        # awkward content. Two things it buys: a restore through /config/cluster/import
        # strips every quote from a text value, which turns stored JSON into something
        # nothing can parse, and base64 has no quotes to lose. And it is always encoded
        # rather than sometimes, so a reader never has to guess which it got.
        snapshot = dumps(data)
        parent_data['inventory'] = b64encode(snapshot.encode()).decode('ascii')
        # the hash stays over the JSON, not over the encoding of it. It answers
        # 'has this node's hardware changed', and that must not move because we
        # changed how the same answer is written down
        parent_data['hash'] = hashlib.sha256(snapshot.encode()).hexdigest()
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
        self._refresh_children(self.firmware_table, nodeid, source, firmware,
                               self.firmware_fields)
        self.refresh_node_identity(nodeid=nodeid)

        response = f"Inventory for node {name} updated"
        status = True
        return status, response


    def refresh_node_identity(self, nodeid=None):
        """
        This method keeps the node's own vendor and assettag in step with what was
        just collected.

        The two columns are not a second inventory. They belong to the *device*
        abstraction the rack view joins across node, switch, otherdevices and
        controller - and switches have no inventory table, so the columns cannot
        simply move here. What can go is the second collection: the install used
        to run dmidecode again and POST these two values separately, which is one
        more probe, one more request, and a second thing to disagree with.

        Derived from the snapshot rather than sent alongside it, so they also
        refresh on an out-of-band collection instead of only at install time. A
        node whose board was replaced stops reporting the old one.

        Where a node has both snapshots, redfish wins - the same preference the
        plugin search path uses, kept identical on purpose: dmidecode and Redfish
        do not always spell a manufacturer the same way, and two rules for one
        question is how they drift.
        """
        rows = Database().get_record(table=self.table, where=f'nodeid = "{nodeid}"')
        if not rows:
            return False
        chosen = None
        for row in rows:
            if str(row['source'] or '').strip().lower() == 'redfish':
                chosen = row
                break
            if chosen is None:
                chosen = row
        identity = {}
        if chosen.get('manufacturer'):
            identity['vendor'] = chosen['manufacturer']
        # assettag has held the serial number since it was introduced; the name is
        # wrong and renaming it is an API change, so this fills it the way the
        # install always did rather than quietly changing what it means
        if chosen.get('serial'):
            identity['assettag'] = chosen['serial']
        if not identity:
            return False
        Database().update('node', Helper().make_rows(identity),
                          [{"column": "id", "value": nodeid}])
        return True


    def delete_inventory(self, nodeid=None):
        """
        This method will remove a node's rows from all three inventory tables.
        Called from the node delete path.
        """
        for table in [self.table, self.disk_table, self.gpu_table, self.nic_table,
                      self.firmware_table]:
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


    def bmc_for(self, name=None, needs=LOGIN):
        """
        This method resolves how to reach a node's BMC: its address, and the
        credentials to use.

        The caller says what privilege the operation needs and gets the weakest
        account carrying it - a whole-cluster inventory sweep has no business
        running as a BMC administrator, and a BIOS push has no business running as
        one either when an Operator can reset a system.

        A node with no redfishsetup is refused rather than reached with the bmcsetup
        credentials (TRIX-2027). Those credentials do work over Redfish, because the
        BMC keeps one user store behind both front ends - which is precisely why
        using them was wrong: it meant an administrator could not express "leave
        this BMC alone" by declining to configure Redfish for it.
        """
        node = Database().get_record_join(
            ['node.id as nodeid', 'node.name as nodename', 'node.groupid as groupid',
             'ipaddress.ipaddress as device', 'node.bmcsetupid'],
            ['nodeinterface.nodeid=node.id', 'ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', "nodeinterface.interface='BMC'",
             f"node.name='{name}'"])
        if not node:
            return False, f'{name} does not exist or has no BMC interface configured'
        if not node[0]['device']:
            return False, f'{name} has no BMC address configured'
        status, access = RedfishAccess().for_node(nodename=name, needs=needs)
        if not status:
            return False, access
        return True, {'device': node[0]['device'], 'username': access['username'],
                      'password': access['password'], 'scheme': access['scheme'],
                      'port': access['port'], 'verify': access['verify']}


    def redfish_snapshot(self, redfish=None):
        """
        This method builds an inventory snapshot from a Redfish service.

        Everything is read from what the service publishes. Nothing here assumes a
        resource path, a component list or a vendor: the collections are reached
        through the service root, and the firmware components are whatever the
        machine's own FirmwareInventory happens to list. A board that exposes
        something nobody anticipated is stored correctly without a schema change,
        because components are rows rather than columns.
        """
        snapshot = {'source': 'redfish'}
        # the client answers (status, path, data), and on a failure the reason is in
        # the second slot rather than the third - the third is None
        status, system_path, system = redfish.system()
        if not status:
            return False, system_path
        for column, key in (('manufacturer', 'Manufacturer'), ('product', 'Model'),
                            ('serial', 'SerialNumber'), ('bios_version', 'BiosVersion')):
            if system.get(key):
                snapshot[column] = str(system[key])
        processors = system.get('ProcessorSummary') or {}
        if processors.get('Model'):
            snapshot['cpu_model'] = str(processors['Model']).strip()
        if processors.get('Count'):
            snapshot['cpu_count'] = int(processors['Count'])
        memory = system.get('MemorySummary') or {}
        if memory.get('TotalSystemMemoryGiB'):
            snapshot['memory_mb'] = int(float(memory['TotalSystemMemoryGiB']) * 1024)
        digest = self.bios_digest(redfish=redfish, system=system)
        if digest:
            snapshot['bios_digest'] = digest
        snapshot['disks'] = self.redfish_disks(redfish=redfish, system=system)
        snapshot['nics'] = self.redfish_nics(redfish=redfish, system=system)
        snapshot['gpus'] = []
        snapshot['firmware'] = self.redfish_firmware(redfish=redfish)
        return True, snapshot


    def bios_digest(self, redfish=None, system=None):
        """
        This method returns a digest of the BIOS attributes a machine holds, or None.

        A digest rather than the attributes themselves, and that is a decision
        rather than an economy. The attribute set runs from about a hundred
        entries to several hundred, so keeping it per node costs tens of megabytes
        across a cluster - in the database, in every backup, and in the hash the
        controllers compare on every pass. The questions an operator actually asks
        of stored inventory are "has this machine's BIOS moved since we last
        looked" and "do these nodes all hold the same one", and a digest answers
        both of those exactly.

        What it cannot answer is what the settings are, or how far a machine is
        from a configuration. Those need the board, and the status view says so
        rather than implying the stored answer is the current one.
        """
        bios_path = (system or {}).get('Bios', {}).get('@odata.id')
        if not bios_path:
            return None
        status, bios = redfish.get(path=bios_path)
        attributes = (bios or {}).get('Attributes') if status else None
        if not isinstance(attributes, dict) or not attributes:
            return None
        return hashlib.sha256(dumps(attributes, sort_keys=True).encode()).hexdigest()


    def redfish_disks(self, redfish=None, system=None):
        """
        This method reads the drives a system exposes.

        Both shapes are tried because both are in the wild: Storage is the current
        model and SimpleStorage is what older services publish. Neither is assumed.
        """
        disks = []
        storage_path = (system.get('Storage') or {}).get('@odata.id')
        if storage_path:
            status, storage = redfish.get(path=storage_path)
            for member in (storage.get('Members', []) if status else []):
                status, controller = redfish.get(path=member.get('@odata.id'))
                if not status:
                    continue
                for drive in controller.get('Drives', []) or []:
                    status, data = redfish.get(path=drive.get('@odata.id'))
                    if not status:
                        continue
                    disks.append({
                        'name': str(data.get('Id') or data.get('Name') or ''),
                        'size_gb': int((data.get('CapacityBytes') or 0) / 1000000000),
                        'type': str(data.get('MediaType') or ''),
                        'model': str(data.get('Model') or ''),
                        'serial': str(data.get('SerialNumber') or ''),
                    })
        if disks:
            return disks
        simple_path = (system.get('SimpleStorage') or {}).get('@odata.id')
        if simple_path:
            status, simple = redfish.get(path=simple_path)
            for member in (simple.get('Members', []) if status else []):
                status, controller = redfish.get(path=member.get('@odata.id'))
                if not status:
                    continue
                for device in controller.get('Devices', []) or []:
                    disks.append({
                        'name': str(device.get('Name') or ''),
                        'size_gb': int((device.get('CapacityBytes') or 0) / 1000000000),
                        'type': '',
                        'model': str(device.get('Model') or ''),
                        'serial': '',
                    })
        return disks


    def redfish_nics(self, redfish=None, system=None):
        """
        This method reads the network interfaces a system exposes.
        """
        nics = []
        path = (system.get('EthernetInterfaces') or {}).get('@odata.id')
        if not path:
            return nics
        status, collection = redfish.get(path=path)
        if not status:
            return nics
        for member in collection.get('Members', []):
            status, data = redfish.get(path=member.get('@odata.id'))
            if not status:
                continue
            nics.append({
                'name': str(data.get('Id') or data.get('Name') or ''),
                'mac': str(data.get('MACAddress') or data.get('PermanentMACAddress') or ''),
                'speed_mbps': int(data.get('SpeedMbps') or 0),
                'capabilities': str(data.get('Status', {}).get('Health') or ''),
            })
        return nics


    def redfish_firmware(self, redfish=None):
        """
        This method reads every firmware component the machine reports.

        Two levels, and both are taken. The BMC's own FirmwareVersion, which is one
        of the two strings that are effectively always present and the one a flash is
        verified against - and then UpdateService/FirmwareInventory, which is the
        general answer and whose membership is entirely up to the implementation.

        Updateable is carried deliberately: it says whether the update service will
        touch a component at all, which is a question that is currently answered by
        trying.
        """
        components = []
        status, _, manager = redfish.manager()
        if status and manager.get('FirmwareVersion'):
            components.append({
                'name': 'bmc',
                'component': str(manager.get('Model') or 'BMC'),
                'version': str(manager['FirmwareVersion']),
                'updateable': 1,
                'manufacturer': str(manager.get('Manufacturer') or ''),
                'release_date': '',
                'software_id': '',
                'related_item': str(manager.get('@odata.id') or ''),
            })
        status, root = redfish.service_root()
        if not status:
            return components
        update_path = (root.get('UpdateService') or {}).get('@odata.id')
        if not update_path:
            return components
        status, update_service = redfish.get(path=update_path)
        if not status:
            return components
        inventory_path = (update_service.get('FirmwareInventory') or {}).get('@odata.id')
        if not inventory_path:
            return components
        status, collection = redfish.get(path=inventory_path)
        if not status:
            return components
        for member in collection.get('Members', []):
            status, data = redfish.get(path=member.get('@odata.id'))
            if not status:
                continue
            related = data.get('RelatedItem') or []
            components.append({
                'name': str(data.get('Id') or data.get('Name') or ''),
                'component': str(data.get('Name') or ''),
                'version': str(data.get('Version') or ''),
                'updateable': 1 if data.get('Updateable') else 0,
                'manufacturer': str(data.get('Manufacturer') or ''),
                'release_date': str(data.get('ReleaseDate') or ''),
                'software_id': str(data.get('SoftwareId') or ''),
                'related_item': str(related[0].get('@odata.id')) if related and isinstance(related[0], dict) else '',
            })
        return components


    def collect_redfish(self, name=None):
        """
        This method collects a node's inventory over Redfish and hands it back in
        the shape update_inventory takes, to be stored as the 'redfish' snapshot
        beside whatever in-band collection left.

        It collects and does not write, because storing it is a replicated change
        and the route is what decides replication - every other base class here
        leaves that to its route, and a base class reaching for the journal is a
        circular import besides.

        It works on a node that has never been provisioned and on one that is
        powered off, which is the whole point: in-band collection runs only during
        an install, so a brand-new node has no inventory at all and nothing that
        selects on hardware can work for it.
        """
        status, access = self.bmc_for(name=name)
        if not status:
            return False, access
        redfish = Redfish(device=access['device'], username=access['username'],
                          password=access['password'], scheme=access['scheme'],
                          port=access['port'], verify=access['verify'])
        status, snapshot = self.redfish_snapshot(redfish=redfish)
        if not status:
            return False, f'{name}: {snapshot}'
        return True, {'config': {'node': {name: {'inventory': snapshot}}}}


    def store_collected(self, name=None, payload=None):
        """
        This method stores a collected snapshot, replicating it to the peer.

        The journal import is function-local, which is the one case this repo allows
        it: utils/journal.py imports this class by name so it can dispatch to it, so
        importing Journal at the top of this module is a genuine cycle. base/boot.py
        can import it at the top only because the journal does not import boot.
        """
        from utils.journal import Journal

        status, response = Journal().add_request(function="NodeInventory.update_inventory",
                                                 object=name, payload=payload)
        if status is True:
            status, response = self.update_inventory(name, payload)
        return status, response


    def collect_child(self, name=None, request_id=None):
        """
        This method collects one node and records the outcome against the request.

        A node that cannot be reached is reported and does not raise: one dark BMC
        must not take the sweep down, and the operator needs to know which node it
        was rather than that something failed.
        """
        try:
            status, payload = self.collect_redfish(name=name)
            if status:
                status, message = self.store_collected(name=name, payload=payload)
            else:
                message = payload
        except Exception as exp:
            status, message = False, f'{exp}'
            self.logger.error(f'redfish inventory for {name} raised: {exp}')
        # the shape Control().get_status parses, because this reuses that channel
        # rather than growing a second one: <node>:<subsystem> <action>:<result>:<text>
        Status().add_message(request_id=request_id, username_initiator='redfish_inventory',
                             message=f"{name}:inventory redfish:{status}:{message}",
                             status=200 if status else 500)
        return status


    def bulk_collect_redfish(self, request_data=None):
        """
        This method collects inventory over Redfish for a hostlist.

        It runs outside the control pipeline deliberately - control is for turning
        machines on and off, and a slow inventory sweep has no business occupying it.
        Concurrency is bounded by the same BMC batch size the control path uses,
        because it is the same resource being protected: a controller talking to too
        many BMCs at once, and a rack of dark ones whose connect timeouts must not
        starve the healthy nodes.

        It returns as soon as the work is scheduled. Per-node outcomes arrive through
        the request_id channel, which is what luna already polls for a hostlist.

        A group may be named instead of a hostlist, and it is expanded here at the
        edge rather than carried into the sweep: the members are read now, so a node
        added to the group after the operator asked is not silently included in
        something they did not see. That is the same rule a BIOS push follows.
        """
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        try:
            asked = request_data['config']['node']
        except (KeyError, TypeError):
            return False, 'Invalid request: no hostlist supplied'
        if asked.get('group'):
            group = asked['group']
            # 'group' is a reserved SQL word, hence the backticks - the form
            # utils/osimage.py uses. Bare, the statement is a syntax error the
            # daemon logs and swallows, and an empty answer then reads exactly like
            # a group with no nodes
            members = Database().get_record_join(
                ['node.name as name'], ['group.id=node.groupid'],
                [f'`group`.name="{group}"'])
            if not members:
                exists = Database().get_record(table='group', where=f'name = "{group}"')
                return False, (f'Group {group} has no nodes' if exists
                               else f'Group {group} is not available')
            hostlist = [member['name'] for member in members]
        else:
            raw_hosts = asked.get('hostlist')
            if not raw_hosts:
                return False, 'Invalid request: no hostlist supplied'
            hostlist = Helper().get_hostlist(raw_hosts)
            if not hostlist:
                return False, 'Invalid request: invalid hostlist'
        batch = int(CONSTANT['BMCCONTROL']['BMC_BATCH_SIZE'])
        request_id = str(time()) + str(randint(1001, 9999)) + str(getpid())
        Status().add_message(request_id, 'redfish_inventory', 'Collecting inventory...')
        Status().mark_messages_read(request_id)

        def sweep():
            with ThreadPoolExecutor(max_workers=batch) as executor:
                for host in hostlist:
                    executor.submit(self.collect_child, host, request_id)
            Status().add_message(request_id, 'redfish_inventory', 'EOF')

        starter = ThreadPoolExecutor(max_workers=1)
        starter.submit(sweep)
        starter.shutdown(wait=False)
        return True, {'request_id': request_id,
                      'config': {'node': {'inventory': {'queued': len(hostlist)}}}}
