"""
The BIOS, firmware and profile status routes name a node or a group, not a catalogue
object, so the gate checks read on that node or group. The base methods are stubs: whether
the view is reached is the question.
"""
import json

import pytest
from flask import Flask
from jwt import encode

from test_access_bits import db, world  # noqa: F401 - fixtures

NODE_ROUTES = ['/config/biosconfig/status/node001', '/config/firmwarecatalog/status/node001',
               '/config/profiles/status/node001']
GROUP_ROUTES = ['/config/biosconfig/status/group/compute', '/config/firmwarecatalog/status/group/compute']


@pytest.fixture
def get(db, world, monkeypatch):
    from base.bios import Bios
    from base.firmware import Firmware
    from base.profile import Profile
    from common.constant import CONSTANT
    from routes.config_bios import bios_blueprint
    from routes.config_firmware import firmware_blueprint
    from routes.config_profiles import profiles_blueprint
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    for table in ('biosconfig', 'firmwarecatalog', 'profile'):
        db.create(table, DBStructure().get_database_table_structure(table))
    db.insert('group', Helper().make_rows({'name': 'compute', 'usergroups': str(world.intel), 'access': '750'}))
    monkeypatch.setattr(Bios, 'status', lambda self, name=None, group=None: (True, {'reached': name or group}))
    monkeypatch.setattr(Firmware, 'status', lambda self, name=None, group=None: (True, {'reached': name or group}))
    monkeypatch.setattr(Profile, 'status', lambda self, name=None: (True, {'reached': name}))

    app = Flask(__name__)
    app.testing = True
    for blueprint in (bios_blueprint, firmware_blueprint, profiles_blueprint):
        app.register_blueprint(blueprint)

    def call(userid, path):
        token = encode({'id': userid}, CONSTANT['API']['SECRET_KEY'], 'HS256')
        response = app.test_client().get(path, headers={'x-access-tokens': token})
        return response.status_code, json.loads(response.data)

    return call


@pytest.mark.parametrize('path', NODE_ROUTES + GROUP_ROUTES)
def test_a_reader_of_the_node_and_group_reaches_the_status(get, world, path):
    code, body = get(world.ids['dave'], path)
    assert code == 200, body
    assert body == {'reached': path.rsplit('/', 1)[-1]}


@pytest.mark.parametrize('path', NODE_ROUTES + GROUP_ROUTES)
def test_outside_the_scope_the_node_or_group_does_not_exist(get, world, path):
    code, body = get(world.ids['erin'], path)
    expected = 'group compute' if '/group/' in path else 'node node001'
    assert (code, body['message']) == (404, f'{expected} is not available')
