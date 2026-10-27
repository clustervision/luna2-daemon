"""
TRIX-2237: a network's gateway, and its nameserver and NTP server when they sit inside the
network, are taken addresses. Auto-assignment must never hand them to a node, and the reserve
listing must show them, so the two agree on what "taken" means.
"""
import pytest

from utils.database import Database
from utils.helper import Helper

NET = {'name': 'qa-net', 'network': '10.99.0.0', 'subnet': '255.255.255.0', 'gateway': '10.99.0.1',
       'nameserver_ip': '10.99.0.2', 'ntp_server': 'ntp.example.net'}


def test_the_networks_own_addresses_inside_its_range():
    assert Helper().network_service_addresses(NET) == [('gateway', '10.99.0.1'), ('nameserver', '10.99.0.2')]
    outside = dict(NET, nameserver_ip='10.141.0.2', ntp_server='10.99.0.3')
    assert Helper().network_service_addresses(outside) == [('gateway', '10.99.0.1'), ('ntp', '10.99.0.3')]
    assert Helper().network_service_addresses({'name': 'bare', 'network': '10.99.0.0', 'subnet': '255.255.255.0'}) == []
    v6 = {'network_ipv6': 'fd00:99::', 'subnet_ipv6': '64', 'gateway_ipv6': 'fd00:99::1', 'nameserver_ip_ipv6': 'fd00:98::53'}
    assert Helper().network_service_addresses(v6, 'ipv6') == [('gateway', 'fd00:99::1')]


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.dbstructure import DBStructure
    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['network', 'ipaddress', 'reservedipaddress', 'node', 'nodeinterface', 'switch', 'switchinterface',
                  'otherdevices', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_auto_assignment_skips_the_gateway_and_the_nameserver(db):
    """The customer case: gateway .1, first auto-assigned node used to get .1."""
    from utils.config import Config
    db.insert('network', Helper().make_rows(NET))
    occupied = Config().get_all_occupied_ips_from_network('qa-net')
    assert '10.99.0.1' in occupied and '10.99.0.2' in occupied
    assert Helper().get_available_ip('10.99.0.0', '255.255.255.0', occupied) == '10.99.0.3'


def test_the_reserve_listing_shows_them_even_on_an_otherwise_empty_network(db):
    from base.network import Network
    db.insert('network', Helper().make_rows(NET))
    status, response = Network().taken_ip('qa-net')
    assert status is True, response
    assert response['config']['network']['qa-net']['taken'] == [
        {'ipaddress': '10.99.0.1', 'device': 'gateway'}, {'ipaddress': '10.99.0.2', 'device': 'nameserver'}]


def test_a_network_with_nothing_of_its_own_still_says_all_free(db):
    from base.network import Network
    db.insert('network', Helper().make_rows({'name': 'bare', 'network': '10.98.0.0', 'subnet': '255.255.255.0'}))
    status, response = Network().taken_ip('bare')
    assert status is False and 'All IP Address are free on Network bare' in response
