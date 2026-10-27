"""
luna node listinventory shows one row per node. A node with an installer snapshot and a
BMC snapshot shows the installer's: it always carries the summary, where some boards publish
none over Redfish, and the two count differently (threads against physical cores). The BMC
snapshot stands in only for a node that has nothing else.
"""
from base.nodeinventory import NodeInventory
from utils.database import Database
from utils.helper import Helper

INBAND = {'source': 'inband', 'product': 'R181-Z91-00', 'serial': 'GJGAN6121A0001',
          'cpu_count': 96, 'memory_mb': 64257, 'disks': [], 'gpus': [], 'nics': []}
REDFISH_BLANK = {'source': 'redfish', 'product': 'R181-Z91-00', 'disks': [], 'gpus': [], 'nics': []}
REDFISH = {'source': 'redfish', 'product': 'AS -1123US-TR4', 'serial': 'S268665X8226819',
           'cpu_count': 48, 'memory_mb': 131072, 'disks': [], 'gpus': [], 'nics': []}


def _store(name, snapshot):
    status, message = NodeInventory().update_inventory(
        name=name, request_data={'config': {'node': {name: {'inventory': snapshot}}}})
    assert status is True, message


def test_the_list_prefers_the_installer_snapshot_over_the_bmc_one(sqlite_db):
    for name in ('node002', 'node003'):
        Database().insert('node', Helper().make_rows({'name': name}))
    _store('node002', INBAND)
    _store('node002', REDFISH_BLANK)      # written later, so the last row the join returns
    _store('node003', REDFISH)            # a node the installer never inventoried

    status, response = NodeInventory().list_inventory()

    assert status is True, response
    rows = response['config']['node']
    assert rows['node002']['source'] == 'inband' and rows['node002']['cpu_count'] == 96
    assert rows['node003']['source'] == 'redfish' and rows['node003']['cpu_count'] == 48
