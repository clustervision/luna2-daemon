"""
A node may import its own hardware alert rules with the provision token it holds.

The AlertX post-boot hook fetches a token through /tpm and posts to
/import/prometheus_hw_rules. Since /tpm issues provision-scoped tokens the
import route, admin-only, refused every node on every boot with a 403 nobody
looked at, and no node's hardware rules were imported for three months. The
route now takes a provision token for that one importer, for the node the
token names, and nothing else.
"""

import json

import pytest
from flask import Flask
from jwt import encode


def _app():
    from common.constant import CONSTANT
    from common.validate_auth import provision_token_required
    app = Flask(__name__)

    @app.route('/import/<string:name>', methods=['POST'])
    @provision_token_required(node_in_payload='hostname', only=('prometheus_hw_rules',))
    def import_data(name=None):
        return json.dumps({'imported': name}), 200

    @app.route('/boot/install/<string:node>', methods=['GET'])
    @provision_token_required
    def boot_install(node=None):
        return json.dumps({'node': node}), 200

    key = CONSTANT['API']['SECRET_KEY']
    node = encode({'node': 'node001', 'scope': 'provision'}, key, 'HS256')
    admin = encode({'id': 0}, key, 'HS256')
    return app.test_client(), node, admin


def _post(client, token, name, hostname):
    return client.post(f'/import/{name}', headers={'x-access-tokens': token},
                       data=json.dumps({'hostname': hostname}), content_type='application/json')


def _post_list(client, token, hosts):
    body = [{'hostname': host, 'force': False} for host in hosts]
    return client.post('/import/prometheus_hw_rules', headers={'x-access-tokens': token},
                       data=json.dumps(body), content_type='application/json')


def test_the_hook_posts_a_list_with_the_fqdn_and_that_is_its_own_node():
    """What alertx-hook.sh actually sends: a one-entry list naming the node by FQDN."""
    client, node, _ = _app()
    assert _post_list(client, node, ['node001.cluster']).status_code == 200


def test_a_list_naming_another_node_anywhere_is_refused():
    client, node, _ = _app()
    assert _post_list(client, node, ['node001.cluster', 'node002.cluster']).status_code == 403
    assert _post_list(client, node, []).status_code == 403


def test_a_node_may_import_its_own_hardware_rules():
    client, node, _ = _app()
    assert _post(client, node, 'prometheus_hw_rules', 'node001').status_code == 200


def test_a_node_may_not_import_for_another_node():
    client, node, _ = _app()
    assert _post(client, node, 'prometheus_hw_rules', 'node002').status_code == 403


def test_a_node_may_not_use_any_other_importer():
    client, node, _ = _app()
    assert _post(client, node, 'boot_plugins', 'node001').status_code == 403


def test_a_missing_hostname_is_refused_not_guessed():
    client, node, _ = _app()
    response = client.post('/import/prometheus_hw_rules', headers={'x-access-tokens': node},
                           data=json.dumps({}), content_type='application/json')
    assert response.status_code == 403


def test_an_admin_token_is_not_restricted():
    client, _, admin = _app()
    assert _post(client, admin, 'boot_plugins', 'whatever').status_code == 200


def test_the_bare_decorator_still_matches_the_path_segment():
    client, node, _ = _app()
    assert client.get('/boot/install/node001', headers={'x-access-tokens': node}).status_code == 200
    assert client.get('/boot/install/node002', headers={'x-access-tokens': node}).status_code == 403
