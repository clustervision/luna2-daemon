"""
Portal delegation (TRIX-2122): a user carrying the delegate flag obtains, at the token
exchange, the token of a person it vouches for; that token is the person's own. A delegate
never acts as itself: every route refuses its own token. The flag is the boolean on the
user row and nothing else.
"""
import json
import os
import sys
import types

import pytest
from flask import Flask
from jwt import decode, encode

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['node', 'user', 'usergroup', 'usergroupmember', 'usergroupmap']


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'delegation.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    monkeypatch.setitem(constant.CONSTANT, 'AUTH', {'CHAIN': 'local, pam'})
    monkeypatch.setitem(constant.CONSTANT, 'AUDIT', {'LOGFILE': str(tmp_path / 'audit.log')})
    from utils.audit import Audit
    Audit._logger = None
    yield Database()
    for handler in list(Audit.logger().handlers):
        handler.close()
        Audit.logger().removeHandler(handler)
    Audit._logger = None
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def app(db):
    from routes.auth import auth_blueprint
    from routes.config_node import node_blueprint
    from routes.config_user import user_blueprint
    from routes.config_usergroup import usergroup_blueprint
    flask_app = Flask(__name__)
    for blueprint in (auth_blueprint, node_blueprint, user_blueprint, usergroup_blueprint):
        flask_app.register_blueprint(blueprint)
    return flask_app.test_client()


@pytest.fixture
def world(app, db):
    """ood is the portal's delegate; alice a local user in intel; bob has no flag."""
    from utils.helper import Helper
    admin = {'x-access-tokens': encode({'id': 0}, 'test', 'HS256')}

    def post(path, body):
        response = app.post(path, headers=admin, data=json.dumps(body), content_type='application/json')
        assert response.status_code in (201, 204), (path, response.data)
    post('/config/user/ood', {'config': {'user': {'ood': {'password': 'ood-pw', 'delegate': True}}}})
    post('/config/user/alice', {'config': {'user': {'alice': {'password': 'alice-pw'}}}})
    post('/config/user/bob', {'config': {'user': {'bob': {'password': 'bob-pw'}}}})
    post('/config/usergroup/intel', {'config': {'usergroup': {'intel': {}}}})
    post('/config/usergroup/intel/members', {'config': {'usergroup': {'intel': {'username': 'alice', 'role': 'manager'}}}})
    db.insert('node', Helper().make_rows({'name': 'node001', 'usergroups': str(db.get_record(table='usergroup')[0]['id']), 'access': '770'}))
    return types.SimpleNamespace(alice=db.get_record(table='user', where="username = 'alice'")[0]['id'],
                                 ood=db.get_record(table='user', where="username = 'ood'")[0]['id'])


def _token(app, username, password, on_behalf_of=None):
    body = {'username': username, 'password': password}
    if on_behalf_of:
        body['on_behalf_of'] = on_behalf_of
    response = app.post('/token', data=json.dumps(body), content_type='application/json')
    return response.status_code, json.loads(response.data)


def _whoami(app, token):
    response = app.get('/whoami', headers={'x-access-tokens': token})
    return response.status_code, json.loads(response.data)


def _trail(tmp_path_of_db):
    return tmp_path_of_db.read_text().splitlines()


# ── the exchange ────────────────────────────────────────────────────────────

def test_a_delegate_obtains_the_persons_own_token(app, world):
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='alice')
    assert code == 201, body
    claims = decode(body['token'], 'test', algorithms=['HS256'])
    assert claims['id'] == world.alice and set(claims) == {'id', 'exp'}, 'nothing in the token remembers ood'
    code, answer = _whoami(app, body['token'])
    assert code == 200 and answer['user'] == 'alice' and answer['usergroups'] == {'intel': 'manager'}
    own = _token(app, 'alice', 'alice-pw')[1]['token']
    assert decode(own, 'test', algorithms=['HS256'])['id'] == claims['id'], 'the same identity as her own login'


def test_the_persons_token_acts_with_the_persons_rights(app, world):
    token = _token(app, 'ood', 'ood-pw', on_behalf_of='alice')[1]['token']
    response = app.post('/config/node/node001', headers={'x-access-tokens': token},
                        data=json.dumps({'config': {'node': {'node001': {'comment': 'via the portal'}}}}), content_type='application/json')
    assert response.status_code in (201, 204), response.data


def test_a_user_without_the_flag_is_refused_and_no_token_is_minted(app, world):
    code, body = _token(app, 'bob', 'bob-pw', on_behalf_of='alice')
    assert code == 403 and 'may not obtain a token on behalf of others' in body['message']
    assert 'token' not in body


def test_a_wrong_delegate_password_is_refused_before_anything_is_resolved(app, world, monkeypatch):
    from base.authentication import Authentication
    monkeypatch.setattr(Authentication, 'delegate', lambda *a, **k: pytest.fail('resolution must not run on a bad delegate password'))
    code, body = _token(app, 'ood', 'wrong', on_behalf_of='alice')
    assert code == 403 and 'Incorrect password' in body['message']


def test_a_person_no_source_knows_and_a_disabled_person_are_refused(app, world, db):
    from utils.helper import Helper
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='nobody')
    assert code == 403 and 'not known to any authentication source' in body['message']
    db.update('user', Helper().make_rows({'enabled': '0'}), [{'column': 'username', 'value': 'alice'}])
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='alice')
    assert code == 403 and 'disabled' in body['message']


def test_the_configuration_file_account_is_neither_delegate_nor_target(app, world):
    code, body = _token(app, 'luna', 'luna', on_behalf_of='alice')
    assert code == 403 and 'not a delegate' in body['message']
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='luna')
    assert code == 403 and 'cannot be delegated to' in body['message']


def test_a_delegate_cannot_be_delegated_to(app, world, db):
    from utils.helper import Helper
    db.insert('user', Helper().make_rows({'username': 'ood2', 'source': 'local', 'enabled': '1', 'admin': '0', 'delegate': '1'}))
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='ood2')
    assert code == 403 and 'is a delegate and cannot be delegated to' in body['message']


def test_an_os_person_with_no_row_is_created_on_delegation_with_mapped_memberships(app, world, db, monkeypatch):
    import pwd
    import grp
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: types.SimpleNamespace(pw_name=name, pw_uid=1500, pw_gid=1500, pw_shell='/bin/bash') if name == 'ossam' else (_ for _ in ()).throw(KeyError(name)))
    monkeypatch.setattr(os, 'getgrouplist', lambda name, gid: [1500, 2001])
    monkeypatch.setattr(grp, 'getgrgid', lambda gid: types.SimpleNamespace(gr_name={1500: 'ossam', 2001: 'hpc-intel'}[gid]))
    monkeypatch.setitem(sys.modules, 'pam', types.SimpleNamespace(pam=lambda: types.SimpleNamespace(authenticate=lambda *a, **k: False, reason='')))
    admin = {'x-access-tokens': encode({'id': 0}, 'test', 'HS256')}
    app.post('/config/usergroupmap', headers=admin, data=json.dumps({'config': {'usergroupmap': {
        'source': 'pam', 'external_group': 'hpc-intel', 'usergroup': 'intel', 'role': 'operator'}}}), content_type='application/json')
    code, body = _token(app, 'ood', 'ood-pw', on_behalf_of='ossam')
    assert code == 201, body
    code, answer = _whoami(app, body['token'])
    assert answer['user'] == 'ossam' and answer['source'] == 'pam' and answer['usergroups'] == {'intel': 'operator'}
    assert db.get_record(table='user', where="username = 'ossam'")[0]['external_id'] == '1500'


def test_a_system_account_cannot_be_delegated_to(app, world, monkeypatch):
    """Found live: the OS knows nobody, bin and every service account, none of which has a
    password; a delegation skips the password, so the fence is the account's own shape:
    a login shell and an ordinary uid."""
    import pwd
    accounts = {'nobody': types.SimpleNamespace(pw_name='nobody', pw_uid=65534, pw_gid=65534, pw_shell='/sbin/nologin'),
                'svc': types.SimpleNamespace(pw_name='svc', pw_uid=400, pw_gid=400, pw_shell='/bin/bash'),
                'oddshell': types.SimpleNamespace(pw_name='oddshell', pw_uid=1600, pw_gid=1600, pw_shell='/bin/false'),
                'root': types.SimpleNamespace(pw_name='root', pw_uid=0, pw_gid=0, pw_shell='/bin/bash')}
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: accounts[name] if name in accounts else (_ for _ in ()).throw(KeyError(name)))
    monkeypatch.setitem(sys.modules, 'pam', types.SimpleNamespace(pam=lambda: types.SimpleNamespace(authenticate=lambda *a, **k: False, reason='')))
    for name in accounts:
        code, body = _token(app, 'ood', 'ood-pw', on_behalf_of=name)
        assert code == 403 and 'not known to any authentication source' in body['message'], (name, body)
        assert 'token' not in body


# ── the delegate itself ─────────────────────────────────────────────────────

def test_a_delegates_own_token_is_refused_on_every_route(app, world):
    code, body = _token(app, 'ood', 'ood-pw')
    assert code == 201, 'a delegate can log in, which is how it presents its credential'
    token = body['token']
    for path in ('/whoami', '/config/node', '/config/node/node001', '/config/user'):
        response = app.get(path, headers={'x-access-tokens': token})
        assert response.status_code == 403, (path, response.status_code)
        assert 'is a delegate and may only obtain tokens for others' in json.loads(response.data)['message'], path
    response = app.post('/config/node/node001', headers={'x-access-tokens': token},
                        data=json.dumps({'config': {'node': {'node001': {'comment': 'x'}}}}), content_type='application/json')
    assert response.status_code == 403


# ── the trail ───────────────────────────────────────────────────────────────

def test_the_trail_names_both_on_success_and_on_refusal(app, world, tmp_path):
    _token(app, 'ood', 'ood-pw', on_behalf_of='alice')
    _token(app, 'bob', 'bob-pw', on_behalf_of='alice')
    lines = (tmp_path / 'audit.log').read_text().splitlines()
    delegated = [l for l in lines if 'outcome=delegated' in l]
    assert len(delegated) == 1 and 'user=alice' in delegated[0] and 'detail="by ood"' in delegated[0], delegated
    refused = [l for l in lines if 'outcome=refused' in l and 'on behalf of alice' in l]
    assert len(refused) == 1 and 'user=bob' in refused[0], refused
