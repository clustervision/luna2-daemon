"""
TRIX-2229: a network's type is written into every node's interface config as type=<value>, and
the per-distro templates only know ethernet and infiniband, in lower case. Anything else is
refused at update_network, the one path create, update and the peer's replay all take.
"""
import glob
import os
import re

import pytest

from base.network import Network
from utils.database import Database
from utils.dbstructure import DBStructure
from utils.queue import Queue

TEMPLATES = os.path.join(os.path.dirname(__file__), '..', '..', 'daemon', 'plugins', 'boot', 'network')


@pytest.fixture
def network_db(db, seed, monkeypatch):
    """The db fixture plus the ipaddress table, with the post-validation side effects stubbed."""
    Database().create('ipaddress', DBStructure().get_database_table_structure('ipaddress'))
    monkeypatch.setattr(Network, '_queue_network_services', lambda self: None)
    monkeypatch.setattr(Queue, 'add_task_to_queue', lambda *args, **kwargs: (1, 'stubbed'))
    monkeypatch.setattr(Queue, 'next_task_in_queue', lambda *args, **kwargs: None)
    return db


def _set_type(value):
    return Network().update_network('cluster', {'config': {'network': {'cluster': {'type': value}}}})


def _stored_type():
    return Database().get_record(table='network', where="name='cluster'")[0]['type']


@pytest.mark.parametrize('value', ['ethernet', 'infiniband'])
def test_a_supported_type_is_stored(network_db, value):
    status, response = _set_type(value)
    assert status is True, response
    assert _stored_type() == value


@pytest.mark.parametrize('value', ['ethernt', 'Ethernet', 'INFINIBAND', 'ib', 'vlan', 'bond'])
def test_any_other_type_is_refused_and_not_stored(network_db, value):
    before = _stored_type()
    status, response = _set_type(value)
    assert status is False
    assert response.startswith('Invalid request') and 'ethernet' in response and 'infiniband' in response
    assert _stored_type() == before


def test_an_update_without_a_type_is_untouched(network_db):
    before = _stored_type()
    status, response = Network().update_network(
        'cluster', {'config': {'network': {'cluster': {'comment': 'no type here'}}}})
    assert status is True, response
    assert _stored_type() == before


def test_every_type_a_template_branches_on_is_accepted():
    """The accepted set is held to what the NetworkManager templates actually handle."""
    named = set()
    for template in glob.glob(os.path.join(TEMPLATES, '*.templ')):
        with open(template, encoding='utf-8') as handle:
            named.update(re.findall(r"\['networktype'\]\s*==\s*'([^']+)'", handle.read()))
    assert named, 'no template compares networktype; the pattern above no longer matches them'
    assert named | {'ethernet'} == set(Network.NETWORK_TYPES)
