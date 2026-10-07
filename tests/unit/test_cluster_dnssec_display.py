"""
TRIX-2230: cluster show marks a dnssec setting N/A when the rendered named.conf leaves it out,
so the view and the config agree. dnssec-enable only exists in legacy BIND, and with it off,
dnssec-validation is not rendered either.
"""
import pytest

from base.cluster import Cluster
from utils.database import Database


@pytest.fixture
def cluster_db(sqlite_db):
    """A cluster with one controller: cluster show answers only once it has found one."""
    def insert(table, **columns):
        Database().insert(table, [{'column': k, 'value': v} for k, v in columns.items()])
    insert('cluster', name='mycluster')
    insert('network', name='cluster', network='10.141.0.0', subnet='16')
    insert('controller', hostname='controller', beacon=1, clusterid=1)
    insert('ipaddress', ipaddress='10.141.255.254', tableref='controller', tablerefid=1, networkid=1)
    return sqlite_db


def _shown(legacy, enable, validation):
    Database().update('cluster', [{'column': 'bind_legacy', 'value': legacy},
                                  {'column': 'dnssec_enable', 'value': enable},
                                  {'column': 'dnssec_validation', 'value': validation}], [])
    status, response = Cluster().information()
    assert status is True, response
    cluster = response['config']['cluster']
    return cluster['bind_legacy'], cluster['dnssec_enable'], cluster['dnssec_validation']


@pytest.mark.parametrize('legacy, enable, validation, shown', [
    (1, 0, 1, (True, False, 'N/A')),
    (1, 0, 0, (True, False, 'N/A')),
    (1, 0, None, (True, False, 'N/A')),
    (1, 1, 1, (True, True, True)),
    (1, 1, 0, (True, True, False)),
    (1, None, 1, (True, None, True)),
    (0, 0, 1, (False, 'N/A', True)),
    (0, None, 0, (False, 'N/A', False)),
    (0, None, None, (False, 'N/A', None)),
])
def test_cluster_show_marks_what_named_conf_leaves_out(cluster_db, legacy, enable, validation, shown):
    assert _shown(legacy, enable, validation) == shown
