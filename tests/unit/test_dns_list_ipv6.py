"""
TRIX-2097: listing the dns entries of a network shows an IPv6 address. The table stores
a colon address in its own column, and the list read only the IPv4 one, so every IPv6
row came back as None while the zone served it.
"""
import pytest
from json import loads
from jwt import encode
from cases.route_requirements_cases import app as routes_app
from utils.database import Database
from utils.helper import Helper


@pytest.fixture(name='listed')
def listed_fixture(sqlite_db):
    from common.constant import CONSTANT
    networkid = Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Database().insert('dns', Helper().make_rows({'host': 'svc', 'ipaddress': '10.141.1.1', 'networkid': networkid}))
    Database().insert('dns', Helper().make_rows({'host': 'svc', 'ipaddress_ipv6': 'fd00:2097::50', 'networkid': networkid}))
    client = routes_app().test_client()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    response = client.get('/config/dns/cluster', headers={'x-access-tokens': token})
    assert response.status_code == 200
    return loads(response.data)['config']['dns']['cluster']


def test_every_row_carries_its_address(listed):
    assert sorted(row['ipaddress'] for row in listed) == ['10.141.1.1', 'fd00:2097::50']
