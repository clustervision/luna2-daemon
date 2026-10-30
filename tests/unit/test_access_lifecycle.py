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
    assert code == 401 and 'user hans is disabled' in body['message']
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
    assert User().whoami(world.ids['tom']) == (False, 'Authentication error: user tom is disabled')
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
    assert Access().annotate('osimage', image)['owners'] == 'rootus'


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
    assert code == 403 and 'removing node node001 is not permitted' in body['message']
    assert alice.post('/config/node/node001', _body('node', 'node001', comment='w still works'))[0] == 200
    assert alice.get('/config/group/compute-intel/_delete')[0] == 200, 'a department object goes with w'
    assert hans.get('/config/node/node002/_delete')[0] == 200
    db.insert('bmcsetup', Helper().make_rows({'name': 'ipmi', 'usergroups': str(world.intel), 'access': '770'}))
    assert alice.get('/config/bmcsetup/ipmi/_delete')[0] == 403
    code, body = alice.get('/config/node/node001/interfaces/BOOTIF/_delete')
    assert code == 403 and 'removing an interface of node node001 is not permitted' in body['message']
    assert hans.get('/config/node/node002/interfaces/BOOTIF/_delete')[0] == 200
    code, body = alice.get('/config/group/compute-intel/interfaces/BOOTIF/_delete')
    assert code == 403 and 'interface of group compute-intel' in body['message']


def test_removing_infrastructure_stays_with_rootus_and_admin(client, world, db):
    from utils.helper import Helper
    hans, zed = client.as_(world.ids['hans']), client.as_(world.ids['zed'])
    db.insert('network', Helper().make_rows({'name': 'mine', 'network': '10.8.0.0', 'subnet': '16',
                                             'owners': str(world.ids['hans']), 'access': '700'}))
    assert hans.post('/config/network/mine', _body('network', 'mine', comment='w on my own network'))[0] == 200
    code, body = hans.get('/config/network/mine/_delete')
    assert code == 403 and 'removing network mine is not permitted: that is for rootus and admin users' in body['message']
    assert zed.get('/config/network/mine/_delete')[0] == 200


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
            assert (row.get('owners'), row.get('usergroups'), row.get('access')) == ('owner', 'dept', 'rwxr-x---'), (table, row)
    finally:
        context.pop()


# TRIX-2144

def test_the_backup_path_is_rootus():
    """the export carries every table, secrets and user digests included, so r on the
    cluster row, which everyone holds, cannot be enough for it; import writes them all"""
    from routes.config_cluster import config_cluster_export, config_cluster_import
    assert config_cluster_export.requires == 'rootus'
    assert config_cluster_import.requires == 'rootus'


# TRIX-2145

def test_a_persons_fetch_of_a_nodes_install_script_is_reprovisioning(client, world):
    """the script carries the node's provision token, so handing it out is the x act;
    the role, profile and script feeds are for nodes"""
    carol, ivan, hans, zed = (client.as_(world.ids[n]) for n in ('carol', 'ivan', 'hans', 'zed'))
    code, body = carol.get('/boot/install/node001')
    assert code == 403 and 'operating node node001 is not permitted' in body['message']
    assert ivan.get('/boot/install/node001')[0] == 200
    assert hans.get('/boot/install/node001')[0] == 404
    code, body = ivan.get('/boot/roles/compute')
    assert code == 403 and 'for nodes, rootus and admin users' in body['message']
    assert zed.get('/boot/roles/compute')[0] == 200


# TRIX-2336

def test_a_groups_bmc_and_redfish_setup_are_hardware(client, world, db):
    alice = client.as_(world.ids['alice'])
    for fields in ({'bmcsetupname': 'ipmi'}, {'redfishsetupname': 'rf'}, {'redfishsetupname': ''}):
        code, body = alice.post('/config/group/compute-intel', _body('group', 'compute-intel', **fields))
        assert code == 403, f'{fields}: intel has no hardware flag'
        assert f'changing {next(iter(fields))} of group compute-intel is not permitted' in body['message']


def test_a_group_may_only_name_a_bmc_or_redfish_setup_the_caller_can_read(client, world, db):
    from utils.dbstructure import DBStructure
    from utils.helper import Helper
    db.create('redfishsetup', DBStructure().get_database_table_structure('redfishsetup'))
    for table in ('bmcsetup', 'redfishsetup'):
        db.insert(table, Helper().make_rows({'name': 'mine', 'usergroups': str(world.amd), 'access': '770'}))
        db.insert(table, Helper().make_rows({'name': 'locked', 'access': '700'}))
    hans = client.as_(world.ids['hans'])
    for key, table in (('bmcsetupname', 'bmcsetup'), ('redfishsetupname', 'redfishsetup')):
        assert hans.post('/config/group/compute-amd', _body('group', 'compute-amd', **{key: 'mine'}))[0] == 200
        code, body = hans.post('/config/group/compute-amd', _body('group', 'compute-amd', **{key: 'locked'}))
        assert code == 404, f'{key}: {table} locked is not readable by amd'
        assert f'{table} locked is not available' in body['message']


def _body_keys(entity):
    """What a node or group body carries: the table's columns, the named references the
    base resolves to their id columns, and every key the base module tests the body for."""
    import ast
    import importlib
    from utils.dbstructure import DBStructure
    module = importlib.import_module(f'base.{entity}')
    names = {key: value[0] if isinstance(value, tuple) else key for key, value in module.NAME_REFERENCES.items()}
    keys = {c['column'] for c in DBStructure().get_database_table_structure(entity)} | set(names)
    with open(module.__file__, encoding='utf-8') as source:
        for node in ast.walk(ast.parse(source.read())):
            if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant)
                    and isinstance(node.ops[0], (ast.In, ast.NotIn)) and getattr(node.comparators[0], 'id', None) == 'data'):
                keys.add(node.left.value)
    return keys, names


def test_hardware_and_reference_keys_are_keys_a_node_or_group_body_carries():
    from utils.access import HARDWARE_KEYS, REFERENCES
    wrong = []
    for entity in ('node', 'group'):
        keys, names = _body_keys(entity)
        wrong += [f'{entity} HARDWARE_KEYS {key}' for key in sorted(HARDWARE_KEYS[entity] - keys)]
        wrong += [f'{entity} REFERENCES {key}' for key in sorted(set(REFERENCES[entity]) - keys)]
        wrong += [f'{entity} REFERENCES {key} -> {table}, the base resolves it in {names[key]}'
                  for key, table in REFERENCES[entity].items() if key in names and names[key] != table]
    assert not wrong, f'keys no body carries, so the gate never sees them: {wrong}'
