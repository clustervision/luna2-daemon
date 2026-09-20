"""
Luna users, usergroups, memberships and the directory map (TRIX-2082).

Every write goes through the real routes, the journal (a no-op outside HA), the base
classes and the SQLite data layer. Nothing is enforced yet: an admin token does all of it.
"""
import json
import os

import pytest
from flask import Flask
from jwt import decode, encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['user', 'usergroup', 'usergroupmember', 'usergroupmap']


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'users.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    # a login walks the authentication chain, whose sources are plugin files
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def client(db):
    from common.constant import CONSTANT
    from routes.config_user import user_blueprint
    from routes.config_usergroup import usergroup_blueprint

    app = Flask(__name__)
    app.register_blueprint(user_blueprint)
    app.register_blueprint(usergroup_blueprint)
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    class Client:
        def get(self, path):
            return app.test_client().get(path, headers={'x-access-tokens': token})

        def post(self, path, body):
            return app.test_client().post(path, headers={'x-access-tokens': token},
                                          data=json.dumps(body), content_type='application/json')

        def user(self, name, **fields):
            return self.post(f'/config/user/{name}', {'config': {'user': {name: fields}}})

        def usergroup(self, name, **fields):
            return self.post(f'/config/usergroup/{name}', {'config': {'usergroup': {name: fields}}})

        def member(self, group, **fields):
            return self.post(f'/config/usergroup/{group}/members', {'config': {'usergroup': {group: fields}}})

        def unmember(self, group, **fields):
            return self.post(f'/config/usergroup/{group}/members/_remove', {'config': {'usergroup': {group: fields}}})

        def map(self, **fields):
            return self.post('/config/usergroupmap', {'config': {'usergroupmap': fields}})

        def unmap(self, **fields):
            return self.post('/config/usergroupmap/_remove', {'config': {'usergroupmap': fields}})

    return Client()


def _body(response):
    return json.loads(response.data)


# ── users ───────────────────────────────────────────────────────────────────

def test_a_user_is_created_and_shown_without_its_password(client, db):
    assert client.user('alice', password='s3cret').status_code == 201
    shown = _body(client.get('/config/user/alice'))['config']['user']['alice']
    assert 'password' not in shown
    assert shown['password_set'] is True
    assert shown['enabled'] is True and shown['admin'] is False and shown['delegate'] is False
    assert shown['source'] == 'local'
    assert shown['createdby'] == 'luna', 'the creator is the INI account behind token id 0'
    assert shown['usergroups'] == {}
    stored = db.get_record(table='user', where="username = 'alice'")[0]['password']
    assert stored.startswith('pbkdf2_sha256$') and 's3cret' not in stored


def test_the_user_list_and_a_missing_user(client):
    assert client.get('/config/user').status_code == 404
    client.user('alice', password='x')
    client.user('bob')
    assert sorted(_body(client.get('/config/user'))['config']['user']) == ['alice', 'bob']
    assert client.get('/config/user/carol').status_code == 404


def test_a_user_without_a_password_is_recorded_as_such(client):
    client.user('bob')
    assert _body(client.get('/config/user/bob'))['config']['user']['bob']['password_set'] is False


def test_unknown_fields_are_refused_not_ignored(client):
    response = client.user('alice', colour='blue')
    assert response.status_code == 400
    assert 'colour' in _body(response)['message']


def test_a_user_is_renamed_and_flags_are_changed(client):
    client.user('alice', password='x')
    assert client.user('alice', newusername='alicia', admin=True, enabled=False).status_code == 204
    assert client.get('/config/user/alice').status_code == 404
    shown = _body(client.get('/config/user/alicia'))['config']['user']['alicia']
    assert shown['admin'] is True and shown['enabled'] is False
    assert shown['password_set'] is True, 'a rename keeps the digest'


def test_a_rename_onto_an_existing_user_is_refused(client):
    client.user('alice')
    client.user('bob')
    assert client.user('alice', newusername='bob').status_code == 400


def test_deleting_a_user_takes_its_memberships_with_it(client, db):
    client.user('alice')
    client.usergroup('intel')
    client.member('intel', username='alice', role='reader')
    assert db.get_record(table='usergroupmember')
    assert client.get('/config/user/alice/_delete').status_code == 204
    assert not db.get_record(table='usergroupmember')
    assert client.get('/config/user/alice').status_code == 404


# ── login ───────────────────────────────────────────────────────────────────

def _login(monkeypatch, username, password):
    from common.constant import CONSTANT
    from base.authentication import Authentication
    monkeypatch.setitem(CONSTANT['API'], 'EXPIRY', '3600')
    status, response = Authentication().get_token({'username': username, 'password': password})
    if status:
        return decode(response['token'], CONSTANT['API']['SECRET_KEY'], algorithms=['HS256'])['id']
    return response['message']


def test_login_with_a_user_password_mints_that_users_id(client, db, monkeypatch):
    client.user('alice', password="it's")
    userid = db.get_record(table='user', where="username = 'alice'")[0]['id']
    assert _login(monkeypatch, 'alice', "it's") == userid, 'a quote in a password must survive the input filter'
    assert db.get_record(table='user', where="username = 'alice'")[0]['lastlogin'], 'lastlogin is stamped'


def test_a_wrong_password_a_disabled_user_and_a_stranger_are_refused(client, monkeypatch):
    client.user('alice', password='right')
    assert 'Incorrect password' in _login(monkeypatch, 'alice', 'wrong')
    client.user('alice', enabled=False)
    assert 'disabled' in _login(monkeypatch, 'alice', 'right')
    assert 'not known to any authentication source' in _login(monkeypatch, 'nobody', 'x')


def test_a_user_without_a_digest_cannot_log_in_locally(client, monkeypatch):
    """local answers not-known for a row without a digest, so the chain moves on; with no
    other source claiming the name, the login is refused."""
    client.user('bob')
    assert 'not known to any authentication source' in _login(monkeypatch, 'bob', 'anything')


def test_the_configuration_file_account_still_mints_id_zero(db, monkeypatch):
    assert _login(monkeypatch, 'luna', 'luna') == 0


def test_an_empty_password_removes_the_digest(client, monkeypatch):
    client.user('alice', password='x')
    client.user('alice', password='')
    assert 'not known to any authentication source' in _login(monkeypatch, 'alice', 'x')


# ── usergroups and members ──────────────────────────────────────────────────

def test_a_usergroup_is_created_renamed_and_deleted(client):
    assert client.usergroup('intel', comment='Intel Corporation').status_code == 201
    shown = _body(client.get('/config/usergroup/intel'))['config']['usergroup']['intel']
    assert shown == {'comment': 'Intel Corporation', 'members': {}}
    assert client.usergroup('intel', newusergroupname='intel-nl').status_code == 204
    assert client.get('/config/usergroup/intel').status_code == 404
    assert client.get('/config/usergroup/intel-nl/_delete').status_code == 204
    assert client.get('/config/usergroup').status_code == 404


def test_members_are_not_accepted_in_the_usergroup_body(client):
    response = client.usergroup('intel', members={'alice': 'admin'})
    assert response.status_code == 400
    assert 'members' in _body(response)['message']


def test_a_member_is_added_re_roled_listed_and_removed(client):
    client.user('alice')
    client.usergroup('intel')
    assert client.member('intel', username='alice', role='reader').status_code == 201
    assert _body(client.get('/config/usergroup/intel/members'))['config']['usergroup']['intel']['members'] == {'alice': 'reader'}
    assert client.member('intel', username='alice', role='admin').status_code == 204
    assert _body(client.get('/config/usergroup/intel'))['config']['usergroup']['intel']['members'] == {'alice': 'admin'}
    assert _body(client.get('/config/user/alice'))['config']['user']['alice']['usergroups'] == {'intel': 'admin'}
    assert client.unmember('intel', username='alice').status_code == 204
    assert _body(client.get('/config/usergroup/intel/members'))['config']['usergroup']['intel']['members'] == {}


def test_one_user_holds_a_different_role_per_usergroup(client):
    client.user('alice')
    client.usergroup('intel')
    client.usergroup('intel-a')
    client.member('intel', username='alice', role='admin')
    client.member('intel-a', username='alice', role='reader')
    assert _body(client.get('/config/user/alice'))['config']['user']['alice']['usergroups'] == {
        'intel': 'admin', 'intel-a': 'reader'}


def test_a_role_the_code_does_not_know_is_refused(client):
    client.user('alice')
    client.usergroup('intel')
    response = client.member('intel', username='alice', role='owner')
    assert response.status_code == 400
    assert 'admin, manager, operator, reader' in _body(response)['message']


def test_membership_needs_an_existing_user_and_usergroup(client):
    client.usergroup('intel')
    assert client.member('intel', username='ghost', role='reader').status_code == 404
    client.user('alice')
    assert client.member('nowhere', username='alice', role='reader').status_code == 404
    assert client.unmember('intel', username='alice').status_code == 404


def test_deleting_a_usergroup_takes_memberships_and_map_rows_with_it(client, db):
    client.user('alice')
    client.usergroup('intel')
    client.member('intel', username='alice', role='reader')
    client.map(source='ldap', external_group='cn=hpc-intel,ou=groups,dc=example,dc=com', usergroup='intel', role='reader')
    assert client.get('/config/usergroup/intel/_delete').status_code == 204
    assert not db.get_record(table='usergroupmember')
    assert not db.get_record(table='usergroupmap')


# ── the directory map ───────────────────────────────────────────────────────

DN = 'cn=hpc intel-admins,ou=groups,dc=example,dc=com'


def test_a_map_entry_keeps_the_directory_name_exactly(client, db):
    client.usergroup('intel')
    assert client.map(source='ldap', external_group=DN, usergroup='intel', role='admin').status_code == 201
    entries = _body(client.get('/config/usergroupmap'))['config']['usergroupmap']
    assert entries == [{'source': 'ldap', 'external_group': DN, 'usergroup': 'intel', 'role': 'admin'}]
    assert db.get_record(table='usergroupmap')[0]['external_group'] == DN, 'commas, equals signs and spaces survive'


def test_two_directory_groups_feed_one_usergroup_with_different_roles(client):
    client.usergroup('intel')
    client.map(source='ldap', external_group=DN, usergroup='intel', role='admin')
    client.map(source='ldap', external_group='cn=hpc-intel,ou=groups,dc=example,dc=com', usergroup='intel', role='reader')
    roles = {e['external_group']: e['role'] for e in _body(client.get('/config/usergroupmap'))['config']['usergroupmap']}
    assert roles == {DN: 'admin', 'cn=hpc-intel,ou=groups,dc=example,dc=com': 'reader'}


def test_a_map_entry_is_updated_by_its_key_and_removed(client):
    client.usergroup('intel')
    client.usergroup('intel-a')
    client.map(source='ldap', external_group=DN, usergroup='intel', role='admin')
    assert client.map(source='ldap', external_group=DN, usergroup='intel-a', role='reader').status_code == 204
    entries = _body(client.get('/config/usergroupmap'))['config']['usergroupmap']
    assert entries == [{'source': 'ldap', 'external_group': DN, 'usergroup': 'intel-a', 'role': 'reader'}]
    assert client.unmap(source='ldap', external_group=DN).status_code == 204
    assert client.get('/config/usergroupmap').status_code == 404


def test_a_map_entry_needs_its_key_a_known_usergroup_and_a_known_role(client):
    client.usergroup('intel')
    assert client.map(source='ldap', usergroup='intel', role='admin').status_code == 400
    assert client.map(source='ldap', external_group=DN, usergroup='nowhere', role='admin').status_code == 404
    assert client.map(source='ldap', external_group=DN, usergroup='intel', role='boss').status_code == 400
    assert client.map(source='ldap', external_group="cn=o'brien,dc=x", usergroup='intel', role='admin').status_code == 400


# ── upgrade and layout ──────────────────────────────────────────────────────

def test_an_old_user_table_gains_the_identity_columns_at_the_structure_check(tmp_path):
    """The migrator only adds columns, and that is all an upgrade needs here."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'old.db')
    database.local_thread.connection = None
    old = [{"column": "id", "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
           {"column": "username", "datatype": "VARCHAR", "length": "50"},
           {"column": "password", "datatype": "VARCHAR", "length": "100"},
           {"column": "roleid", "datatype": "INTEGER", "length": "10"},
           {"column": "createdby", "datatype": "INTEGER", "length": "10"},
           {"column": "lastlogin", "datatype": "VARCHAR", "length": "50"},
           {"column": "created", "datatype": "NUMERIC"}]
    Database().create('user', old)
    DBStructure().check_and_fix_table_layout('user')
    columns = set(Database().get_columns('user'))
    assert {'source', 'external_id', 'enabled', 'admin', 'delegate'} <= columns
    assert {'username', 'roleid', 'createdby'} <= columns, 'legacy columns stay, so every cluster has one shape'
    database.local_thread.connection = None


def test_lastlogin_is_not_part_of_the_controller_hash(client, db, monkeypatch):
    """A login on one controller must not make the pair disagree until the next hard sync."""
    from utils.tables import Tables
    client.user('alice', password='x')
    before = Tables().get_table_hashes()['user']
    db.update('user', [{'column': 'lastlogin', 'value': '2026-09-20 12:00:00'}],
              [{'column': 'username', 'value': 'alice'}])
    assert Tables().get_table_hashes()['user'] == before
