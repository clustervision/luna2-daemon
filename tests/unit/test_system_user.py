"""
The system user (TRIX-2085): the daemon talks to its peer as the configuration-file
account, user 0, and it does so from one place. A second place that builds a token
header is an internal caller the sweep did not know, and it would be the one that
locks a controller out of itself once the bits are enforced.
"""
import ast
import os

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
PRESENTER = os.path.join('utils', 'request.py')
# Both daemons read a token out of the same header name, so the two meanings of
# x-access-tokens land in the same search. This one is a token trixd minted, for trixd's
# own account out of trixd.ini, presented to trixd - nothing to do with Luna's user 0 or
# with Luna's access bits, so the sweep above does not have to know it. Named here one
# file at a time rather than exempting a directory, so a third presenter still has to
# come past this test and say which daemon it is talking to.
TRIXD_PRESENTER = os.path.join('plugins', 'addons', 'trixd.py')


def _python_files():
    for root, _, files in os.walk(DAEMON):
        for name in files:
            if name.endswith('.py'):
                yield os.path.join(root, name)


def _builds_token_header(tree):
    """A dict literal or a subscript assignment keyed 'x-access-tokens' constructs the header;
    reading request.headers['x-access-tokens'] is a consumer and does not count."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == 'x-access-tokens':
                    return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                        and target.slice.value == 'x-access-tokens'):
                    return True
    return False


def test_the_request_helper_is_the_only_presenter_of_a_token_to_luna():
    presenters = []
    for path in _python_files():
        with open(path, encoding='utf-8') as source:
            tree = ast.parse(source.read(), filename=path)
        if _builds_token_header(tree):
            presenters.append(os.path.relpath(path, DAEMON))
    assert sorted(presenters) == sorted([PRESENTER, TRIXD_PRESENTER]), (
        f"files that build an x-access-tokens header: {sorted(presenters)}. Every call to a Luna "
        "peer goes through utils/request.py as the configuration-file account; a new presenter is "
        "an internal caller the system-user sweep on TRIX-2085 does not know. If the new one "
        "presents to trixd rather than to Luna, name it beside TRIXD_PRESENTER and say so.")


def test_the_request_helper_logs_in_as_the_configuration_file_account():
    with open(os.path.join(DAEMON, PRESENTER), encoding='utf-8') as source:
        tree = ast.parse(source.read())
    seen = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                and node.slice.value in ('USERNAME', 'PASSWORD')
                and isinstance(node.value, ast.Subscript) and isinstance(node.value.slice, ast.Constant)
                and node.value.slice.value == 'API'):
            seen.add(node.slice.value)
    assert seen == {'USERNAME', 'PASSWORD'}, 'the peer login must use the [API] account and nothing else'
