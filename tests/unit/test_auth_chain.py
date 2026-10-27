"""
The authentication chain (TRIX-2083): local, pam and ldap sources, the identity core that
turns a source's answer into a Luna user, and the memberships written from the map.

pam and ldap3 are not on the test box, so fake modules stand in for them; that proves the
chain and the core, not the libraries.
"""
import json
import os
import sys
import types

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
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'chain.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def api(db):
    """Admin-token calls to the user, usergroup and map routes, to seed the tables."""
    from common.constant import CONSTANT
    from routes.config_user import user_blueprint
    from routes.config_usergroup import usergroup_blueprint

    app = Flask(__name__)
    app.register_blueprint(user_blueprint)
    app.register_blueprint(usergroup_blueprint)
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')

    def post(path, body):
        response = app.test_client().post(path, headers={'x-access-tokens': token},
                                          data=json.dumps(body), content_type='application/json')
        assert response.status_code in (201, 204), (path, response.data)

    def get(path):
        response = app.test_client().get(path, headers={'x-access-tokens': token})
        return json.loads(response.data)

    return types.SimpleNamespace(
        user=lambda name, **f: post(f'/config/user/{name}', {'config': {'user': {name: f}}}),
        usergroup=lambda name, **f: post(f'/config/usergroup/{name}', {'config': {'usergroup': {name: f}}}),
        member=lambda group, **f: post(f'/config/usergroup/{group}/members', {'config': {'usergroup': {group: f}}}),
        map=lambda **f: post('/config/usergroupmap', {'config': {'usergroupmap': f}}),
        show=lambda name: get(f'/config/user/{name}')['config']['user'][name],
    )


def _chain(monkeypatch, chain):
    from common.constant import CONSTANT
    monkeypatch.setitem(CONSTANT, 'AUTH', {'CHAIN': chain})


def _login(username, password):
    from common.constant import CONSTANT
    from base.authentication import Authentication
    status, response = Authentication().get_token({'username': username, 'password': password})
    if status:
        return decode(response['token'], CONSTANT['API']['SECRET_KEY'], algorithms=['HS256'])['id']
    return response['message']


# ── fakes for the operating system and the libraries ────────────────────────

OS_USERS = {'ossam': (1500, 1500, ['hpc-intel', 'users']), 'alice': (1501, 1501, ['users'])}


def _fake_os(monkeypatch, accept='ospass', groups=None):
    """An OS with two accounts and a PAM that accepts one password for all of them."""
    import pwd
    import grp

    def getpwnam(name):
        if name not in OS_USERS:
            raise KeyError(name)
        uid, gid, _ = OS_USERS[name]
        return types.SimpleNamespace(pw_name=name, pw_uid=uid, pw_gid=gid)

    def getgrouplist(name, gid):
        return [gid] + [hash(g) % 10000 + 2000 for g in (groups if groups is not None else OS_USERS[name][2])]

    def getgrgid(gid):
        for name, (uid, g, gs) in OS_USERS.items():
            if gid == g:
                return types.SimpleNamespace(gr_name=name)
        for g in (groups if groups is not None else sum((u[2] for u in OS_USERS.values()), [])):
            if gid == hash(g) % 10000 + 2000:
                return types.SimpleNamespace(gr_name=g)
        raise KeyError(gid)

    monkeypatch.setattr(pwd, 'getpwnam', getpwnam)
    monkeypatch.setattr(os, 'getgrouplist', getgrouplist)
    monkeypatch.setattr(grp, 'getgrgid', getgrgid)

    class Conversation:
        reason = 'Authentication failure'

        def authenticate(self, name, password, service='login'):
            return password == accept

    monkeypatch.setitem(sys.modules, 'pam', types.SimpleNamespace(pam=Conversation))


def _no_pam_library(monkeypatch):
    monkeypatch.setitem(sys.modules, 'pam', None)


def _fake_ldap3(monkeypatch, people=None, reachable=True):
    """A directory with one entry per person: {name: (dn, uuid, [groups])}, or one that is down."""
    people = people or {}

    class LDAPBindError(Exception):
        pass

    class LDAPKeyError(KeyError):
        pass

    class Attribute:
        def __init__(self, values):
            self.values = values

    class Entry:
        def __init__(self, dn, uuid, groups):
            self.entry_dn = dn
            self._attrs = {'entryUUID': Attribute([uuid]), 'memberOf': Attribute(groups)}

        def __getitem__(self, attribute):
            if attribute not in self._attrs:
                raise LDAPKeyError(attribute)
            return self._attrs[attribute]

    class Connection:
        def __init__(self, server, user=None, password=None, auto_bind=True, receive_timeout=None):
            if not reachable:
                raise ConnectionError('directory unreachable')
            if user and not user.startswith('cn=search'):
                dn_passwords = {dn: 'dirpass' for dn, _, _ in people.values()}
                if dn_passwords.get(user) != password:
                    raise LDAPBindError('invalid credentials')
            self.entries = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def search(self, base, search_filter, attributes=None):
            name = search_filter.split('=', 1)[1].rstrip(')')
            self.entries = [Entry(*people[name])] if name in people else []
            return bool(self.entries)

    fake = types.SimpleNamespace(
        NONE='NONE', Server=lambda uri, get_info=None: uri, Connection=Connection,
        utils=types.SimpleNamespace(conv=types.SimpleNamespace(escape_filter_chars=lambda s: s)),
        core=types.SimpleNamespace(exceptions=types.SimpleNamespace(LDAPBindError=LDAPBindError, LDAPKeyError=LDAPKeyError)))
    monkeypatch.setitem(sys.modules, 'ldap3', fake)
    from common.constant import CONSTANT
    monkeypatch.setitem(CONSTANT, 'AUTH_LDAP', {'URI': 'ldaps://dir.example', 'BASE': 'dc=example,dc=com',
                                                'BIND_DN': 'cn=search,dc=example,dc=com', 'BIND_PASSWORD': 'x'})


# ── the chain ───────────────────────────────────────────────────────────────

def test_the_default_chain_is_local_then_pam(db):
    from base.authentication import Authentication
    assert Authentication().chain() == ['local', 'pam']


def test_a_local_digest_wins_and_a_wrong_local_password_never_falls_through(api, db, monkeypatch):
    """alice exists in the OS too, and the fake PAM accepts her password; local still decides."""
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch, accept='lunapass')
    api.user('alice', password='lunapass')
    userid = db.get_record(table='user', where="username = 'alice'")[0]['id']
    assert _login('alice', 'lunapass') == userid
    assert 'Incorrect password' in _login('alice', 'wrong')
    assert db.get_record(table='user', where="username = 'alice'")[0]['source'] == 'local'


def test_an_os_user_is_created_on_first_login_with_memberships_from_the_map(api, db, monkeypatch):
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    api.usergroup('intel')
    api.map(source='pam', external_group='hpc-intel', usergroup='intel', role='manager')
    userid = _login('ossam', 'ospass')
    assert isinstance(userid, int)
    shown = api.show('ossam')
    assert shown['source'] == 'pam' and shown['external_id'] == '1500'
    assert shown['password_set'] is False and shown['enabled'] is True
    assert shown['usergroups'] == {'intel': 'manager'}, 'users is not mapped and grants nothing'
    assert shown['lastlogin']


def test_a_second_login_refreshes_the_source_memberships_and_keeps_local_ones(api, db, monkeypatch):
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    api.usergroup('intel')
    api.usergroup('ops')
    api.map(source='pam', external_group='hpc-intel', usergroup='intel', role='manager')
    first = _login('ossam', 'ospass')
    api.member('ops', username='ossam', role='operator')
    assert api.show('ossam')['usergroups'] == {'intel': 'manager', 'ops': 'operator'}
    _fake_os(monkeypatch, groups=['users'])
    assert _login('ossam', 'ospass') == first, 'the same row, found by uid'
    assert api.show('ossam')['usergroups'] == {'ops': 'operator'}
    assert len(db.get_record(table='user')) == 1


def test_a_wrong_os_password_is_refused_by_pam(api, db, monkeypatch):
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    assert 'PAM refused' in _login('ossam', 'wrong')
    assert not db.get_record(table='user'), 'nothing is created for a refused login'


def test_a_name_no_source_knows_is_refused(db, monkeypatch):
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    assert 'not known to any authentication source' in _login('nobody', 'x')


def test_a_local_row_without_a_password_is_claimed_by_pam_only_when_its_source_says_so(api, db, monkeypatch):
    """rootus may create a row ahead for an OS account; a local row with the same name is a clash."""
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    api.user('ossam', source='pam')
    userid = db.get_record(table='user', where="username = 'ossam'")[0]['id']
    assert _login('ossam', 'ospass') == userid
    assert api.show('ossam')['external_id'] == '1500', 'the stable id is filled in on first login'
    api.user('alice')
    message = _login('alice', 'ospass')
    assert 'exists with source local' in message
    assert len(db.get_record(table='user', where="username = 'alice'")) == 1


def test_a_disabled_os_user_is_refused_without_touching_the_os(api, db, monkeypatch):
    _chain(monkeypatch, 'local, pam')
    _fake_os(monkeypatch)
    _login('ossam', 'ospass')
    api.user('ossam', enabled=False)
    assert 'disabled' in _login('ossam', 'ospass')


def test_a_missing_pam_library_is_logged_and_local_still_works(api, db, monkeypatch, caplog):
    import logging
    _chain(monkeypatch, 'pam, local')
    _no_pam_library(monkeypatch)
    api.user('alice', password='lunapass')
    with caplog.at_level(logging.ERROR, logger='luna2-daemon'):
        assert isinstance(_login('alice', 'lunapass'), int)
    assert 'authentication source pam is unavailable' in caplog.text


def test_an_unreachable_directory_is_logged_and_local_still_works(api, db, monkeypatch, caplog):
    import logging
    _chain(monkeypatch, 'ldap, local')
    _fake_ldap3(monkeypatch, reachable=False)
    api.user('alice', password='lunapass')
    with caplog.at_level(logging.ERROR, logger='luna2-daemon'):
        assert isinstance(_login('alice', 'lunapass'), int)
    assert 'authentication source ldap is unavailable' in caplog.text


def test_a_directory_user_is_created_keyed_on_its_uuid_with_mapped_groups(api, db, monkeypatch):
    _chain(monkeypatch, 'local, ldap')
    _fake_ldap3(monkeypatch, people={'dkumar': ('uid=dkumar,ou=people,dc=example,dc=com', '8f3a-uuid',
                                                ['cn=hpc-intel,ou=groups,dc=example,dc=com', 'cn=other,dc=x'])})
    api.usergroup('intel')
    api.map(source='ldap', external_group='cn=hpc-intel,ou=groups,dc=example,dc=com', usergroup='intel', role='reader')
    assert 'refused the password' in _login('dkumar', 'wrong')
    userid = _login('dkumar', 'dirpass')
    assert isinstance(userid, int)
    shown = api.show('dkumar')
    assert shown['source'] == 'ldap' and shown['external_id'] == '8f3a-uuid'
    assert shown['usergroups'] == {'intel': 'reader'}


def test_the_configuration_file_account_is_not_a_chain_step(db, monkeypatch):
    _chain(monkeypatch, 'pam')
    _no_pam_library(monkeypatch)
    assert _login('luna', 'luna') == 0
