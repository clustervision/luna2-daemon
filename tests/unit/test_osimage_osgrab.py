"""
A grab writes its rsync output to a file of its own, named by the image and the request, and
GET /config/osimage/<name>/osgrab/<request_id> answers what that grab changes and deletes.

The file is named to the plugin on the instance, not as a keyword: a site's own grab plugin
keeps the old signature and must still be called. Grabs run on the master, so the list is
asked of the master, and another controller answers 503 rather than a 404 that reads as
"no such grab". The push plugin names its output file in one place the same way, and keeps
/tmp/ospush.out.
"""
import importlib

import pytest

from test_access_bits import client, db, world  # noqa: F401 - fixtures

OUTPUT = """receiving incremental file list
etc/
etc/motd
etc/localtime -> ../usr/share/zoneinfo/UTC
etc/hosts.bak => etc/hosts
deleting etc/old.conf

sent 1,234 bytes  received 5,678 bytes  13,824.00 bytes/sec
total size is 9,012  speedup is 1.30 (DRY RUN)
"""


@pytest.fixture
def grabbed(db, world, tmp_path, monkeypatch):
    import base.osimage
    from utils.ha import HA
    from utils.helper import Helper
    db.insert('osimage', Helper().make_rows({'name': 'alma9', 'usergroups': str(world.intel), 'access': '770'}))
    monkeypatch.setattr(base.osimage, 'GRAB_OUTPUT', str(tmp_path / 'osgrab-{osimage}-{request_id}.out'))
    monkeypatch.setattr(HA, 'get_hastate', lambda self: False)
    (tmp_path / 'osgrab-rocky9-1.2.out').write_text(OUTPUT)


def in_a_pair(monkeypatch, master):
    from utils.ha import HA
    monkeypatch.setattr(HA, 'get_hastate', lambda self: True)
    monkeypatch.setattr(HA, 'get_role', lambda self: master)


def test_a_reader_gets_what_the_grab_changes_and_deletes(client, world, grabbed):
    assert client.as_(world.ids['dave']).get('/config/osimage/rocky9/osgrab/1.2') == \
        (200, {'changed': ['etc/', 'etc/motd', 'etc/localtime', 'etc/hosts.bak'], 'deleted': ['etc/old.conf']})


@pytest.mark.parametrize('who,path,code', [
    ('dave', '/config/osimage/rocky9/osgrab/9.9', 404),
    ('erin', '/config/osimage/alma9/osgrab/1.2', 404),
    ('dave', '/config/osimage/rocky9/osgrab/1;2', 400),
    (None, '/config/osimage/rocky9/osgrab/1.2', 401),
])
def test_no_grab_a_hidden_image_a_bad_request_id_and_no_token_are_refused(client, world, grabbed, who, path, code):
    assert (client.as_(world.ids[who]) if who else client).get(path)[0] == code


def test_the_master_answers_and_another_controller_says_where_to_ask(client, world, grabbed, monkeypatch):
    in_a_pair(monkeypatch, master=True)
    assert client.as_(world.ids['dave']).get('/config/osimage/rocky9/osgrab/1.2')[0] == 200
    in_a_pair(monkeypatch, master=False)
    code, body = client.as_(world.ids['dave']).get('/config/osimage/rocky9/osgrab/1.2')
    assert code == 503
    assert 'not the master' in body.get('message', '') and 'changed' not in body


def run_plugin(monkeypatch, operation, filesystems, output=None):
    """Run the default grab or push plugin with its commands recorded rather than run."""
    module = importlib.import_module(f'plugins.osimage.operations.{operation}.default')
    commands = []
    monkeypatch.setattr(module.Helper, 'runcommand', lambda self, command, *args: commands.append(command) or (('', ''), 0))
    monkeypatch.setattr(module, 'newest_kernel', lambda path: ('5.14', ['5.14']), raising=False)
    plugin = module.Plugin()
    if output:
        plugin.output = output
    status, message, *_ = (plugin.grab if operation == 'osgrab' else plugin.push)('rocky9', '/img', 'node001', filesystems, [])
    return status, message, commands


@pytest.mark.parametrize('operation', ['osgrab', 'ospush'])
@pytest.mark.parametrize('filesystems', [[], ['/etc']])
def test_the_plugin_writes_only_to_the_output_it_is_given(monkeypatch, operation, filesystems):
    status, message, commands = run_plugin(monkeypatch, operation, filesystems, output='/out')
    assert status and message == 'Success. See /out for details'
    assert commands and all(command.endswith("'/out'") for command in commands)


@pytest.mark.parametrize('operation', ['osgrab', 'ospush'])
@pytest.mark.parametrize('filesystems', [[], ['/etc']])
def test_left_alone_the_plugin_writes_to_its_old_file(monkeypatch, operation, filesystems):
    status, message, commands = run_plugin(monkeypatch, operation, filesystems)
    assert status and message == f'Success. See /tmp/{operation}.out for details'
    assert commands and all(command.rstrip("'").endswith(f'/tmp/{operation}.out') for command in commands)


class OldSignature():
    """A site's grab plugin as written before core named an output file: no output keyword."""
    seen = {}

    def grab(self, osimage, image_path, node, grab_filesystems=[], grab_exclude=[], nodry=False):
        OldSignature.seen = {'output': getattr(self, 'output', None)}
        return True, 'Success', None


def test_a_site_plugin_with_the_old_signature_still_grabs(sqlite_db, monkeypatch, tmp_path):
    import utils.osimage
    from utils.database import Database
    from utils.helper import Helper
    monkeypatch.setattr(utils.osimage, 'sleep', lambda seconds: None)
    monkeypatch.setattr(Helper, 'plugin_load', lambda self, *args: OldSignature)
    groupid = Database().insert('group', Helper().make_rows({'name': 'compute'}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': groupid}))
    Database().insert('osimage', Helper().make_rows({'name': 'rocky9', 'path': str(tmp_path / 'rocky9')}))
    task = Database().insert('queue', Helper().make_rows({
        'subsystem': 'osimage', 'status': 'in progress', 'request_id': 'r1', 'task': 'grab_osimage',
        'param': 'node001:rocky9:False', 'noeof': 0, 'created': 'NOW'}))
    assert utils.osimage.OsImage().grab_osimage(task, 'r1') is True
    assert OldSignature.seen.get('output') == '/tmp/osgrab-rocky9-r1.out'
