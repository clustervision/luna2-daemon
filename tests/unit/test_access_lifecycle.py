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


# TRIX-2337

@pytest.fixture
def routes(sqlite_db, monkeypatch):
    """The real node and group routes over a full schema: alice manages intel (no hardware
    flag), hans manages amd (hardware flag), zed is admin; locked objects only rootus reads."""
    import json
    import common.constant as constant
    from jwt import encode
    from utils.database import Database
    from utils.helper import Helper
    from routes.config_node import node_blueprint
    from routes.config_group import group_blueprint
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    db = Database()

    def insert(table, **row):
        return db.insert(table, Helper().make_rows(row))
    ids = {n: insert('user', username=n, source='local', enabled='1', admin='1' if n == 'zed' else '0', delegate='0')
           for n in ('alice', 'hans', 'zed')}
    intel, amd = insert('usergroup', name='intel', hardware='0'), insert('usergroup', name='amd', hardware='1')
    insert('usergroupmember', userid=ids['alice'], usergroupid=intel, role='manager', source='local')
    insert('usergroupmember', userid=ids['hans'], usergroupid=amd, role='manager', source='local')
    for table in ('bmcsetup', 'redfishsetup', 'osimage'):
        ids[table] = insert(table, name='locked', access='700')
    ids['g_intel'] = insert('group', name='compute-intel', usergroups=str(intel), access='770')
    ids['g_amd'] = insert('group', name='compute-amd', usergroups=str(amd), access='770')
    insert('node', name='node001', groupid=ids['g_intel'], usergroups=str(intel), access='770')
    insert('node', name='node002', groupid=ids['g_amd'], usergroups=str(amd), access='770')
    app = Flask(__name__)
    app.register_blueprint(node_blueprint)
    app.register_blueprint(group_blueprint)

    def post(who, entity, name, fields):
        claims = {'node': name, 'scope': 'provision'} if who == 'node' else {'id': ids[who]}
        token = encode(claims, constant.CONSTANT['API']['SECRET_KEY'], 'HS256')
        response = app.test_client().post(f'/config/{entity}/{name}', headers={'x-access-tokens': token},
                                          data=json.dumps({'config': {entity: {name: fields}}}), content_type='application/json')
        return response.status_code, (json.loads(response.data) if response.data else {}).get('message')

    def row(entity, name):
        return db.get_record(table=entity, where=f"name = '{name}'")[0]
    return ids, post, row


def test_a_body_may_not_set_an_id_column_of_a_node_or_group(routes):
    """the base writes a key naming a column as it stands, so an id in the body would
    walk past the hardware and reference checks, which read the names the API takes"""
    ids, post, row = routes
    cases = [('node', 'node001', 'bmcsetupid', ids['bmcsetup']), ('node', 'node001', 'redfishsetupid', ids['redfishsetup']),
             ('node', 'node001', 'osimageid', ids['osimage']), ('node', 'node001', 'groupid', ids['g_amd']),
             ('node', 'node001', 'id', 77), ('group', 'compute-intel', 'osimagetagid', 5),
             ('group', 'compute-intel', 'bmcsetupid', ids['bmcsetup']), ('group', 'compute-intel', 'id', 77)]
    for entity, name, key, value in cases:
        before = row(entity, name)
        code, message = post('alice', entity, name, {key: value})
        assert row(entity, name) == before, f'{entity} {key} was written'
        assert code == 403 and f'setting {key} on {entity} {name} is not permitted' in (message or ''), (entity, key)
    for entity, name, key, value in cases[:4] + cases[5:7]:
        assert post('zed', entity, name, {key: value})[0] == 204, (entity, key)
        assert str(row(entity, name)[key]) == str(value), f'admin sets {entity} {key}'
    assert post('alice', 'node', 'node001', {'bmcsetup': 'locked'})[0] == 403, 'the name form stays hardware'
    assert post('alice', 'node', 'node001', {'osimage': 'locked'})[0] == 404, 'the name form still needs r'
    assert post('alice', 'node', 'node001', {'comment': 'x'})[0] == 204
    assert post('hans', 'node', 'node002', {'tpm_uuid': 'abc'})[0] == 204, 'tpm_uuid is no id column'
    code, message = post('node', 'node', 'node001', {'groupid': ids['g_amd']})
    assert code == 403 and 'setting groupid on node node001' in (message or ''), 'a node token is refused too'
    assert post('node', 'node', 'node001', {'comment': 'x'})[0] == 204


# Columns a non-admin body may name although CONFIG_FIELDS does not list them: name is the
# route's own name; status is in HARDWARE_FIELDS but no body key gates it, which this pins as today.
PASSES_UNCLASSIFIED = {'node': {'name', 'status'}, 'group': {'name'}}


def test_every_node_and_group_column_in_a_body_is_refused_or_classified(routes):
    """A column a non-admin may name must be config or deliberately allowed: a new id
    column, or any new column, fails here until it is classified."""
    from utils.dbstructure import DBStructure
    from utils.access import CONFIG_FIELDS
    _, post, _ = routes
    unclassified = []
    for entity, name in (('node', 'node001'), ('group', 'compute-intel')):
        allowed = {c for c in CONFIG_FIELDS[entity] if not c.endswith('id')} | PASSES_UNCLASSIFIED[entity]
        for column in [c['column'] for c in DBStructure().get_database_table_structure(entity)]:
            code, _ = post('alice', entity, name, {column: name if column == 'name' else '1'})
            if code != 403 and column not in allowed:
                unclassified.append(f'{entity}.{column} ({code})')
    assert not unclassified, f'a non-admin body sets these past every gate: {unclassified}'
