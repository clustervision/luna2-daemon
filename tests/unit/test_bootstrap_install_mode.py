"""
A fresh cluster takes its install_mode from [CLUSTER] INSTALL_MODE in bootstrap.ini, so
the installer can make lpart the default without touching clusters bootstrapped before.
"""
from configparser import RawConfigParser

import pytest

from utils.database import Database

STOCK = """
[CLUSTER]
DOMAIN_SEARCH = cluster
BIND_LEGACY = False
{install_mode}

[HOSTS]
CONTROLLER = controller:10.141.255.254
SERVERPORT = 7050
NODELIST = node[001-004]

[NETWORKS]
cluster = default:ethernet:10.141.0.0/16:DHCP:10.141.155.0-10.141.165.0
ipmi = bmc:ethernet:10.148.0.0/16

[GROUPS]
NAME = compute-group

[OSIMAGE]
NAME = compute-image
PATH = /trinity/images/compute-image

[BMCSETUP]
NAME = default-bmcsetup
USERNAME = admin
PASSWORD = x
"""


def bootstrapped(sqlite_db, tmp_path, monkeypatch, line):
    from common import bootstrap
    # both are module globals: a parser left over from another test would carry its keys
    monkeypatch.setattr(bootstrap, 'configParser', RawConfigParser())
    monkeypatch.setattr(bootstrap, 'BOOTSTRAP', {
        'HOSTS': {'HOSTNAME': None, 'CONTROLLER': None, 'NODELIST': None, 'PRIMARY_DOMAIN': None},
        'NETWORKS': {'cluster': None, 'ipmi': None, 'ib': None},
        'GROUPS': {'NAME': None},
        'OSIMAGE': {'NAME': None},
        'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}}, raising=False)
    ini = tmp_path / 'bootstrap.ini'
    ini.write_text(STOCK.format(install_mode=line))
    # bootstrap ends by renaming the file into the controller's fixed config directory
    monkeypatch.setattr(bootstrap.os, 'rename', lambda *args: None)
    assert bootstrap.get_config(str(ini))
    bootstrap.bootstrap(str(ini))
    return Database().get_record(table='cluster')[0]


def test_the_installer_line_sets_the_cluster_install_mode(sqlite_db, tmp_path, monkeypatch):
    cluster = bootstrapped(sqlite_db, tmp_path, monkeypatch, 'INSTALL_MODE = auto')
    assert cluster['install_mode'] == 'auto'
    assert cluster['domain_search'] == 'cluster'


def test_a_bootstrap_ini_without_the_line_leaves_it_unset(sqlite_db, tmp_path, monkeypatch):
    cluster = bootstrapped(sqlite_db, tmp_path, monkeypatch, '')
    assert not cluster['install_mode']


@pytest.mark.parametrize('value, expected', [
    ('auto', 'auto'), (' Memboot ', 'memboot'), ('legacy', 'legacy'), ('', None), ('fast', None)])
def test_only_a_known_mode_is_taken(value, expected):
    from common.bootstrap import default_install_mode
    assert default_install_mode({'INSTALL_MODE': value}) == expected
    assert default_install_mode({}) is None


@pytest.mark.parametrize('line, seeded', [
    ('', True), ('INSTALL_MODE = legacy', True),
    ('INSTALL_MODE = memboot', False), ('INSTALL_MODE = auto', False), ('INSTALL_MODE = sanitize', False)])
def test_the_compute_group_gets_the_tmpfs_scripts_only_for_legacy(sqlite_db, tmp_path, monkeypatch, line, seeded):
    """TRIX-2196: lpart mounts its own root and writes its own fstab, so a group that
    starts in an lpart mode carries no legacy part/post scripts to run before it."""
    bootstrapped(sqlite_db, tmp_path, monkeypatch, line)
    group = Database().get_record(table='group', where="name = 'compute-group'")[0]
    assert bool(group['partscript']) is seeded
    assert bool(group['postscript']) is seeded
    assert not group['prescript']
