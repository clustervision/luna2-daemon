"""
A BIOS push without a name applies what each node is assigned, its own else its group's,
so the gate requires write on exactly those configurations. push_bios is a stub: whether
it is reached is the question.
"""
import json

import pytest
from flask import Flask
from jwt import encode

from test_access_bits import db, world  # noqa: F401 - fixtures


@pytest.fixture
def push(db, world, monkeypatch):
    from base.bios import Bios
    from common.constant import CONSTANT
    from routes.config_bios import bios_blueprint
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    db.create('biosconfig', DBStructure().get_database_table_structure('biosconfig'))
    alice = str(world.ids['alice'])
    world.configs = {name: db.insert('biosconfig', Helper().make_rows(dict(name=name, **columns)))
                     for name, columns in (('golden', {'owners': alice}), ('gpu', {'owners': alice}),
                                           ('locked', {}))}

    def group(name, config=None):
        return db.insert('group', Helper().make_rows({'name': name, 'owners': alice, 'access': '750',
                                                      'biosconfigid': world.configs.get(config)}))

    def node(name, groupid=None, config=None):
        db.insert('node', Helper().make_rows({'name': name, 'owners': alice, 'access': '750', 'groupid': groupid,
                                              'biosconfigid': world.configs.get(config)}))

    world.group, world.node = group, node
    monkeypatch.setattr(Bios, 'push_bios', lambda self, object_type=None, name=None, request_data=None:
                        (True, f'reached {object_type} {name}', 'request'))

    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(bios_blueprint)

    def call(userid, object_type, name, record=None):
        token = encode({'id': userid}, CONSTANT['API']['SECRET_KEY'], 'HS256')
        response = app.test_client().post(f'/config/{object_type}/{name}/_biospush',
                                          json={'config': {object_type: {name: record or {}}}},
                                          headers={'x-access-tokens': token})
        return response.status_code, json.loads(response.data)['message']

    return call


def test_a_node_without_its_own_configuration_is_checked_on_its_groups(push, world):
    world.node('node010', world.group('compute', 'golden'))
    for userid in (world.ids['alice'], 0):
        assert push(userid, 'node', 'node010') == (200, 'reached node node010')


def test_a_groups_configuration_the_caller_may_not_change_is_still_refused(push, world):
    world.node('node010', world.group('compute', 'locked'))
    world.node('node011', config='locked')
    refusal = 'changing or removing biosconfig locked is not permitted: you may read it (other)'
    assert push(world.ids['alice'], 'node', 'node010') == (403, refusal)
    assert push(world.ids['alice'], 'node', 'node011') == (403, refusal)


def test_a_group_with_none_is_checked_on_what_each_member_has(push, world):
    compute = world.group('compute')
    world.node('node010', compute, 'golden')
    world.node('node011', compute, 'gpu')
    for userid in (world.ids['alice'], 0):
        assert push(userid, 'group', 'compute') == (200, 'reached group compute')


def test_a_member_configuration_the_caller_may_not_change_refuses_the_group(push, world):
    compute = world.group('compute', 'golden')
    world.node('node010', compute)
    world.node('node011', compute, 'locked')
    code, message = push(world.ids['alice'], 'group', 'compute')
    assert (code, message) == (403, 'changing or removing biosconfig locked is not permitted: you may read it (other)')


def test_a_named_configuration_is_checked_rather_than_the_assignment(push, world):
    world.node('node010', world.group('compute', 'golden'))
    assert push(world.ids['alice'], 'node', 'node010', {'biosconfig': 'locked'})[0] == 403
    world.node('node011', config='locked')
    assert push(world.ids['alice'], 'node', 'node011', {'biosconfig': 'golden'}) == (200, 'reached node node011')


def test_nothing_assigned_anywhere_is_the_bad_request_it_always_was(push, world):
    world.node('node010', world.group('compute'))
    world.node('node011')
    for userid in (world.ids['alice'], world.ids['zed'], 0):
        assert push(userid, 'node', 'node010') == (400, 'Invalid request: no biosconfig named')
        assert push(userid, 'node', 'node011') == (400, 'Invalid request: no biosconfig named')
        assert push(userid, 'group', 'compute') == (400, 'Invalid request: no biosconfig named')
