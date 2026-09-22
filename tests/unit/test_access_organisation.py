"""
Organisations on (TRIX-2088): who may create what, what a new object inherits, the hardware
axis on node and group, and membership managed by a usergroup's own admins. Two derived
tests pin the shape: every insert into a governed table goes through the creator helper,
and every column of node and group is classified as config or hardware.
"""
import ast
import json
import os
import re
import types

import pytest
from flask import request, Blueprint, Flask, g
from jwt import encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['node', 'group', 'osimage', 'bmcsetup', 'network', 'user', 'usergroup', 'usergroupmember', 'usergroupmap']


# ── the derived half ────────────────────────────────────────────────────────

def _governed_inserts():
    """Every Database().insert into a governed table under base/ and utils/model.py, with
    whether its row argument is wrapped in Access().created_row."""
    from utils.access import GOVERNED
    found = []
    files = [os.path.join(DAEMON, 'base', n) for n in os.listdir(os.path.join(DAEMON, 'base')) if n.endswith('.py')]
    files.append(os.path.join(DAEMON, 'utils', 'model.py'))
    for path in files:
        with open(path, encoding='utf-8') as source:
            text = source.read()
        tree = ast.parse(text)
        self_table = re.search(r"self\.table\s*=\s*'(\w+)'", text)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'insert'
                    and isinstance(node.func.value, ast.Call) and getattr(node.func.value.func, 'id', None) == 'Database'):
                continue
            if len(node.args) < 2:
                continue
            target = node.args[0]
            if isinstance(target, ast.Constant):
                table = target.value
            elif isinstance(target, ast.Attribute) and target.attr == 'table' and self_table:
                table = self_table.group(1)
            elif isinstance(target, ast.Name) and target.id == 'table':
                # a variable table: the shared model creates any object and must go through the
                # helper; the inventory collector inserts child rows only, which carry nothing
                if 'nodeinventory.py' in path:
                    continue
                table = 'table'
            else:
                continue
            if table != 'table' and table not in GOVERNED:
                continue
            row = node.args[1]
            wrapped = (isinstance(row, ast.Call) and isinstance(row.func, ast.Attribute) and row.func.attr == 'created_row'
                       and isinstance(row.func.value, ast.Call) and getattr(row.func.value.func, 'id', None) == 'Access')
            found.append((os.path.relpath(path, DAEMON), node.lineno, table, wrapped))
    return found


def test_every_insert_into_a_governed_table_goes_through_the_creator_helper():
    inserts = _governed_inserts()
    assert len(inserts) >= 20, inserts
    bare = [f'{path}:{line} ({table})' for path, line, table, wrapped in inserts if not wrapped]
    assert not bare, ('inserts into governed tables whose row is not Access().created_row(...): '
                      + ', '.join(bare) + '. A new object must inherit or receive its owners, usergroups and access.')


def test_every_column_of_node_and_group_is_config_or_hardware():
    from utils.access import CONFIG_FIELDS, HARDWARE_FIELDS
    from utils.dbstructure import DBStructure
    meta = {'id', 'owners', 'usergroups', 'access'}
    for table in ('node', 'group'):
        columns = {c['column'] for c in DBStructure().get_database_table_structure(table)} - meta
        both = CONFIG_FIELDS[table] & HARDWARE_FIELDS[table]
        assert not both, f'{table}: fields on both lists: {sorted(both)}'
        unclassified = columns - CONFIG_FIELDS[table] - HARDWARE_FIELDS[table]
        assert not unclassified, f'{table}: columns neither config nor hardware: {sorted(unclassified)}'
        unknown = (CONFIG_FIELDS[table] | HARDWARE_FIELDS[table]) - columns
        assert not unknown, f'{table}: classified fields that are not columns: {sorted(unknown)}'


# ── the behaviour half ──────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'org.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def world(db):
    """intel (hardware flag off) with ivan admin, alice manager, carol reader; amd (hardware flag
    on) with hans manager; two networks, one readable by amd; a group per team; two nodes."""
    from utils.helper import Helper

    def user(name, admin=False):
        return db.insert('user', Helper().make_rows({'username': name, 'source': 'local', 'enabled': '1',
                                                     'admin': '1' if admin else '0', 'delegate': '0'}))

    def member(userid, usergroupid, role):
        db.insert('usergroupmember', Helper().make_rows({'userid': userid, 'usergroupid': usergroupid,
                                                         'role': role, 'source': 'local'}))

    ids = {n: user(n) for n in ('ivan', 'alice', 'carol', 'hans', 'tom')}
    ids['zed'] = user('zed', admin=True)
    intel = db.insert('usergroup', Helper().make_rows({'name': 'intel', 'hardware': '0'}))
    amd = db.insert('usergroup', Helper().make_rows({'name': 'amd', 'hardware': '1'}))
    member(ids['ivan'], intel, 'admin')
    member(ids['alice'], intel, 'manager')
    member(ids['carol'], intel, 'reader')
    member(ids['hans'], amd, 'manager')
    db.insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16',
                                             'usergroups': str(amd), 'access': '640'}))
    db.insert('network', Helper().make_rows({'name': 'fenced', 'network': '10.9.0.0', 'subnet': '16', 'access': '600'}))
    g_intel = db.insert('group', Helper().make_rows({'name': 'compute-intel', 'usergroups': str(intel), 'access': '770'}))
    g_amd = db.insert('group', Helper().make_rows({'name': 'compute-amd', 'usergroups': str(amd), 'access': '770'}))
    db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': g_intel, 'usergroups': str(intel), 'access': '770'}))
    db.insert('node', Helper().make_rows({'name': 'node002', 'groupid': g_amd, 'usergroups': str(amd), 'access': '770'}))
    db.insert('osimage', Helper().make_rows({'name': 'rocky9', 'access': '774'}))
    return types.SimpleNamespace(ids=ids, intel=intel, amd=amd, g_intel=g_intel, g_amd=g_amd)


@pytest.fixture
def client(db):
    from common.constant import CONSTANT
    from common.validate_auth import token_required
    from routes.config_usergroup import usergroup_blueprint

    stub = Blueprint('stub', __name__)

    for entity in ('node', 'group', 'osimage', 'profile', 'bmcsetup', 'network', 'switch'):
        def make(entity):
            def view(name=None, **_):
                # the body as the route would journal it, after the decorator ran
                return json.dumps({'reached': f'{entity} {name}', 'body': request.get_json(force=True, silent=True)}), 200
            return view
        stub.add_url_rule(f'/config/{entity}/<string:name>', endpoint=f'{entity}_post',
                          view_func=token_required(make(entity)), methods=['POST'])
        stub.add_url_rule(f'/config/{entity}/<string:name>/_delete', endpoint=f'{entity}_delete',
                          view_func=token_required(make(entity)), methods=['GET'])

    for entity in ('node', 'group'):
        stub.add_url_rule(f'/config/{entity}/<string:name>/interfaces/<string:interface>/_delete',
                          endpoint=f'{entity}_interface_delete', view_func=token_required(make(entity)), methods=['GET'])

    stub.add_url_rule('/boot/install/<string:node>', endpoint='boot_install', view_func=token_required(make('boot')), methods=['GET'])
    stub.add_url_rule('/boot/roles/<string:role>', endpoint='boot_roles', view_func=token_required(make('boot')), methods=['GET'])

    @stub.route('/config/node/<string:name>/interfaces', methods=['POST'])
    @token_required
    def interfaces(name=None):
        return json.dumps({'reached': 'interfaces'}), 200

    @stub.route('/config/osimage/<string:name>/_clone', methods=['POST'])
    @token_required
    def clone(name=None):
        return json.dumps({'reached': 'clone'}), 200

    @stub.route('/config/node/<string:name>/_clone', methods=['POST'])
    @token_required
    def clone_node(name=None):
        return json.dumps({'reached': 'clone'}), 200

    @stub.route('/control/action/<string:subsystem>/<string:hostname>/_<string:action>', methods=['GET'])
    @token_required
    def control(subsystem=None, hostname=None, action=None):
        return json.dumps({'reached': action}), 200

    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(stub)
    app.register_blueprint(usergroup_blueprint)
    key = CONSTANT['API']['SECRET_KEY']

    class Client:
        def __init__(self, token=None):
            self.token = token

        def as_(self, userid):
            return Client(encode({'id': userid}, key, 'HS256'))

        def get(self, path):
            response = app.test_client().get(path, headers={'x-access-tokens': self.token})
            return response.status_code, (json.loads(response.data) if response.data else {})

        def post(self, path, body=None):
            response = app.test_client().post(path, headers={'x-access-tokens': self.token},
                                              data=json.dumps(body if body is not None else {'config': {}}),
                                              content_type='application/json')
            return response.status_code, (json.loads(response.data) if response.data else {})

    return Client()


def _body(entity, name, **fields):
    return {'config': {entity: {name: fields}}}


def _as(userid):
    app = Flask(__name__)
    context = app.test_request_context('/')
    context.push()
    g.userid = userid
    return context


# creates

def test_a_reader_creates_nothing_and_a_manager_creates_a_department_object(client, world):
    carol, alice = client.as_(world.ids['carol']), client.as_(world.ids['alice'])
    code, body = carol.post('/config/osimage/new', _body('osimage', 'new'))
    assert code == 403 and 'creating a osimage is not permitted: it needs the admin or manager role' in body['message']
    assert alice.post('/config/osimage/new', _body('osimage', 'new'))[0] == 200
    assert alice.post('/config/group/newgroup', _body('group', 'newgroup'))[0] == 200
    assert alice.post('/config/profile/p1', _body('profile', 'p1'))[0] == 200


def test_the_hardware_catalogue_and_nodes_need_the_hardware_flag(client, world):
    alice, hans = client.as_(world.ids['alice']), client.as_(world.ids['hans'])
    code, body = alice.post('/config/bmcsetup/ipmi', _body('bmcsetup', 'ipmi'))
    assert code == 403 and 'with the hardware flag' in body['message']
    assert hans.post('/config/bmcsetup/ipmi', _body('bmcsetup', 'ipmi'))[0] == 200
    code, body = alice.post('/config/node/node010', _body('node', 'node010', group='compute-intel'))
    assert code == 403 and 'hardware flag' in body['message']
    assert hans.post('/config/node/node010', _body('node', 'node010', group='compute-amd'))[0] == 200


def test_a_department_creates_nodes_only_into_its_own_groups_on_networks_it_may_read(client, world):
    hans = client.as_(world.ids['hans'])
    code, body = hans.post('/config/node/node011', _body('node', 'node011', group='compute-intel'))
    assert code == 403 and 'into group compute-intel is not permitted' in body['message']
    code, body = hans.post('/config/node/node011', _body('node', 'node011'))
    assert code == 403 and 'needs a group' in body['message']
    ok = _body('node', 'node011', group='compute-amd', interfaces=[{'interface': 'BOOTIF', 'network': 'cluster'}])
    assert hans.post('/config/node/node011', ok)[0] == 200
    fenced = _body('node', 'node011', group='compute-amd', interfaces=[{'interface': 'BOOTIF', 'network': 'fenced'}])
    code, body = hans.post('/config/node/node011', fenced)
    assert code == 404 and 'network fenced is not available' in body['message'], 'rootus fences by withholding r'


def test_infrastructure_stays_with_rootus_and_admin(client, world):
    hans = client.as_(world.ids['hans'])
    code, body = hans.post('/config/network/newnet', _body('network', 'newnet'))
    assert code == 403 and 'is not permitted: that is for rootus and admin users' in body['message']
    assert client.as_(world.ids['zed']).post('/config/switch/sw1', _body('switch', 'sw1'))[0] == 200


def test_clone_is_a_create_with_r_on_the_source(client, world):
    carol, alice = client.as_(world.ids['carol']), client.as_(world.ids['alice'])
    assert carol.post('/config/osimage/rocky9/_clone', _body('osimage', 'rocky9', newosimage='mine'))[0] == 403
    assert alice.post('/config/osimage/rocky9/_clone', _body('osimage', 'rocky9', newosimage='mine'))[0] == 200


def test_a_node_clone_is_fenced_by_the_source_nodes_group_when_the_body_names_none(client, world):
    """A clone body names only the new node; the group comes from the source. The create
    fence must read it from there, or a department could never clone its own nodes."""
    hans, alice = client.as_(world.ids['hans']), client.as_(world.ids['alice'])
    assert hans.post('/config/node/node002/_clone', _body('node', 'node002', newnodename='node022'))[0] == 200, \
        'hans leads amd with the hardware flag; node002 sits in compute-amd, which lists amd'
    code, body = hans.post('/config/node/node001/_clone', _body('node', 'node001', newnodename='node023'))
    assert code == 404, 'node001 is intel\'s: not readable, so not a source'
    code, body = alice.post('/config/node/node001/_clone', _body('node', 'node001', newnodename='node024'))
    assert code == 403 and 'hardware flag' in body['message'], 'intel has no hardware flag: no node creates'


# inheritance

def test_a_department_create_carries_the_creators_columns_in_the_body_it_journals(client, world):
    """The owner and the usergroups the creator leads are written into the request body by
    the access check, before the route journals it: the peer replays that body as user 0 and
    must store the same columns. The default mode stays unset until a chmod."""
    alice = client.as_(world.ids['alice'])
    code, body = alice.post('/config/osimage/mine', _body('osimage', 'mine', path='/trinity/images/mine'))
    assert code == 200, body
    sent = body['body']['config']['osimage']['mine']
    assert sent['owners'] == str(world.ids['alice']) and sent['usergroups'] == str(world.intel)
    assert 'access' not in sent
    assert sent['path'] == '/trinity/images/mine', 'the rest of the body is untouched'
    hans = client.as_(world.ids['hans'])
    code, body = hans.post('/config/node/node013', _body('node', 'node013', group='compute-amd'))
    assert code == 200 and 'owners' not in body['body']['config']['node']['node013'], \
        'a node is left to copy its group at insert time, which both controllers can do alike'


def test_the_three_columns_cannot_be_set_through_a_create_or_update_body(client, world):
    """A w-holder could otherwise walk past chown, chgrp and chmod by naming the columns
    in an ordinary write; rootus and admin users keep the right, which the import needs."""
    alice = client.as_(world.ids['alice'])
    for payload in ({'access': '777'}, {'usergroups': str(world.amd)}, {'owners': '0'}):
        code, body = alice.post('/config/group/compute-intel', _body('group', 'compute-intel', **payload))
        assert code == 403 and 'changed with chown, chgrp and chmod' in body['message'], payload
        code, body = alice.post('/config/osimage/mine2', _body('osimage', 'mine2', **payload))
        assert code == 403 and 'changed with chown, chgrp and chmod' in body['message'], payload
    for userid in (0, world.ids['zed']):
        assert client.as_(userid).post('/config/group/compute-intel', _body('group', 'compute-intel', access='777'))[0] == 200


def test_a_node_created_into_a_group_copies_the_groups_columns(world):
    from utils.access import Access
    from utils.helper import Helper
    context = _as(world.ids['hans'])
    try:
        row = Access().created_row('node', Helper().make_rows({'name': 'node011', 'groupid': world.g_amd}))
    finally:
        context.pop()
    columns = {e['column']: e['value'] for e in row}
    assert columns['usergroups'] == str(world.amd) and columns['access'] == '770'


def test_rootus_and_admin_creates_leave_the_columns_alone(world):
    from utils.access import Access
    from utils.helper import Helper
    for userid in (0, world.ids['zed']):
        context = _as(userid)
        try:
            row = Access().created_row('osimage', Helper().make_rows({'name': 'x'}))
        finally:
            context.pop()
        assert {e['column'] for e in row} == {'name'}
    assert {e['column'] for e in Access().created_row('osimage', Helper().make_rows({'name': 'x'}))} == {'name'}, \
        'outside a request, as when the journal replays, nothing is added'
    row = Access().created_row('node', Helper().make_rows({'name': 'node012', 'groupid': world.g_amd}))
    assert {e['column']: e['value'] for e in row}['usergroups'] == str(world.amd), \
        'a node copies its group outside a request too: the peer inserts the same row'


# the hardware axis

def test_a_department_changes_config_fields_and_not_hardware_fields(client, world):
    alice = client.as_(world.ids['alice'])
    assert alice.post('/config/node/node001', _body('node', 'node001', kerneloptions='quiet'))[0] == 200
    code, body = alice.post('/config/node/node001', _body('node', 'node001', bmcsetup='ipmi', kerneloptions='quiet'))
    assert code == 403 and 'changing bmcsetup of node node001 is not permitted' in body['message']
    code, body = alice.post('/config/node/node001/interfaces', _body('node', 'node001', interfaces=[]))
    assert code == 403 and 'changing the interfaces of node node001 is not permitted' in body['message']
    assert alice.post('/config/group/compute-intel', _body('group', 'compute-intel', osimage='rocky9'))[0] == 200
    assert alice.post('/config/group/compute-intel', _body('group', 'compute-intel', domain='x'))[0] == 403


def test_the_hardware_flag_opens_the_hardware_fields(client, world, db):
    from utils.helper import Helper
    db.insert('bmcsetup', Helper().make_rows({'name': 'ipmi', 'usergroups': str(world.amd), 'access': '770'}))
    hans = client.as_(world.ids['hans'])
    assert hans.post('/config/node/node002', _body('node', 'node002', bmcsetup='ipmi'))[0] == 200
    assert hans.post('/config/node/node002/interfaces', _body('node', 'node002', interfaces=[]))[0] == 200
    assert client.as_(world.ids['zed']).post('/config/node/node001', _body('node', 'node001', bmcsetup='ipmi'))[0] == 200


# membership delegation

def test_a_usergroups_own_admin_manages_its_members_and_a_manager_does_not(client, world):
    ivan, alice = client.as_(world.ids['ivan']), client.as_(world.ids['alice'])
    body = _body('usergroup', 'intel', username='tom', role='operator')
    assert ivan.post('/config/usergroup/intel/members', body)[0] == 201
    assert ivan.get('/config/usergroup/intel/members')[1]['config']['usergroup']['intel']['members']['tom'] == 'operator'
    code, reply = alice.post('/config/usergroup/intel/members', body)
    assert code == 403 and 'managed by its admins' in reply['message']
    assert ivan.post('/config/usergroup/amd/members', _body('usergroup', 'amd', username='tom', role='reader'))[0] == 403
    assert ivan.post('/config/usergroup/newteam', _body('usergroup', 'newteam'))[0] == 403, \
        'creating usergroups stays with rootus and admin'


def test_whoami_and_the_usergroup_show_the_hardware_flag(client, world, db):
    from base.user import User
    from base.usergroup import UserGroup
    context = _as(world.ids['hans'])
    try:
        status, answer = User().whoami(world.ids['hans'])
        assert answer['usergroups'] == {'amd': 'manager'} and answer['hardware'] == ['amd']
        status, groups = UserGroup().get_usergroup('amd')
        assert groups['config']['usergroup']['amd']['hardware'] is True
    finally:
        context.pop()


# the worked example, compactly

def test_the_tester_operates_two_nodes_and_cannot_reconfigure_them(client, world, db):
    from utils.helper import Helper
    test = db.insert('usergroup', Helper().make_rows({'name': 'intel-a-test'}))
    db.insert('usergroupmember', Helper().make_rows({'userid': world.ids['tom'], 'usergroupid': test, 'role': 'operator', 'source': 'local'}))
    db.update('node', Helper().make_rows({'usergroups': f'{world.intel},{test}'}), [{'column': 'name', 'value': 'node001'}])
    tom = client.as_(world.ids['tom'])
    assert tom.get('/control/action/power/node001/_reset')[0] == 200
    code, body = tom.post('/config/node/node001', _body('node', 'node001', kerneloptions='x'))
    assert code == 403 and 'changing node node001 is not permitted: you may read and operate it (operator role)' in body['message']
