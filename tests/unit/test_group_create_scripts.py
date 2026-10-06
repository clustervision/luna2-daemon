"""
TRIX-2196: a new group gets the classic installer's diskless partscript and postscript
only when it will install in legacy mode. lpart mounts the root and writes fstab itself,
and runs whatever part/post a group carries before its own phases.
"""
import pytest

PART = 'bW91bnQgLW8gbXBvbD1pbnRlcmxlYXZlIC10IHRtcGZzIHRtcGZzIC9zeXNyb290Cg=='
POST = 'ZWNobyAndG1wZnMgLyB0bXBmcyBtcG9sPWludGVybGVhdmUgMCAwJyA+PiAvc3lzcm9vdC9ldGMvZnN0YWIK'


@pytest.fixture
def db(tmp_path):
    """A fresh, isolated SQLite database with the tables a group create touches."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['group', 'node', 'cluster', 'osimage', 'osimagetag', 'bmcsetup',
                  'redfishsetup', 'biosconfig', 'network', 'groupinterface', 'ipaddress', 'monitor',
                  'queue', 'route', 'routemap', 'groupsecrets', 'switch', 'cloud', 'controller']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('osimage', Helper().make_rows({'name': 'theosimage'}))
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16'}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _cluster(db, mode):
    from utils.helper import Helper
    db.insert('cluster', Helper().make_rows({'name': 'cluster', 'install_mode': mode}))


def _group(db, name, **fields):
    from base.group import Group
    status, response = Group().update_group(
        name=name, request_data={'config': {'group': {name: dict(
            {'osimage': 'theosimage', 'interfaces': [{'interface': 'BOOTIF', 'network': 'cluster'}]}, **fields)}}})
    assert status is True, response
    row = db.get_record(table='group', where=f'name = "{name}"')[0]
    return row['partscript'] or '', row['postscript'] or ''


@pytest.mark.parametrize('cluster_mode, group_mode, scripts', [
    (None, None, (PART, POST)),
    ('legacy', None, (PART, POST)),
    ('memboot', None, ('', '')),
    ('auto', None, ('', '')),
    ('memboot', 'legacy', (PART, POST)),
    ('legacy', 'sanitize', ('', '')),
])
def test_a_new_group_gets_the_diskless_scripts_only_in_legacy(db, cluster_mode, group_mode, scripts):
    _cluster(db, cluster_mode)
    fields = {'install_mode': group_mode} if group_mode else {}
    assert _group(db, 'new', **fields) == scripts


def test_scripts_the_request_supplies_are_kept_in_any_mode(db):
    _cluster(db, 'memboot')
    assert _group(db, 'new', partscript='ZWNobyBwYXJ0Cg==', postscript='ZWNobyBwb3N0Cg==') == \
        ('ZWNobyBwYXJ0Cg==', 'ZWNobyBwb3N0Cg==')


def test_an_existing_group_keeps_its_scripts_on_update(db):
    _cluster(db, None)
    assert _group(db, 'old') == (PART, POST)
    from utils.helper import Helper
    db.update('cluster', Helper().make_rows({'install_mode': 'memboot'}), [])
    assert _group(db, 'old', comment='touched') == (PART, POST)
