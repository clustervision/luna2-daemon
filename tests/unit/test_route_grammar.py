"""
Every registered route declares what it requires (TRIX-2084), proven from Flask's own
route map rather than by review: a text scan of the route files misses decorators with
nested parentheses, and the whole failure mode is the next route being forgotten.
"""
import ast
import importlib
import os
import pkgutil

import pytest
from flask import Blueprint, Flask

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
SKIP_METHODS = {'HEAD', 'OPTIONS'}


def _blueprints():
    """Every Blueprint defined by a module under routes/, keyed by the name luna.py imports."""
    import routes
    found = {}
    for module_info in pkgutil.iter_modules(routes.__path__):
        module = importlib.import_module(f'routes.{module_info.name}')
        for attribute, value in vars(module).items():
            if isinstance(value, Blueprint):
                found[attribute] = value
    return found


def _registered_by_the_daemon():
    """The blueprint names luna.py hands to register_blueprint, read from the file itself."""
    with open(os.path.join(DAEMON, 'luna.py'), encoding='utf-8') as source:
        tree = ast.parse(source.read())
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'register_blueprint' and node.args
                and isinstance(node.args[0], ast.Name)):
            names.add(node.args[0].id)
    return names


def _app():
    app = Flask(__name__)
    for blueprint in _blueprints().values():
        app.register_blueprint(blueprint)
    return app


def _token_wrapper_codes():
    """The code objects of the two decorators' inner functions: what a wrapped view runs first."""
    from common.validate_auth import provision_token_required, token_required
    return {token_required(lambda **kwargs: None).__code__,
            provision_token_required(lambda **kwargs: None).__code__}


def _has_token_decorator(view):
    """
    Walk the wrapper chain functools.wraps leaves behind. wraps copies the view's own
    name onto every wrapper, so a name tells nothing; the code object does.
    """
    codes = _token_wrapper_codes()
    while view is not None:
        if getattr(view, '__code__', None) in codes:
            return True
        view = getattr(view, '__wrapped__', None)
    return False


def _fake_args(rule):
    """One value per path argument, so the grammar sees the shape a real request has."""
    return {argument: f'<{argument}>' for argument in rule.arguments}


def test_the_daemon_registers_every_blueprint_the_route_modules_define():
    defined = set(_blueprints())
    registered = _registered_by_the_daemon()
    assert defined == registered, (
        f"defined but not registered: {sorted(defined - registered)}; "
        f"registered but not defined: {sorted(registered - defined)}")


def test_every_route_is_deliberately_open_or_classified():
    from common.route_grammar import OPEN, KINDS, requirement

    app = _app()
    seen_open = set()
    unlisted_open = []
    unclassified = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        view = app.view_functions[rule.endpoint]
        for method in sorted(rule.methods - SKIP_METHODS):
            if not _has_token_decorator(view):
                if (rule.rule, method) not in OPEN:
                    unlisted_open.append(f'{method} {rule.rule}')
                seen_open.add((rule.rule, method))
                continue
            assert (rule.rule, method) not in OPEN, f"{method} {rule.rule} is on the open list but has a token decorator"
            try:
                answer = requirement(rule.rule, method, _fake_args(rule))
            except Exception as exp:
                unclassified.append(f'{method} {rule.rule}: {exp}')
                continue
            assert answer['kind'] in KINDS, (rule.rule, method, answer)
    assert not unlisted_open, ('routes without a token that are not on the deliberately-open list:\n  '
                               + '\n  '.join(unlisted_open))
    assert not unclassified, 'routes the grammar cannot place:\n  ' + '\n  '.join(unclassified)
    assert seen_open == OPEN, (
        f"open-list drift; listed but no such open route: {sorted(OPEN - seen_open)}")


def test_the_open_list_is_the_boot_path_and_monitoring_only():
    """The routes the design leaves outside access control (31 on development plus the HA
    liveness probe the text census missed), and no more."""
    from common.route_grammar import OPEN
    heads = {rule.strip('/').split('/')[0] for rule, _ in OPEN}
    assert heads == {'token', 'tpm', 'filesauth', 'boot', 'kickstart', 'config', 'control',
                     'service', 'files', 'monitor', 'export', 'announce', 'scrape', 'ping'}
    assert all(rule.endswith('/<string:request_id>') for rule, _ in OPEN
               if rule.startswith(('/config/', '/control/', '/service/'))), \
        'under config, control and service only the status polls are open'
    assert len(OPEN) == 32


def test_a_route_of_an_unknown_shape_is_refused_not_defaulted():
    from common.route_grammar import GrammarError, requirement
    with pytest.raises(GrammarError):
        requirement('/foo/<string:name>', 'GET', {'name': 'x'})
    with pytest.raises(GrammarError):
        requirement('/config/node/<string:name>/_teleport', 'POST', {'name': 'x'})


@pytest.mark.parametrize('rule, method, expected', [
    ('/config/node/<string:name>', 'GET', {'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'r'}),
    ('/config/node/<string:name>', 'POST', {'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'w'}),
    ('/config/node/<string:name>/_delete', 'GET', {'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'w'}),
    ('/config/node/<string:name>/interfaces', 'GET', {'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'r'}),
    ('/config/secrets/node/<string:name>', 'GET', {'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'r'}),
    ('/config/profiles/group/<string:name>', 'POST', {'kind': 'object', 'entity': 'group', 'name': 'node001', 'bit': 'w'}),
    ('/config/osimage/<string:name>/_pack', 'GET', {'kind': 'object', 'entity': 'osimage', 'name': 'node001', 'bit': 'w'}),
    ('/config/group/<string:name>/_member', 'GET', {'kind': 'object', 'entity': 'group', 'name': 'node001', 'bit': 'r'}),
    ('/config/otherdev/<string:name>', 'GET', {'kind': 'object', 'entity': 'otherdevices', 'name': 'node001', 'bit': 'r'}),
    ('/config/cluster', 'POST', {'kind': 'object', 'entity': 'cluster', 'name': 'cluster', 'bit': 'w'}),
    ('/config/user/<string:name>', 'POST', {'kind': 'rootus', 'entity': 'user'}),
    ('/config/usergroup/<string:name>', 'POST', {'kind': 'rootus', 'entity': 'usergroup'}),
    ('/config/usergroup/<string:name>/members', 'POST', {'kind': 'membership', 'entity': 'usergroup', 'name': 'node001', 'bit': 'w'}),
    ('/hash', 'GET', {'kind': 'rootus', 'entity': 'hash'}),
    ('/whoami', 'GET', {'kind': 'self'}),
    ('/boot', 'GET', {'kind': 'open'}),
])
def test_the_grammar_reads_these_routes_as_the_design_says(rule, method, expected):
    from common.route_grammar import requirement
    assert requirement(rule, method, {'name': 'node001'}) == expected


def test_overrides_and_dynamic_routes_carry_what_the_later_check_needs():
    from common.route_grammar import requirement
    push = requirement('/config/node/<string:name>/_ospush', 'POST', {'name': 'node001'})
    assert push['kind'] == 'override' and push['action'] == 'ospush' and push['entity'] == 'node'
    couple = requirement('/config/route/<string:name>/<string:tableref>/<string:target>/_couple', 'GET',
                         {'name': 'r1', 'tableref': 'group', 'target': 'compute'})
    assert couple['kind'] == 'override' and couple['action'] == 'couple' and couple['args']['target'] == 'compute'
    power = requirement('/control/action/<string:subsystem>/<string:hostname>/_<string:action>', 'GET',
                        {'subsystem': 'power', 'hostname': 'node001', 'action': 'off'})
    assert power == {'kind': 'dynamic', 'entity': 'node', 'name': 'node001', 'action': 'off'}
