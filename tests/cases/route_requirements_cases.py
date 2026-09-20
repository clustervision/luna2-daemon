"""
What every registered route requires, as one map: the input of the golden and of the
derived test. Built from Flask's own route map over every blueprint the route modules
define, with one placeholder per path argument so the answer has the shape of a real
request. A declaration made on a route's decorator is read off the wrapper chain and
wins over the grammar, exactly as it does at request time.
"""
import ast
import importlib
import os
import pkgutil

from flask import Blueprint, Flask

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
SKIP_METHODS = {'HEAD', 'OPTIONS'}


def blueprints():
    """Every Blueprint defined by a module under routes/, keyed by the name luna.py imports."""
    import routes
    found = {}
    for module_info in pkgutil.iter_modules(routes.__path__):
        module = importlib.import_module(f'routes.{module_info.name}')
        for attribute, value in vars(module).items():
            if isinstance(value, Blueprint):
                found[attribute] = value
    return found


def registered_by_the_daemon():
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


def app():
    flask_app = Flask(__name__)
    for blueprint in blueprints().values():
        flask_app.register_blueprint(blueprint)
    return flask_app


def _token_wrapper_codes():
    """The code objects of the two decorators' inner functions: what a wrapped view runs first."""
    from common.validate_auth import provision_token_required, token_required
    return {token_required(lambda **kwargs: None).__code__,
            provision_token_required(lambda **kwargs: None).__code__}


def token_layer(view):
    """
    The token decorator's own wrapper in the chain functools.wraps leaves behind, or None.
    wraps copies the view's name onto every wrapper, so a name tells nothing; the code
    object does. The layer carries what the route declared, if anything.
    """
    codes = _token_wrapper_codes()
    while view is not None:
        if getattr(view, '__code__', None) in codes:
            return view
        view = getattr(view, '__wrapped__', None)
    return None


def fake_args(rule):
    """One value per path argument, so the grammar sees the shape a real request has."""
    return {argument: f'<{argument}>' for argument in rule.arguments}


def build_requirement_map(flask_app=None):
    """
    Output - {'METHOD /rule': requirement} for every registered route; open routes say
             so; a route neither declared nor placed by the grammar carries the error text,
             so the golden and the test both see it.
    """
    from common.route_grammar import requirement
    flask_app = flask_app or app()
    result = {}
    for rule in flask_app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        layer = token_layer(flask_app.view_functions[rule.endpoint])
        for method in sorted(rule.methods - SKIP_METHODS):
            key = f'{method} {rule.rule}'
            if layer is None:
                result[key] = {'kind': 'no-token'}
                continue
            try:
                result[key] = requirement(rule.rule, method, fake_args(rule), getattr(layer, 'requires', None))
            except Exception as exp:
                result[key] = {'error': str(exp)}
    return dict(sorted(result.items()))
