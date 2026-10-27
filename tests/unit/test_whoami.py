"""
GET /whoami (TRIX-2089): who a token belongs to, from the id the token decorator stores.
"""
import json
import os
import sys
import types

import pytest
from flask import Flask
from jwt import encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['user', 'usergroup', 'usergroupmember', 'usergroupmap']


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'whoami.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def app(db):
    from routes.auth import auth_blueprint
    from routes.config_user import user_blueprint
    from routes.config_usergroup import usergroup_blueprint

    flask_app = Flask(__name__)
    for blueprint in (auth_blueprint, user_blueprint, usergroup_blueprint):
        flask_app.register_blueprint(blueprint)
    return flask_app.test_client()


def _token(userid):
    from common.constant import CONSTANT
    return encode({'id': userid}, CONSTANT['API']['SECRET_KEY'], 'HS256')


def _admin_post(app, path, body):
    response = app.post(path, headers={'x-access-tokens': _token(0)},
                        data=json.dumps(body), content_type='application/json')
    assert response.status_code in (201, 204), (path, response.data)


def _login(app, username, password):
    response = app.post('/token', data=json.dumps({'username': username, 'password': password}),
                        content_type='application/json')
    assert response.status_code == 201, response.data
    return json.loads(response.data)['token']


def _whoami(app, token):
    response = app.get('/whoami', headers={'x-access-tokens': token})
    return response.status_code, json.loads(response.data)


def test_the_configuration_file_account(app):
    code, body = _whoami(app, _token(0))
    assert code == 200
    assert body == {'user': 'luna', 'id': 0, 'source': 'ini', 'admin': True, 'usergroups': {}, 'hardware': []}


def test_a_local_user_with_its_usergroups_and_roles(app, db):
    _admin_post(app, '/config/user/alice', {'config': {'user': {'alice': {'password': 'x', 'admin': True}}}})
    _admin_post(app, '/config/usergroup/intel', {'config': {'usergroup': {'intel': {}}}})
    _admin_post(app, '/config/usergroup/intel-a', {'config': {'usergroup': {'intel-a': {}}}})
    _admin_post(app, '/config/usergroup/intel/members', {'config': {'usergroup': {'intel': {'username': 'alice', 'role': 'admin'}}}})
    _admin_post(app, '/config/usergroup/intel-a/members', {'config': {'usergroup': {'intel-a': {'username': 'alice', 'role': 'reader'}}}})
    token = _login(app, 'alice', 'x')
    code, body = _whoami(app, token)
    assert code == 200
    assert body['user'] == 'alice' and body['source'] == 'local' and body['admin'] is True
    assert body['usergroups'] == {'intel': 'admin', 'intel-a': 'reader'}
    assert body['id'] == db.get_record(table='user', where="username = 'alice'")[0]['id']


def test_an_os_user_created_at_login_with_mapped_usergroups(app, db, monkeypatch):
    import pwd
    import grp
    from common.constant import CONSTANT
    monkeypatch.setitem(CONSTANT, 'AUTH', {'CHAIN': 'local, pam'})
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: types.SimpleNamespace(pw_name=name, pw_uid=1500, pw_gid=1500))
    monkeypatch.setattr(os, 'getgrouplist', lambda name, gid: [1500, 2001])
    monkeypatch.setattr(grp, 'getgrgid', lambda gid: types.SimpleNamespace(gr_name={1500: 'ossam', 2001: 'hpc-intel'}[gid]))
    monkeypatch.setitem(sys.modules, 'pam', types.SimpleNamespace(
        pam=lambda: types.SimpleNamespace(authenticate=lambda n, p, service='login': p == 'ospass', reason='')))
    _admin_post(app, '/config/usergroup/intel', {'config': {'usergroup': {'intel': {}}}})
    _admin_post(app, '/config/usergroupmap', {'config': {'usergroupmap': {
        'source': 'pam', 'external_group': 'hpc-intel', 'usergroup': 'intel', 'role': 'operator'}}})
    token = _login(app, 'ossam', 'ospass')
    code, body = _whoami(app, token)
    assert code == 200
    assert body['user'] == 'ossam' and body['source'] == 'pam' and body['admin'] is False
    assert body['usergroups'] == {'intel': 'operator'}


def test_a_token_for_a_deleted_or_disabled_user_is_refused(app, db):
    _admin_post(app, '/config/user/alice', {'config': {'user': {'alice': {'password': 'x'}}}})
    token = _login(app, 'alice', 'x')
    assert _whoami(app, token)[0] == 200
    _admin_post(app, '/config/user/alice', {'config': {'user': {'alice': {'enabled': False}}}})
    code, body = _whoami(app, token)
    assert code == 401 and 'disabled' in body['message']
    response = app.get('/config/user/alice/_delete', headers={'x-access-tokens': _token(0)})
    assert response.status_code == 204
    code, body = _whoami(app, token)
    assert code == 401 and 'no longer exists' in body['message']


def test_whoami_needs_a_token(app):
    assert app.get('/whoami').status_code == 401
