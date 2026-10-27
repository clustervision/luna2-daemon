"""
TRIX-2248: luna network reserve lists every taken address on a network with the device that
holds it. A node and a switch both hold addresses through their own interface rows, so each
interface kind resolves through its own table, and an address whose interface row is gone is
skipped with a log line rather than taking the whole listing down.
"""
import pytest

from utils.database import Database
from utils.helper import Helper


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.dbstructure import DBStructure
    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['network', 'ipaddress', 'node', 'nodeinterface', 'switch', 'switchinterface',
                  'otherdevices', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _address(db, ip, tableref, tablerefid, networkid):
    db.insert('ipaddress', Helper().make_rows({'ipaddress': ip, 'tableref': tableref,
                                               'tablerefid': tablerefid, 'networkid': networkid}))


def test_every_kind_of_owner_is_listed_and_an_orphan_is_skipped(db):
    from base.network import Network
    net = db.insert('network', Helper().make_rows({'name': 'qa-net', 'network': '10.99.0.0', 'subnet': '255.255.255.0'}))
    node = db.insert('node', Helper().make_rows({'name': 'node001'}))
    nic = db.insert('nodeinterface', Helper().make_rows({'nodeid': node, 'interface': 'BOOTIF'}))
    switch = db.insert('switch', Helper().make_rows({'name': 'sw01'}))
    sw_mgmt = db.insert('switchinterface', Helper().make_rows({'switchid': switch, 'interface': 'mgmt'}))
    sw_up = db.insert('switchinterface', Helper().make_rows({'switchid': switch, 'interface': 'uplink'}))
    other = db.insert('otherdevices', Helper().make_rows({'name': 'pdu01'}))
    ctrl = db.insert('controller', Helper().make_rows({'hostname': 'controller'}))
    _address(db, '10.99.0.10', 'nodeinterface', nic, net)
    _address(db, '10.99.0.20', 'switchinterface', sw_mgmt, net)
    _address(db, '10.99.0.21', 'switchinterface', sw_up, net)
    _address(db, '10.99.0.30', 'otherdevices', other, net)
    _address(db, '10.99.0.1', 'controller', ctrl, net)
    _address(db, '10.99.0.40', 'switch', switch, net)                # a switch addressed directly, as before
    _address(db, '10.99.0.50', 'node', node, net)                    # a node addressed directly, as before
    _address(db, '10.99.0.99', 'nodeinterface', 999, net)           # the interface row is gone

    status, response = Network().taken_ip('qa-net')

    assert status is True, response
    taken = {t['ipaddress']: t['device'] for t in response['config']['network']['qa-net']['taken']}
    assert taken == {'10.99.0.10': 'node001', '10.99.0.20': 'sw01', '10.99.0.21': 'sw01',
                     '10.99.0.30': 'pdu01', '10.99.0.1': 'controller',
                     '10.99.0.40': 'sw01', '10.99.0.50': 'node001'}
    assert '10.99.0.99' not in taken, 'an orphaned address is skipped, not fatal'
