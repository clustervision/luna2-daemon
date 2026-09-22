"""
Every registered route declares what it requires (TRIX-2084), proven from Flask's own
route map rather than by review: a text scan of the route files misses decorators with
nested parentheses, and the whole failure mode is the next route being forgotten.
"""
import pytest
from flask import Blueprint, Flask

from cases.route_requirements_cases import (SKIP_METHODS, app as _app, blueprints as _blueprints,
                                            fake_args as _fake_args,
                                            registered_by_the_daemon as _registered_by_the_daemon,
                                            token_layer as _token_layer)


def test_the_daemon_registers_every_blueprint_the_route_modules_define():
    defined = set(_blueprints())
    registered = _registered_by_the_daemon()
    assert defined == registered, (
        f"defined but not registered: {sorted(defined - registered)}; "
        f"registered but not defined: {sorted(registered - defined)}")


def test_every_route_is_deliberately_open_or_classified():
    from common.route_grammar import OPEN, KINDS, requirement
    from utils.access import GOVERNED

    app = _app()
    seen_open = set()
    unlisted_open = []
    unclassified = []
    ungoverned = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        layer = _token_layer(app.view_functions[rule.endpoint])
        for method in sorted(rule.methods - SKIP_METHODS):
            if layer is None:
                if (rule.rule, method) not in OPEN:
                    unlisted_open.append(f'{method} {rule.rule}')
                seen_open.add((rule.rule, method))
                continue
            assert (rule.rule, method) not in OPEN, f"{method} {rule.rule} is on the open list but has a token decorator"
            try:
                answer = requirement(rule.rule, method, _fake_args(rule), getattr(layer, 'requires', None))
            except Exception as exp:
                unclassified.append(f'{method} {rule.rule}: {exp}')
                continue
            assert answer['kind'] in KINDS, (rule.rule, method, answer)
            if answer['kind'] in ('object', 'override') and not answer.get('entity', '').startswith('<'):
                if answer['entity'] not in GOVERNED:
                    ungoverned.append(f"{method} {rule.rule} reads as entity {answer['entity']}")
    assert not unlisted_open, ('routes without a token that are not on the deliberately-open list:\n  '
                               + '\n  '.join(unlisted_open))
    assert not unclassified, 'routes the grammar cannot place:\n  ' + '\n  '.join(unclassified)
    assert not ungoverned, ('object routes whose entity is not a governed table (alias it in the grammar):\n  '
                            + '\n  '.join(ungoverned))
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


def test_a_declaration_on_the_decorator_wins_over_the_grammar():
    """The author of an odd route says what it needs where the route is written."""
    from common.route_grammar import GrammarError, requirement
    from common.validate_auth import token_required

    @token_required(requires=('node', 'x'))
    def power(name=None):
        return name

    @token_required(requires='rootus')
    def sweep():
        return None

    assert power.requires == ('node', 'x') and sweep.requires == 'rootus'
    assert requirement('/config/node/<string:name>', 'GET', {'name': 'node001'}, power.requires) == {
        'kind': 'object', 'entity': 'node', 'name': 'node001', 'bit': 'x'}
    assert requirement('/config/node/<string:name>', 'GET', {'name': 'node001'}, sweep.requires) == {
        'kind': 'rootus', 'entity': 'config'}
    with pytest.raises(GrammarError):
        requirement('/config/node/<string:name>', 'GET', {}, 'superuser')
    with pytest.raises(GrammarError):
        requirement('/config/node/<string:name>', 'GET', {}, ('node', 'q'))
