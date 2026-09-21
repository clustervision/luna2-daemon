"""
The audit trail (TRIX-2090): one line per state-changing call and per refusal, in its own
file, never a body. Proven over the route map, not by sampling: every state-changing route
leaves a line when allowed and when refused.
"""
import json
import os
import types

import pytest
from flask import Blueprint, Flask
from jwt import encode

from cases.route_requirements_cases import app as _routes_app, fake_args as _fake_args, token_layer as _token_layer

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
TABLES = ['node', 'osimage', 'user', 'usergroup', 'usergroupmember', 'usergroupmap', 'nodesecrets']


@pytest.fixture
def trail(tmp_path, monkeypatch):
    """A fresh audit file per test, and a fresh handler pointed at it."""
    import common.constant as constant
    from utils.audit import Audit
    path = tmp_path / 'luna2-audit.log'
    monkeypatch.setitem(constant.CONSTANT, 'AUDIT', {'LOGFILE': str(path)})
    Audit._logger = None
    yield path
    for handler in list(Audit.logger().handlers):
        handler.close()
        Audit.logger().removeHandler(handler)
    Audit._logger = None


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'audit.db')
    database.local_thread.connection = None
    for table in TABLES:
        Database().create(table, DBStructure().get_database_table_structure(table))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    monkeypatch.setitem(constant.CONSTANT['API'], 'EXPIRY', '3600')
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def world(db):
    from utils.helper import Helper
    dave = db.insert('user', Helper().make_rows({'username': 'dave', 'source': 'local', 'enabled': '1', 'admin': '0', 'delegate': '0'}))
    intel = db.insert('usergroup', Helper().make_rows({'name': 'intel'}))
    db.insert('usergroupmember', Helper().make_rows({'userid': dave, 'usergroupid': intel, 'role': 'reader', 'source': 'local'}))
    db.insert('node', Helper().make_rows({'name': 'node001', 'usergroups': str(intel), 'access': '750'}))
    return types.SimpleNamespace(dave=dave, intel=intel)


def _lines(path):
    return [line for line in path.read_text().splitlines() if 'AUDIT ' in line] if path.exists() else []


def _token(userid):
    from common.constant import CONSTANT
    return encode({'id': userid}, CONSTANT['API']['SECRET_KEY'], 'HS256')


# ── every state-changing route, over the route map ──────────────────────────

def _state_changing_routes():
    from common.route_grammar import requirement
    from utils.audit import Audit
    found = []
    app = _routes_app()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        layer = _token_layer(app.view_functions[rule.endpoint])
        if layer is None:
            continue
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            if not Audit.state_changing(method, rule.rule):
                continue
            answer = requirement(rule.rule, method, _fake_args(rule), getattr(layer, 'requires', None))
            found.append((method, rule.rule, answer['kind']))
    return found


def test_the_route_map_has_state_changing_routes_to_prove():
    routes = _state_changing_routes()
    assert len(routes) >= 80, len(routes)
    assert ('POST', '/config/node/<string:name>', 'object') in routes
    assert ('GET', '/config/node/<string:name>/_delete', 'object') in routes


@pytest.mark.parametrize('method, rule, kind', _state_changing_routes())
def test_every_state_changing_route_leaves_a_line_when_allowed_and_when_refused(method, rule, kind, trail, db, world):
    """The real decorator on a stub view of the route's own shape: id 0 is allowed and
    recorded; a reader is refused (or, on a listing-shaped route, allowed) and recorded."""
    from common.validate_auth import token_required

    stub = Blueprint('stub', __name__)

    def view(**kwargs):
        return json.dumps({'reached': True}), 200
    stub.add_url_rule(rule, endpoint='view', view_func=token_required(view), methods=[method])
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(stub)
    path = rule
    for argument in ('name', 'hostname', 'node', 'object', 'entity', 'secret', 'interface', 'tagname',
                     'subsystem', 'action', 'tableref', 'target', 'device_type', 'subset', 'profile',
                     'role', 'script', 'object_type', 'file', 'request_id', 'username', 'account', 'component'):
        path = path.replace(f'<string:{argument}>', 'node001' if argument in ('name', 'hostname', 'node', 'object') else 'x')
    body = json.dumps({'config': {'node': {'node001': {'comment': 'x'}}}, 'control': {'power': {'off': {'hostlist': 'node001'}}}})
    call = (lambda token: app.test_client().post(path, headers={'x-access-tokens': token}, data=body, content_type='application/json')
            if method == 'POST' else app.test_client().get(path, headers={'x-access-tokens': token}))

    before = len(_lines(trail))
    call(_token(0))
    after_admin = _lines(trail)
    assert len(after_admin) == before + 1, f'{method} {rule}: id 0 left {len(after_admin) - before} lines'
    assert 'outcome=allowed' in after_admin[-1] and 'user=luna' in after_admin[-1] and 'source=ini' in after_admin[-1]

    response = call(_token(world.dave))
    after_reader = _lines(trail)
    assert len(after_reader) == before + 2, f'{method} {rule}: the reader left {len(after_reader) - before - 1} lines'
    expected = 'outcome=refused' if response.status_code in (401, 403, 404) else 'outcome=allowed'
    assert expected in after_reader[-1] and 'user=dave' in after_reader[-1], after_reader[-1]


# ── what a line carries ─────────────────────────────────────────────────────

def test_a_refusal_names_the_missing_bit_and_the_class(trail, db, world):
    from common.validate_auth import token_required
    stub = Blueprint('stub', __name__)

    @stub.route('/config/node/<string:name>', methods=['POST'])
    @token_required
    def node(name=None):
        return json.dumps({}), 200
    app = Flask(__name__)
    app.register_blueprint(stub)
    response = app.test_client().post('/config/node/node001', headers={'x-access-tokens': _token(world.dave)},
                                      data=json.dumps({'config': {'node': {'node001': {'comment': 'x'}}}}), content_type='application/json')
    assert response.status_code == 403
    line = _lines(trail)[-1]
    assert line.startswith('AUDIT ') is False and 'AUDIT user=dave id=' in line
    assert 'action="POST /config/node/node001"' in line and 'object="node node001"' in line
    assert 'outcome=refused code=403' in line
    assert 'detail="node node001 requires w; you hold r-- (reader in intel)"' in line


def test_a_plain_read_leaves_no_line_and_a_power_status_is_a_read(trail, db, world):
    from common.validate_auth import token_required
    stub = Blueprint('stub', __name__)

    @stub.route('/config/node', methods=['GET'])
    @token_required
    def nodes():
        return json.dumps({}), 200

    @stub.route('/control/action/<string:subsystem>/<string:hostname>/_<string:action>', methods=['GET'])
    @token_required
    def control(subsystem=None, hostname=None, action=None):
        return json.dumps({}), 200
    app = Flask(__name__)
    app.register_blueprint(stub)
    admin = {'x-access-tokens': _token(0)}
    assert app.test_client().get('/config/node', headers=admin).status_code == 200
    assert app.test_client().get('/control/action/power/node001/_status', headers=admin).status_code == 200
    assert _lines(trail) == []
    assert app.test_client().get('/control/action/power/node001/_off', headers=admin).status_code == 200
    assert len(_lines(trail)) == 1 and 'action="GET /control/action/power/node001/_off"' in _lines(trail)[0]


def test_a_call_without_a_token_or_with_a_bad_one_is_recorded_without_a_user(trail, db):
    from common.validate_auth import token_required
    stub = Blueprint('stub', __name__)

    @stub.route('/config/node/<string:name>', methods=['POST'])
    @token_required
    def node(name=None):
        return json.dumps({}), 200
    app = Flask(__name__)
    app.register_blueprint(stub)
    app.test_client().post('/config/node/node001', data='{}', content_type='application/json')
    app.test_client().post('/config/node/node001', headers={'x-access-tokens': 'garbage'}, data='{}', content_type='application/json')
    lines = _lines(trail)
    assert len(lines) == 2
    assert all('user=- id=-' in line and 'outcome=refused code=401' in line for line in lines)
    assert 'detail="A valid token is missing"' in lines[0] and 'detail="Token is invalid"' in lines[1]


def test_a_failed_write_is_on_record_as_failed_and_a_views_own_403_as_refused(trail, db):
    """Found live: the generic chmod route and the create rules say no inside the view, after
    the gate let the call through; that is a refusal in the trail, with the view's message."""
    from common.validate_auth import token_required
    stub = Blueprint('stub', __name__)

    @stub.route('/config/node/<string:name>', methods=['POST'])
    @token_required
    def node(name=None):
        return json.dumps({'message': 'Invalid request'}), 400

    @stub.route('/config/node/<string:name>/_chmod', methods=['POST'])
    @token_required
    def chmod(name=None):
        return {'message': 'node node001: chmod is for owners, usergroup admins, rootus and admin users'}, 403
    app = Flask(__name__)
    app.register_blueprint(stub)
    admin = {'x-access-tokens': _token(0)}
    app.test_client().post('/config/node/node001', headers=admin, data='{}', content_type='application/json')
    assert 'outcome=failed code=400' in _lines(trail)[-1]
    app.test_client().post('/config/node/node001/_chmod', headers=admin, data='{}', content_type='application/json')
    assert 'outcome=refused code=403' in _lines(trail)[-1]
    assert 'detail="node node001: chmod is for owners' in _lines(trail)[-1]


def test_logins_and_login_refusals_are_recorded(trail, db, world, monkeypatch):
    from routes.auth import auth_blueprint
    from routes.config_user import user_blueprint
    app = Flask(__name__)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(user_blueprint)
    app.test_client().post('/config/user/dave', headers={'x-access-tokens': _token(0)},
                           data=json.dumps({'config': {'user': {'dave': {'password': 'hunter2'}}}}), content_type='application/json')
    assert app.test_client().post('/token', data=json.dumps({'username': 'dave', 'password': 'hunter2'}), content_type='application/json').status_code == 201
    assert app.test_client().post('/token', data=json.dumps({'username': 'dave', 'password': 'wrong'}), content_type='application/json').status_code == 401
    lines = _lines(trail)
    assert any('outcome=login code=201' in line and 'user=dave' in line for line in lines)
    assert any('outcome=refused code=401' in line and 'Incorrect password' in line for line in lines)


def test_no_password_and_no_secret_content_reaches_the_trail(trail, db, world):
    """A scenario that sets a password and writes a secret; then the whole file is searched."""
    from routes.auth import auth_blueprint
    from routes.config_user import user_blueprint
    from routes.config_secrets import secrets_blueprint
    app = Flask(__name__)
    for blueprint in (auth_blueprint, user_blueprint, secrets_blueprint):
        app.register_blueprint(blueprint)
    admin = {'x-access-tokens': _token(0)}
    app.test_client().post('/config/user/dave', headers=admin,
                           data=json.dumps({'config': {'user': {'dave': {'password': 'S3cretPassw0rd'}}}}), content_type='application/json')
    app.test_client().post('/token', data=json.dumps({'username': 'dave', 'password': 'S3cretPassw0rd'}), content_type='application/json')
    app.test_client().post('/token', data=json.dumps({'username': 'dave', 'password': 'WrongButStillSecret'}), content_type='application/json')
    app.test_client().post('/config/secrets/node/node001', headers=admin,
                           data=json.dumps({'config': {'secrets': {'node': {'node001': [{'name': 'k', 'content': 'TOPSECRETCONTENT', 'path': '/k'}]}}}}),
                           content_type='application/json')
    text = trail.read_text()
    assert 'AUDIT' in text
    for forbidden in ('S3cretPassw0rd', 'WrongButStillSecret', 'TOPSECRETCONTENT'):
        assert forbidden not in text, f'{forbidden} reached the audit trail'


def test_the_trail_does_not_reach_the_daemon_log_at_info(trail, db, world, caplog):
    """Found live: a child logger propagates to the parent's handlers whatever its level, so
    every audit line landed in the daemon log at info as well. The daemon log gets the
    debug copy only."""
    import logging
    from common.validate_auth import token_required
    stub = Blueprint('stub', __name__)

    @stub.route('/config/node/<string:name>', methods=['POST'])
    @token_required
    def node(name=None):
        return json.dumps({}), 200
    app = Flask(__name__)
    app.register_blueprint(stub)
    with caplog.at_level(logging.INFO, logger='luna2-daemon'):
        app.test_client().post('/config/node/node001', headers={'x-access-tokens': _token(0)}, data='{}', content_type='application/json')
    assert len(_lines(trail)) == 1
    assert not [r for r in caplog.records if 'AUDIT ' in r.getMessage() and r.levelno >= logging.INFO], \
        'audit lines must not propagate into the daemon log at info'


def test_the_writer_takes_no_body():
    """The structural guarantee behind the previous test: record() has no way to be handed a body."""
    import inspect
    from utils.audit import Audit
    parameters = set(inspect.signature(Audit.record).parameters)
    assert not parameters & {'body', 'payload', 'data', 'request_data'}, parameters


def test_the_default_path_is_beside_the_daemon_log(monkeypatch):
    import common.constant as constant
    from utils.audit import Audit
    monkeypatch.setitem(constant.CONSTANT, 'LOGGER', {'LEVEL': 'info', 'LOGFILE': '/var/log/luna/luna2-daemon.log'})
    monkeypatch.setitem(constant.CONSTANT, 'AUDIT', {})
    assert Audit.default_path() == '/var/log/luna/luna2-audit.log'
