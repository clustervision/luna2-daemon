"""
Filtering every list and show (TRIX-2087). Two halves: a derived test that every listing
route reaches a base method that asks the access helper what the caller may see, so a
new listing cannot forget it; and the filtering itself, through real base methods on a
seeded database, as a reader, an owner and an admin.
"""
import ast
import json
import os
import types

import pytest
from flask import Blueprint, Flask, g
from jwt import encode

from cases.route_requirements_cases import app as _routes_app, fake_args as _fake_args, token_layer as _token_layer

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
HELPER_CALLS = ('Access().visible(', 'Access().visible_names(', 'Access().admin_caller(')


# ── the derived half: every listing reaches the helper ──────────────────────

def _module_tree(path):
    with open(path, encoding='utf-8') as source:
        return ast.parse(source.read(), filename=path)


def _class_method_source(class_name, method):
    """The source of Class.method from daemon/base or daemon/utils, or None."""
    for folder in ('base', 'utils'):
        for name in os.listdir(os.path.join(DAEMON, folder)):
            if not name.endswith('.py'):
                continue
            path = os.path.join(DAEMON, folder, name)
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
            if f'class {class_name}(' not in text and f'class {class_name}:' not in text:
                continue
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == method:
                            return ast.get_source_segment(text, item)
    return None


def _calls_in(source):
    """Every Class().method pair called in a piece of source."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name)):
            found.add((node.func.value.func.id, node.func.attr))
    return found


def _reaches_helper(source, depth=3, seen=None):
    """Whether the source, or a Class().method it calls, calls the access helper."""
    seen = seen or set()
    if any(call in source for call in HELPER_CALLS):
        return True
    if depth == 0:
        return False
    for class_name, method in _calls_in(source):
        if (class_name, method) in seen or class_name in ('Database', 'Helper', 'Log', 'Journal'):
            continue
        seen.add((class_name, method))
        inner = _class_method_source(class_name, method)
        if inner and _reaches_helper(inner, depth - 1, seen):
            return True
    return False


def _route_function_sources():
    """{(rule, method): source} for every route function, local helpers of the module inlined."""
    import routes
    result = {}
    for name in os.listdir(os.path.join(DAEMON, 'routes')):
        if not name.endswith('.py'):
            continue
        path = os.path.join(DAEMON, 'routes', name)
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        tree = ast.parse(text)
        helpers = {node.name: ast.get_source_segment(text, node) for node in tree.body
                   if isinstance(node, ast.FunctionDef) and not node.decorator_list}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            source = ast.get_source_segment(text, node)
            for helper_name, helper_source in helpers.items():
                if f'{helper_name}(' in source:
                    source += '\n' + helper_source
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == 'route' and decorator.args):
                    rule = decorator.args[0].value
                    methods = ['GET']
                    for keyword in decorator.keywords:
                        if keyword.arg == 'methods':
                            methods = [m.value for m in keyword.value.elts]
                    for method in methods:
                        result[(rule, method)] = source
    return result


def _listing_routes():
    """GET routes whose requirement is an object listing or a plain show, from the route map."""
    from common.route_grammar import requirement
    listings = []
    app = _routes_app()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static' or 'GET' not in rule.methods:
            continue
        layer = _token_layer(app.view_functions[rule.endpoint])
        if layer is None:
            continue
        answer = requirement(rule.rule, 'GET', _fake_args(rule), getattr(layer, 'requires', None))
        parts = rule.rule.strip('/').split('/')
        if answer['kind'] != 'object':
            continue
        # a child's show (dns under network, a tag under its image) is gated by its parent
        plain_show = len(parts) == 3 and parts[2].startswith('<') and parts[1] not in ('dns', 'osimagetag')
        if answer.get('name') is None or plain_show or rule.rule.endswith('/_member'):
            listings.append(rule.rule)
    return sorted(listings)


def test_every_listing_and_show_route_reaches_the_access_helper():
    sources = _route_function_sources()
    missing = []
    for rule in _listing_routes():
        source = sources.get((rule, 'GET'))
        if source is None or not _reaches_helper(source):
            missing.append(rule)
    assert not missing, (
        'listing or show routes whose base method never asks Access() what the caller may see:\n  '
        + '\n  '.join(missing) + '\n(call Access().visible or visible_names over the rows before building the answer)')


def test_the_derived_test_sees_enough_routes_to_mean_something():
    listings = _listing_routes()
    assert len(listings) >= 40, listings
    assert '/config/node' in listings and '/config/secrets' in listings and '/config/rack/inventory' in listings


# ── the filtering half: real base methods, seeded database ──────────────────

@pytest.fixture
def seeded(sqlite_db, monkeypatch):
    """Two images, two nodes, one route; alice owns one image, intel is listed on one node;
    bob is a reader in intel, zed is admin."""
    import common.constant as constant
    from utils.database import Database
    from utils.helper import Helper

    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY', os.path.join(DAEMON, 'plugins'))
    db = Database()

    def user(name, admin=False):
        return db.insert('user', Helper().make_rows({'username': name, 'source': 'local', 'enabled': '1',
                                                     'admin': '1' if admin else '0', 'delegate': '0'}))
    alice, bob, zed = user('alice'), user('bob'), user('zed', admin=True)
    intel = db.insert('usergroup', Helper().make_rows({'name': 'intel'}))
    db.insert('usergroupmember', Helper().make_rows({'userid': bob, 'usergroupid': intel, 'role': 'reader', 'source': 'local'}))
    db.insert('cluster', Helper().make_rows({'name': 'cluster'}))
    group = db.insert('group', Helper().make_rows({'name': 'compute', 'usergroups': str(intel), 'access': '750'}))
    db.insert('osimage', Helper().make_rows({'name': 'mine', 'owners': str(alice), 'access': '700'}))
    db.insert('osimage', Helper().make_rows({'name': 'shared', 'access': '774'}))
    node1 = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': group, 'usergroups': str(intel), 'access': '750'}))
    node2 = db.insert('node', Helper().make_rows({'name': 'node002', 'groupid': group}))
    db.insert('nodesecrets', Helper().make_rows({'nodeid': node1, 'name': 's1', 'content': 'x', 'path': '/s1'}))
    db.insert('nodesecrets', Helper().make_rows({'nodeid': node2, 'name': 's2', 'content': 'y', 'path': '/s2'}))
    db.insert('clustersecrets', Helper().make_rows({'clusterid': 1, 'name': 'cs', 'content': 'z', 'path': '/cs'}))
    db.insert('bmcsetup', Helper().make_rows({'name': 'ipmi', 'usergroups': str(intel), 'access': '770'}))
    db.insert('bmcsetup', Helper().make_rows({'name': 'hidden'}))
    return types.SimpleNamespace(alice=alice, bob=bob, zed=zed, intel=intel)


def _as(userid):
    """A request context carrying the caller, which is what the helper reads."""
    app = Flask(__name__)
    context = app.test_request_context('/')
    context.push()
    g.userid = userid
    return context


def _names(status_response, entity):
    status, response = status_response
    assert status is True, response
    return sorted(response['config'][entity])


def test_a_reader_sees_only_what_the_bits_allow_from_every_listing(seeded):
    from base.osimage import OSImage
    from base.bmcsetup import BMCSetup
    from base.secret import Secret
    from base.group import Group
    from utils.model import Model
    context = _as(seeded.bob)
    try:
        assert _names(OSImage().get_all_osimages(), 'osimage') == ['shared'], 'mine is 700 and not his'
        assert _names(BMCSetup().get_all_bmcsetup(), 'bmcsetup') == ['ipmi'], 'through Model.get_record'
        status, response = Secret().get_all_secrets()
        assert status is True
        assert sorted(response['config']['secrets']['node']) == ['node001'], 'node002 is not listed for intel'
        assert 'cluster' not in response['config']['secrets'], 'cluster secrets are for rootus and admin'
        status, response = Group().get_group_member('compute')
        assert status is True and response['config']['group']['compute']['members'] == ['node001']
        status, response = Model().get_member(name='ipmi', table='bmcsetup', table_cap='BMC setup')
        assert status is False, 'no node points at ipmi yet, and the helper ran over an empty list'
    finally:
        context.pop()


def test_every_entry_carries_owners_usergroups_and_access_as_names(seeded):
    from base.osimage import OSImage
    context = _as(seeded.bob)
    try:
        status, response = OSImage().get_all_osimages()
        shared = response['config']['osimage']['shared']
        assert shared['owners'] == 'rootus' and shared['usergroups'] == '' and shared['access'] == 'rwxrwxr--'
    finally:
        context.pop()
    context = _as(seeded.alice)
    try:
        status, response = OSImage().get_osimage('mine')
        mine = response['config']['osimage']['mine']
        assert mine['owners'] == 'alice' and mine['access'] == 'rwx------'
    finally:
        context.pop()


def test_admin_and_rootus_see_everything_annotated(seeded):
    from base.osimage import OSImage
    from base.secret import Secret
    for userid in (seeded.zed, 0):
        context = _as(userid)
        try:
            assert _names(OSImage().get_all_osimages(), 'osimage') == ['mine', 'shared']
            status, response = Secret().get_all_secrets()
            assert sorted(response['config']['secrets']['node']) == ['node001', 'node002']
            assert len(response['config']['secrets']['cluster']) == 1
        finally:
            context.pop()


def test_outside_a_request_nothing_is_hidden(seeded):
    """A journal replay, housekeeping or a test calling the base class: nobody to hide from."""
    from base.osimage import OSImage
    assert _names(OSImage().get_all_osimages(), 'osimage') == ['mine', 'shared']


def test_a_hostlist_crossing_the_boundary_is_refused_whole_naming_the_nodes(seeded):
    from common.constant import CONSTANT
    from common.validate_auth import token_required

    stub = Blueprint('stub', __name__)

    @stub.route('/control/action/<string:subsystem>/_<string:action>', methods=['POST'])
    @token_required
    def bulk(subsystem=None, action=None):
        return json.dumps({'reached': action}), 200

    app = Flask(__name__)
    app.register_blueprint(stub)
    token = encode({'id': seeded.bob}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    body = {'control': {'power': {'off': {'hostlist': 'node00[1-2]'}}}}
    response = app.test_client().post('/control/action/power/_off', headers={'x-access-tokens': token},
                                      data=json.dumps(body), content_type='application/json')
    assert response.status_code == 403
    message = json.loads(response.data)['message']
    assert message.startswith('refused for 2 of 2 nodes'), message
    assert 'node001 (node node001 requires x; you hold r-- (reader in intel))' in message
    assert 'node002 (node node002 is not available)' in message
    status_body = {'control': {'power': {'status': {'hostlist': 'node001'}}}}
    response = app.test_client().post('/control/action/power/_status', headers={'x-access-tokens': token},
                                      data=json.dumps(status_body), content_type='application/json')
    assert response.status_code == 200, 'a reader may ask the status of the node it may read'
