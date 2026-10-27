"""
TRIX-2203: a pack says so when the image tree and the registered kernel disagree. Only the
registered kernel is served over the network, but every kernel in the tree rides to disk,
so a second one, or a registered one that is gone, is a surprise at the node's disk boot
unless the operator hears about it at pack time.
"""
import os

import pytest

from utils.kernels import kernels_in_image, kernel_state_warning, newest_kernel, version_key

EL9_6 = '5.14.0-570.58.1.el9_6.x86_64'
EL9_7 = '5.14.0-611.30.1.el9_7.x86_64'
EL9_4 = '5.14.0-427.37.1.el9_4.x86_64'


def _kernel(tree, version, vmlinuz=True, husk=False):
    """Lay down what a kernel package leaves in an image; a husk is what removing one leaves."""
    moddir = tree / 'lib' / 'modules' / version
    moddir.mkdir(parents=True, exist_ok=True)
    (moddir / 'modules.dep').write_text('')
    if not husk:
        (moddir / 'kernel').mkdir(exist_ok=True)
    if vmlinuz:
        (tree / 'boot').mkdir(exist_ok=True)
        (tree / 'boot' / f'vmlinuz-{version}').write_text('')


def test_the_version_sort_orders_builds_numerically():
    assert sorted([EL9_7, EL9_4, EL9_6], key=version_key) == [EL9_4, EL9_6, EL9_7]


def test_only_a_vmlinuz_with_a_real_module_tree_counts(tmp_path):
    _kernel(tmp_path, EL9_6)
    _kernel(tmp_path, EL9_4, vmlinuz=False)                       # module tree without a kernel file
    _kernel(tmp_path, '5.14.0-999.el9.x86_64', husk=True)          # a removed kernel's leftovers
    _kernel(tmp_path, '0-rescue-abc')                              # never what a node runs
    _kernel(tmp_path, f'{EL9_7}+debug')
    assert kernels_in_image(str(tmp_path)) == [EL9_6]


def test_one_kernel_and_it_is_the_registered_one_is_silent(tmp_path):
    _kernel(tmp_path, EL9_6)
    assert kernel_state_warning(str(tmp_path), EL9_6) == ''


def test_a_second_kernel_is_named_as_riding_to_disk(tmp_path):
    """The customer case: a package update inside a registered image added a newer kernel."""
    _kernel(tmp_path, EL9_6)
    _kernel(tmp_path, EL9_7)
    warning = kernel_state_warning(str(tmp_path), EL9_6)
    assert warning.startswith('warning:') and '2 kernels' in warning
    assert f'{EL9_6} is registered' in warning and EL9_7 in warning


def test_a_registered_kernel_that_is_gone_is_named_with_what_is_there(tmp_path):
    _kernel(tmp_path, EL9_7)
    warning = kernel_state_warning(str(tmp_path), EL9_6)
    assert f'registered kernel {EL9_6} is not in the image' in warning and EL9_7 in warning
    assert 'no kernel at all' in kernel_state_warning(str(tmp_path / 'empty'), EL9_6)


def test_the_pack_asks_before_it_builds():
    """The warning has to be in the pack's own status stream, ahead of the build, or the
    operator sees it only in the daemon log, which is what changed nothing on the customer."""
    import inspect
    from utils.osimage import OsImage
    source = inspect.getsource(OsImage.pack_osimage)
    asked = source.index('kernel_state_warning(')
    built = source.index('os_image_plugin().pack(')
    assert asked < built
    assert 'Status().add_message' in source[asked:built]


def test_the_kernel_file_rule_is_the_one_every_pack_plugin_applies():
    """A kernel the enumeration counts is one a pack can serve, on every distro and
    architecture: both image plugins look for /boot/vmlinuz-<version>, and so does this."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    plugins = os.path.join(root, 'daemon', 'plugins', 'osimage', 'operations', 'image')
    for name in sorted(os.listdir(plugins)):
        if name.endswith('.py'):
            source = open(os.path.join(plugins, name)).read()
            assert "'/boot/vmlinuz-'" in source, f'{name} names its kernel file differently'
    util = open(os.path.join(root, 'daemon', 'utils', 'kernels.py')).read()
    assert "f'vmlinuz-{version}'" in util


def test_osgrab_picks_the_newest_version_not_the_newest_directory(tmp_path):
    import time
    _kernel(tmp_path, EL9_7)
    _kernel(tmp_path, EL9_6)
    past = time.time() - 3600
    os.utime(tmp_path / 'lib' / 'modules' / EL9_7, (past, past))      # newer version, older directory
    assert newest_kernel(str(tmp_path)) == (EL9_7, [EL9_6, EL9_7])
    assert newest_kernel(str(tmp_path / 'empty')) == (None, [])


def test_the_osgrab_plugin_registers_through_the_same_enumeration():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    source = open(os.path.join(root, 'daemon', 'plugins', 'osimage', 'operations', 'osgrab', 'default.py')).read()
    assert 'ls -tr' not in source and 'newest_kernel(' in source


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['osimage', 'osimagetag', 'queue']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _register(name, version):
    from base.osimage import OSImage
    return OSImage().change_kernel(name, {'config': {'osimage': {name: {'kernelversion': version, 'bare': True}}}})


def test_registering_a_kernel_the_image_does_not_carry_is_refused(db, tmp_path):
    from utils.helper import Helper
    tree = tmp_path / 'img'
    _kernel(tree, EL9_6)
    db.insert('osimage', Helper().make_rows({'name': 'img', 'path': str(tree), 'kernelversion': EL9_6}))

    status, message = _register('img', EL9_7)

    assert status is False
    assert EL9_7 in message and EL9_6 in message, 'the refusal names what the image does carry'
    assert db.get_record(table='osimage', where="name = 'img'")[0]['kernelversion'] == EL9_6, 'nothing written'


def test_registering_a_kernel_the_image_carries_is_stored(db, tmp_path):
    from utils.helper import Helper
    tree = tmp_path / 'img'
    _kernel(tree, EL9_6)
    _kernel(tree, EL9_7)
    db.insert('osimage', Helper().make_rows({'name': 'img', 'path': str(tree), 'kernelversion': EL9_6}))

    status, message = _register('img', EL9_7)

    assert status is True, message
    assert db.get_record(table='osimage', where="name = 'img'")[0]['kernelversion'] == EL9_7


def test_a_tree_not_on_this_controller_is_registered_unchecked(db, tmp_path):
    from utils.helper import Helper
    db.insert('osimage', Helper().make_rows({'name': 'img', 'path': str(tmp_path / 'absent'), 'kernelversion': EL9_6}))
    status, message = _register('img', EL9_7)
    assert status is True, message
