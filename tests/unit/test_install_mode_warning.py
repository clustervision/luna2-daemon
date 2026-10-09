"""
TRIX-2196: leaving legacy for an lpart install_mode while a prescript, partscript or
postscript, or a disk partitioning boot script, is still set answers with a warning.
lpart runs pre/part/post before its own phases.
"""
from base64 import b64encode

import pytest

from utils.installmode import is_legacy, leftovers, warning

PART = b64encode(b'mount -t tmpfs tmpfs /sysroot\n').decode()
BLANK = b64encode(b'\n  \n').decode()


def test_unset_is_legacy_and_every_lpart_mode_is_not():
    assert is_legacy(None) and is_legacy('') and is_legacy('legacy')
    assert not any(is_legacy(mode) for mode in ['auto', 'sync', 'full', 'local', 'memboot', 'sanitize'])


def test_leftovers_name_filled_scripts_and_partitioning_plugins_only():
    row = {'prescript': BLANK, 'partscript': PART, 'postscript': '', 'scripts': 'nodhcp, raid1'}
    assert leftovers(row) == ['partscript', 'disk partitioning script raid1']
    assert leftovers({'scripts': 'diskfull'}) == ['disk partitioning script diskfull']
    assert leftovers({'scripts': 'nodhcp'}) == []


@pytest.mark.parametrize('old, new, expected', [
    ('legacy', 'memboot', True), (None, 'auto', True),
    ('memboot', 'legacy', False), ('memboot', 'auto', False), ('legacy', 'legacy', False)])
def test_only_leaving_legacy_warns(old, new, expected):
    assert bool(warning(old, new, ['partscript'])) is expected


def test_the_warning_reads_as_a_sentence():
    assert warning('legacy', 'auto', ['partscript', 'postscript', 'disk partitioning script raid1']).endswith(
        'but partscript, postscript and disk partitioning script raid1 are still set')
    assert warning('legacy', 'auto', ['partscript']).endswith('but partscript is still set')


def test_nothing_left_means_no_warning():
    assert warning('legacy', 'memboot', []) == ''


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in DBStructure().tables:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('osimage', Helper().make_rows({'name': 'theosimage'}))
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    Database().insert('group', Helper().make_rows({'name': 'compute', 'osimageid': 1, 'partscript': PART}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': 1}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _answer(status, response):
    from utils.helper import Helper
    assert status is True, response
    return Helper().get_access_code(status, response), response


def test_a_group_leaving_legacy_says_what_is_still_set(db):
    from base.group import Group
    code, response = _answer(*Group().update_group(
        name='compute', request_data={'config': {'group': {'compute': {'install_mode': 'memboot'}}}}))
    assert 'warning' in response and 'partscript' in response and code == 201


def test_a_node_leaving_legacy_names_what_it_inherits(db):
    from base.node import Node
    code, response = _answer(*Node().update_node(
        name='node001', request_data={'config': {'node': {'node001': {'install_mode': 'auto'}}}}))
    assert 'warning' in response and 'partscript' in response and code == 201


def test_a_node_moving_from_a_legacy_to_an_lpart_group_warns(db):
    from base.node import Node
    from utils.helper import Helper
    memboot = db.insert('group', Helper().make_rows({
        'name': 'memboot', 'osimageid': 1, 'install_mode': 'memboot'}))
    db.update('node', Helper().make_rows({'partscript': PART}),
              [{'column': 'name', 'value': 'node001'}])

    code, response = _answer(*Node().update_node(
        name='node001', request_data={'config': {'node': {'node001': {'group': 'memboot'}}}}))

    assert "warning: install_mode legacy -> memboot" in response
    assert 'partscript' in response and code == 201
    assert db.get_record(table='node', where='name = "node001"')[0]['groupid'] == memboot


def test_a_node_moving_between_lpart_groups_is_quiet(db):
    from base.node import Node
    from utils.helper import Helper
    auto = db.insert('group', Helper().make_rows({
        'name': 'auto', 'osimageid': 1, 'install_mode': 'auto'}))
    memboot = db.insert('group', Helper().make_rows({
        'name': 'memboot', 'osimageid': 1, 'install_mode': 'memboot'}))
    db.update('node', Helper().make_rows({'groupid': auto, 'partscript': PART}),
              [{'column': 'name', 'value': 'node001'}])

    code, response = _answer(*Node().update_node(
        name='node001', request_data={'config': {'node': {'node001': {'group': 'memboot'}}}}))

    assert 'warning' not in response and code == 204
    assert db.get_record(table='node', where='name = "node001"')[0]['groupid'] == memboot


def test_an_unrelated_node_change_is_quiet(db):
    from base.node import Node
    code, response = _answer(*Node().update_node(
        name='node001', request_data={'config': {'node': {'node001': {'comment': 'unchanged mode'}}}}))
    assert 'warning' not in response and code == 204


def test_a_cluster_leaving_legacy_names_the_groups_that_follow_it(db):
    from base.cluster import Cluster
    from unittest.mock import patch
    with patch('base.cluster.Service'):
        code, response = _answer(*Cluster().update_cluster(
            {'config': {'cluster': {'install_mode': 'memboot'}}}))
    assert 'warning' in response and 'group compute' in response and code == 201


def test_an_update_that_stays_lpart_is_quiet(db):
    from base.group import Group
    Group().update_group(name='compute', request_data={'config': {'group': {'compute': {'install_mode': 'memboot'}}}})
    code, response = _answer(*Group().update_group(
        name='compute', request_data={'config': {'group': {'compute': {'install_mode': 'auto'}}}}))
    assert 'warning' not in response and code == 204


def test_a_cluster_warning_leaves_out_groups_with_their_own_mode(db):
    from base.cluster import Cluster
    from unittest.mock import patch
    from utils.helper import Helper
    db.insert('group', Helper().make_rows({'name': 'gpu', 'osimageid': 1, 'install_mode': 'memboot', 'partscript': PART}))
    with patch('base.cluster.Service'):
        _, response = _answer(*Cluster().update_cluster({'config': {'cluster': {'install_mode': 'memboot'}}}))
    assert 'group compute' in response and 'group gpu' not in response


def test_a_group_that_already_followed_an_lpart_cluster_is_quiet(db):
    from base.group import Group
    from utils.helper import Helper
    db.update('cluster', Helper().make_rows({'install_mode': 'memboot'}), [])
    _, response = _answer(*Group().update_group(
        name='compute', request_data={'config': {'group': {'compute': {'install_mode': 'auto'}}}}))
    assert 'warning' not in response


def test_a_group_clearing_legacy_to_follow_an_lpart_cluster_warns(db):
    from base.group import Group
    from utils.helper import Helper
    db.update('cluster', Helper().make_rows({'install_mode': 'memboot'}), [])
    db.update('group', Helper().make_rows({'install_mode': 'legacy'}), [{'column': 'name', 'value': 'compute'}])
    _, response = _answer(*Group().update_group(
        name='compute', request_data={'config': {'group': {'compute': {'install_mode': ''}}}}))
    assert 'warning: install_mode legacy -> memboot' in response
