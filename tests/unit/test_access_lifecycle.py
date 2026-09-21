"""
What happens around an object's and a user's life, found by driving the branch on a live
cluster (TRIX-2137 to TRIX-2141): a token whose row is disabled or gone is refused everywhere,
a deleted user owns nothing afterwards, a write may only name objects the caller can read,
removing hardware needs what creating it needs, and every show renders the three columns.
"""
import os
import pytest
from flask import Flask, g
from test_access_organisation import db, world, client, _body, TABLES  # noqa: F401 - fixtures

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))


def _as(userid):
    app = Flask(__name__)
    context = app.test_request_context('/')
    context.push()
    g.userid = userid
    return context


# TRIX-2137

def test_a_disabled_users_token_is_refused_on_every_route(client, world, db):
    from utils.helper import Helper
    hans = client.as_(world.ids['hans'])
    assert hans.post('/config/node/node002', _body('node', 'node002', comment='x'))[0] == 200
    db.update('user', Helper().make_rows({'enabled': '0'}), [{'column': 'id', 'value': world.ids['hans']}])
    code, body = hans.post('/config/node/node002', _body('node', 'node002', comment='x'))
    assert code == 401 and 'User hans is disabled' in body['message']
    assert hans.get('/config/node/node002/_delete')[0] == 401


def test_a_deleted_users_token_is_refused_even_where_it_owned(client, world, db):
    from utils.helper import Helper
    db.update('node', Helper().make_rows({'owners': str(world.ids['tom'])}), [{'column': 'name', 'value': 'node002'}])
    tom = client.as_(world.ids['tom'])
    assert tom.post('/config/node/node002', _body('node', 'node002', comment='alive'))[0] == 200
    db.delete_row('user', [{'column': 'id', 'value': world.ids['tom']}])
    code, body = tom.post('/config/node/node002', _body('node', 'node002', comment='ghost'))
    assert code == 401 and 'no longer exists' in body['message']


def test_whoami_gives_the_same_answer_as_the_gate(world, db):
    from base.user import User
    from utils.helper import Helper
    db.update('user', Helper().make_rows({'enabled': '0'}), [{'column': 'id', 'value': world.ids['tom']}])
    assert User().whoami(world.ids['tom']) == (False, 'User tom is disabled')
    assert User().whoami(world.ids['alice'])[0] is True


# TRIX-2138

def test_deleting_a_user_removes_it_from_every_owners_list(world, db):
    from base.user import User
    from utils.access import Access
    from utils.helper import Helper
    tom, alice = world.ids['tom'], world.ids['alice']
    db.update('node', Helper().make_rows({'owners': f'{alice},{tom}'}), [{'column': 'name', 'value': 'node002'}])
    db.update('osimage', Helper().make_rows({'owners': str(tom)}), [{'column': 'name', 'value': 'rocky9'}])
    assert User().delete_user('tom')[0] is True
    node = db.get_record(table='node', where="name = 'node002'")[0]
    image = db.get_record(table='osimage', where="name = 'rocky9'")[0]
    assert Access().ids(node['owners']) == [alice]
    assert not image['owners'], 'an emptied list reads as rootus-owned, not as a dangling id'
    assert Access().annotate('osimage', image)['owners'] == ['rootus']


# TRIX-2139

def test_reference_keys_cover_every_governed_id_column_of_node_and_group():
    from common.database_layout import DATABASE_LAYOUT_node, DATABASE_LAYOUT_group
    from utils.access import GOVERNED, REFERENCES
    for entity, layout in (('node', DATABASE_LAYOUT_node), ('group', DATABASE_LAYOUT_group)):
        governed = {c['column'][:-2] for c in layout if c['column'].endswith('id') and c['column'][:-2] in GOVERNED}
        missing = governed - set(REFERENCES[entity].values())
        assert not missing, f'{entity}: a body key names {sorted(missing)} and no r is required on it'


def test_a_write_may_only_name_objects_the_caller_can_read(client, world, db):
    from utils.helper import Helper
    hans = client.as_(world.ids['hans'])
    assert hans.post('/config/node/node002', _body('node', 'node002', group='compute-amd'))[0] == 200
    code, body = hans.post('/config/node/node002', _body('node', 'node002', group='compute-intel'))
    assert code == 404 and 'group compute-intel is not available' in body['message']
    assert hans.post('/config/node/node002', _body('node', 'node002', osimage='rocky9'))[0] == 200
    db.update('osimage', Helper().make_rows({'access': '770'}), [{'column': 'name', 'value': 'rocky9'}])
    code, body = hans.post('/config/node/node002', _body('node', 'node002', osimage='rocky9'))
    assert code == 404 and 'osimage rocky9 is not available' in body['message']
    code, body = hans.post('/config/node/node012', _body('node', 'node012', group='compute-amd', osimage='rocky9'))
    assert code == 404, 'a create names objects too'
    assert client.as_(world.ids['zed']).post('/config/node/node002', _body('node', 'node002', group='compute-intel'))[0] == 200


# TRIX-2141

def test_removing_hardware_needs_what_creating_it_needs(client, world, db):
    from utils.helper import Helper
    alice, hans = client.as_(world.ids['alice']), client.as_(world.ids['hans'])
    code, body = alice.get('/config/node/node001/_delete')
    assert code == 403 and 'removing a node needs' in body['message']
    assert alice.post('/config/node/node001', _body('node', 'node001', comment='w still works'))[0] == 200
    assert alice.get('/config/group/compute-intel/_delete')[0] == 200, 'a department object goes with w'
    assert hans.get('/config/node/node002/_delete')[0] == 200
    db.insert('bmcsetup', Helper().make_rows({'name': 'ipmi', 'usergroups': str(world.intel), 'access': '770'}))
    assert alice.get('/config/bmcsetup/ipmi/_delete')[0] == 403


# TRIX-2140

@pytest.fixture
def full_db(tmp_path, monkeypatch):
    """every table, so a show that joins its neighbours runs against empty ones"""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'full.db')
    database.local_thread.connection = None
    for table in DBStructure().tables:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def test_every_show_renders_owners_usergroups_and_access(full_db):
    from utils.helper import Helper
    from base.node import Node
    from base.group import Group
    from base.osimage import OSImage
    from base.bmcsetup import BMCSetup
    from base.redfishsetup import RedfishSetup
    from base.network import Network
    from base.switch import Switch
    db = full_db
    userid = db.insert('user', Helper().make_rows({'username': 'owner', 'source': 'local', 'enabled': '1', 'admin': '0', 'delegate': '0'}))
    ugid = db.insert('usergroup', Helper().make_rows({'name': 'dept', 'hardware': '0'}))
    columns = {'owners': str(userid), 'usergroups': str(ugid), 'access': '750'}
    db.insert('cluster', Helper().make_rows({'name': 'mycluster'}))
    imageid = db.insert('osimage', Helper().make_rows(dict(name='img', path='/x', **columns)))
    groupid = db.insert('group', Helper().make_rows(dict(name='grp', osimageid=imageid, **columns)))
    db.insert('node', Helper().make_rows(dict(name='node001', groupid=groupid, **columns)))
    db.insert('bmcsetup', Helper().make_rows(dict(name='bmc', **columns)))
    db.insert('redfishsetup', Helper().make_rows(dict(name='rf', **columns)))
    db.insert('network', Helper().make_rows(dict(name='net', network='10.1.0.0', subnet='16', **columns)))
    db.insert('switch', Helper().make_rows(dict(name='sw', **columns)))
    shows = [('node', 'node001', Node().get_node), ('group', 'grp', Group().get_group),
             ('osimage', 'img', OSImage().get_osimage), ('bmcsetup', 'bmc', BMCSetup().get_bmcsetup),
             ('redfishsetup', 'rf', RedfishSetup().get_redfishsetup), ('network', 'net', Network().get_network),
             ('switch', 'sw', Switch().get_switch)]
    context = _as(userid)
    try:
        for table, name, show in shows:
            status, response = show(name)
            assert status is True, (table, response)
            row = response['config'][table][name]
            assert (row.get('owners'), row.get('usergroups'), row.get('access')) == (['owner'], ['dept'], 'rwxr-x---'), (table, row)
    finally:
        context.pop()
