"""
The bit check (TRIX-2086), through the token decorator on routes of the real shape, so
the grammar, the check and the refusal codes are exercised together. The views are
stubs: what they would do is not the question, whether they are reached is.
"""
import json
import os
import types

import pytest
from flask import Blueprint, Flask
from jwt import encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['node', 'group', 'osimage', 'user', 'usergroup', 'usergroupmember', 'usergroupmap']


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'bits.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def world(db):
    """Two teams, five people, one node listed for intel at rwxr-x---, one node nobody touched."""
    from utils.helper import Helper

    def user(name, admin=False):
        return db.insert('user', Helper().make_rows({'username': name, 'source': 'local', 'enabled': '1',
                                                     'admin': '1' if admin else '0', 'delegate': '0'}))

    def member(userid, usergroupid, role):
        db.insert('usergroupmember', Helper().make_rows({'userid': userid, 'usergroupid': usergroupid,
                                                         'role': role, 'source': 'local'}))

    ids = {name: user(name) for name in ('alice', 'bob', 'carol', 'dave', 'erin')}
    ids['zed'] = user('zed', admin=True)
    intel = db.insert('usergroup', Helper().make_rows({'name': 'intel'}))
    other = db.insert('usergroup', Helper().make_rows({'name': 'other'}))
    db.insert('usergroup', Helper().make_rows({'name': 'third'}))
    member(ids['bob'], intel, 'manager')
    member(ids['carol'], intel, 'operator')
    member(ids['dave'], intel, 'reader')
    member(ids['erin'], other, 'operator')
    db.insert('node', Helper().make_rows({'name': 'node001', 'owners': str(ids['alice']),
                                          'usergroups': str(intel), 'access': '750'}))
    db.insert('node', Helper().make_rows({'name': 'node002'}))
    db.insert('osimage', Helper().make_rows({'name': 'rocky9', 'usergroups': str(intel), 'access': '774'}))
    return types.SimpleNamespace(ids=ids, intel=intel, other=other)


def _parsed(response):
    """A 204 carries no body by definition; everything else here is JSON."""
    return json.loads(response.data) if response.data else {}


@pytest.fixture
def client(db):
    from common.constant import CONSTANT
    from common.validate_auth import token_required
    from routes.config_access import access_blueprint

    stub = Blueprint('stub', __name__)

    @stub.route('/config/node/<string:name>', methods=['GET', 'POST'])
    @token_required
    def node(name=None):
        return json.dumps({'reached': name}), 200

    @stub.route('/config/node/<string:name>/_delete', methods=['GET'])
    @token_required
    def node_delete(name=None):
        return json.dumps({'reached': name}), 200

    @stub.route('/config/node', methods=['GET'])
    @token_required
    def nodes():
        return json.dumps({'reached': 'list'}), 200

    @stub.route('/config/osimage/<string:name>', methods=['GET', 'POST'])
    @token_required
    def osimage(name=None):
        return json.dumps({'reached': name}), 200

    @stub.route('/control/action/<string:subsystem>/<string:hostname>/_<string:action>', methods=['GET'])
    @token_required
    def control(subsystem=None, hostname=None, action=None):
        return json.dumps({'reached': action}), 200

    @stub.route('/hash', methods=['GET'])
    @token_required
    def hashes():
        return json.dumps({'reached': 'hash'}), 200

    @stub.route('/config/usergroup/<string:name>/members', methods=['POST'])
    @token_required
    def members(name=None):
        return json.dumps({'reached': name}), 200

    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(stub)
    app.register_blueprint(access_blueprint)
    key = CONSTANT['API']['SECRET_KEY']

    class Client:
        def __init__(self, token=None):
            self.token = token

        def as_(self, userid):
            """A separate client per identity, so two personas in one test do not share a token."""
            return Client(encode({'id': userid}, key, 'HS256'))

        def get(self, path):
            response = app.test_client().get(path, headers={'x-access-tokens': self.token})
            return response.status_code, _parsed(response)

        def post(self, path, body=None):
            response = app.test_client().post(path, headers={'x-access-tokens': self.token},
                                              data=json.dumps(body or {'config': {}}), content_type='application/json')
            return response.status_code, _parsed(response)

    return Client()


# ── the classes and the bits ────────────────────────────────────────────────

def test_the_owner_holds_the_owner_bits(client, world):
    me = client.as_(world.ids['alice'])
    assert me.get('/config/node/node001')[0] == 200
    assert me.post('/config/node/node001')[0] == 200
    assert me.get('/control/action/power/node001/_off')[0] == 200
    code, body = me.get('/config/node/node001/_delete')
    assert code == 403 and 'removing node node001 needs' in body['message'], 'w on a node does not remove hardware'


def test_the_object_caps_the_team_below_a_managers_role(client, world):
    """rwxr-x--- gives the listed usergroup r-x; a manager's rwx cap cannot add w."""
    me = client.as_(world.ids['bob'])
    assert me.get('/config/node/node001')[0] == 200
    code, body = me.post('/config/node/node001')
    assert code == 403
    assert body['message'] == 'node node001 requires w; you hold r-x (manager in intel)'
    assert me.get('/control/action/power/node001/_off')[0] == 200


def test_an_operator_powers_and_does_not_change(client, world):
    me = client.as_(world.ids['carol'])
    assert me.get('/control/action/power/node001/_off')[0] == 200
    assert me.get('/control/action/power/node001/_status')[0] == 200
    assert me.post('/config/node/node001')[0] == 403
    assert me.get('/config/node/node001/_delete')[0] == 403


def test_a_reader_looks_and_nothing_else(client, world):
    """The role caps the usergroup bits: r-x on the object, r-- for the reader."""
    me = client.as_(world.ids['dave'])
    assert me.get('/config/node/node001')[0] == 200
    assert me.get('/control/action/power/node001/_status')[0] == 200
    code, body = me.get('/control/action/power/node001/_off')
    assert code == 403 and 'requires x; you hold r-- (reader in intel)' in body['message']
    assert me.post('/config/node/node001')[0] == 403


def test_outside_the_scope_an_object_does_not_exist(client, world):
    me = client.as_(world.ids['erin'])
    code, body = me.get('/config/node/node001')
    assert code == 404 and body['message'] == 'node node001 is not available'
    assert me.post('/config/node/node001')[0] == 404
    assert me.get('/control/action/power/node001/_off')[0] == 404


def test_other_bits_apply_to_a_stranger_when_the_mode_grants_them(client, world):
    """rocky9 is rwxrwxr--: erin, in no listed usergroup, may read it and not change it."""
    me = client.as_(world.ids['erin'])
    assert me.get('/config/osimage/rocky9')[0] == 200
    code, body = me.post('/config/osimage/rocky9')
    assert code == 403 and body['message'].endswith('(other)')


def test_a_row_nobody_touched_is_rootus_owned_with_the_default_mode(client, world):
    """node002 has NULL columns: rwxrwx--- for rootus and nobody listed, so others get ---."""
    assert client.as_(world.ids['alice']).get('/config/node/node002')[0] == 404
    assert client.as_(world.ids['zed']).get('/config/node/node002')[0] == 200
    assert client.as_(0).get('/config/node/node002')[0] == 200


def test_the_admin_flag_and_id_zero_pass_everything(client, world):
    for userid in (world.ids['zed'], 0):
        me = client.as_(userid)
        assert me.post('/config/node/node001')[0] == 200
        assert me.get('/config/node/node001/_delete')[0] == 200
        assert me.get('/hash')[0] == 200
        assert me.post('/config/usergroup/intel/members')[0] == 200
        assert me.post('/config/node/newnode')[0] == 200, 'an admin may create'


def test_listings_pass_the_gate_and_rootus_routes_do_not(client, world):
    me = client.as_(world.ids['dave'])
    assert me.get('/config/node')[0] == 200, 'a listing is filtered per row, not gated'
    code, body = me.get('/hash')
    assert code == 403 and 'rootus and admin' in body['message']
    assert me.post('/config/usergroup/intel/members')[0] == 403, 'membership delegation is a later ticket'
    code, body = me.post('/config/node/newnode')
    assert code == 403 and 'creating a node needs' in body['message'], 'a reader creates nothing'


# ── chmod, chgrp, chown ─────────────────────────────────────────────────────

def _body(entity, name, **fields):
    return {'config': {entity: {name: fields}}}


def test_chmod_by_the_owner_changes_what_the_team_gets(client, world):
    alice, bob = client.as_(world.ids['alice']), client.as_(world.ids['bob'])
    assert bob.post('/config/node/node001')[0] == 403
    code, body = alice.post('/config/node/node001/_chmod', _body('node', 'node001', access='rwxrwx---'))
    assert code == 204, body
    assert bob.post('/config/node/node001')[0] == 200
    assert alice.post('/config/node/node001/_chmod', _body('node', 'node001', access='750'))[0] == 204, 'octal as chmod takes it'
    assert bob.post('/config/node/node001')[0] == 403
    assert alice.post('/config/node/node001/_chmod', _body('node', 'node001', access='770'))[0] == 204
    dave = client.as_(world.ids['dave'])
    code, body = dave.post('/config/node/node001/_chmod', _body('node', 'node001', access='rwxrwxrwx'))
    assert code == 403 and 'chmod is for owners' in body['message']
    assert client.as_(world.ids['erin']).post('/config/node/node001/_chmod', _body('node', 'node001', access='rwxrwxrwx'))[0] == 404


def test_a_bad_mode_or_an_ungoverned_entity_is_refused(client, world):
    alice = client.as_(world.ids['alice'])
    assert alice.post('/config/node/node001/_chmod', _body('node', 'node001', access='rwxr-x'))[0] == 400
    assert client.as_(0).post('/config/user/alice/_chmod', _body('user', 'alice', access='rwxrwxrwx'))[0] == 400


def test_chgrp_adds_only_a_usergroup_you_belong_to_even_as_owner(client, world, db):
    from utils.helper import Helper
    dave, erin, alice = client.as_(world.ids['dave']), client.as_(world.ids['erin']), client.as_(world.ids['alice'])
    code, body = dave.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups='+other'))
    assert code == 403 and 'only add usergroups you are a member of' in body['message']
    assert erin.get('/config/node/node001')[0] == 404, 'other is not listed yet'
    code, body = alice.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups='+other'))
    assert code == 403 and 'only add usergroups you are a member of' in body['message'], \
        'an owner outside the target team cannot hand the object to it: nothing leaves an organisation without a superuser'
    db.insert('usergroupmember', Helper().make_rows({'userid': world.ids['alice'], 'usergroupid': world.other,
                                                     'role': 'reader', 'source': 'local'}))
    assert alice.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups='+other'))[0] == 204, \
        'an owner who is a reader in the target team can'
    assert erin.get('/config/node/node001')[0] == 200, 'listed now: other gets the usergroup bits'
    code, body = dave.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups='-other'))
    assert code == 403 and 'removing a usergroup is for owners' in body['message']
    assert alice.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups=['intel']))[0] == 204
    assert erin.get('/config/node/node001')[0] == 404


def test_a_member_may_add_their_own_usergroup_to_an_object_they_can_read(client, world):
    """erin reads rocky9 through the other bits; as an operator in other she may list other on
    it, and not third, of which she is no member. A usergroup admin of a listed usergroup could."""
    erin = client.as_(world.ids['erin'])
    assert erin.post('/config/osimage/rocky9/_chgrp', _body('osimage', 'rocky9', usergroups='+other'))[0] == 204
    code, body = erin.post('/config/osimage/rocky9/_chgrp', _body('osimage', 'rocky9', usergroups='+third'))
    assert code == 403 and 'only add usergroups you are a member of' in body['message']
    assert erin.post('/config/osimage/rocky9/_chgrp', _body('osimage', 'rocky9', usergroups='+intel'))[0] == 204, \
        'intel is listed already: adding it again changes nothing and is not a foreign add'


def test_chown_stays_inside_the_organisation(client, world, db):
    from utils.helper import Helper
    db.insert('usergroupmember', Helper().make_rows({'userid': world.ids['bob'], 'usergroupid': world.intel,
                                                     'role': 'admin', 'source': 'local'}))
    db.delete_row('usergroupmember', [{'column': 'userid', 'value': world.ids['bob']},
                                      {'column': 'role', 'value': 'manager'}])
    bob = client.as_(world.ids['bob'])
    assert bob.post('/config/node/node001/_chown', _body('node', 'node001', owners='+dave'))[0] == 204
    code, body = bob.post('/config/node/node001/_chown', _body('node', 'node001', owners='+erin'))
    assert code == 403 and 'only chown to members of that usergroup' in body['message']
    dave = client.as_(world.ids['dave'])
    assert dave.post('/config/node/node001')[0] == 200, 'dave owns it now'
    code, body = dave.post('/config/node/node001/_chown', _body('node', 'node001', owners='+erin'))
    assert code == 403 and 'chown is for usergroup admins' in body['message']
    assert client.as_(0).post('/config/node/node001/_chown', _body('node', 'node001', owners=['erin']))[0] == 204
    assert client.as_(world.ids['erin']).post('/config/node/node001')[0] == 200
    assert client.as_(world.ids['alice']).get('/config/node/node001')[0] == 404, 'alice no longer owns it'


def test_an_unknown_name_in_a_list_is_refused_not_dropped(client, world):
    alice = client.as_(world.ids['alice'])
    code, body = alice.post('/config/node/node001/_chgrp', _body('node', 'node001', usergroups='+nowhere'))
    assert code == 400 and 'nowhere is not known' in body['message']


# ── modes ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('octal, text', [('750', 'rwxr-x---'), ('644', 'rw-r--r--'), ('770', 'rwxrwx---'),
                                         ('774', 'rwxrwxr--'), ('000', '---------'), ('777', 'rwxrwxrwx')])
def test_modes_round_trip(octal, text):
    from utils.access import Access
    assert Access().mode_text(octal) == text
    assert Access().mode_octal(text) == octal
