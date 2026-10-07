"""
A vlan on its own interface, bond or not, gets the interface's IP configuration.

NetworkManager keeps one device per profile: a bond or an ethernet profile that
also carries a [vlan] section either drops the vlan silently (the bond comes up
with the address untagged) or refuses to start. So the install script must write
the parent and the vlan as two profiles, the address on the vlan, and a parent
without an address must not fall back to DHCP. Netplan describes both devices in
one file; there the address must sit under the vlan, and an interface without an
address must still render a list.

These run the real install route against a seeded database and read back what the
node would write, per interface, through the install script's own heredocs.
"""

import inspect
import os
import re
import subprocess

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NM_DISTRIBUTIONS = [('redhat', '8'), ('redhat', '9'), ('redhat', '10'), ('opensuse', '15')]


@pytest.fixture
def db(tmp_path, monkeypatch):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure

    monkeypatch.setitem(constant.CONSTANT['DATABASE'], 'DATABASE', str(tmp_path / 'unit.db'))
    monkeypatch.setitem(constant.CONSTANT['TEMPLATES'], 'TEMPLATE_FILES',
                        os.path.join(ROOT, 'daemon', 'templates'))
    monkeypatch.setitem(constant.CONSTANT['PLUGINS'], 'PLUGINS_DIRECTORY',
                        os.path.join(ROOT, 'daemon', 'plugins'))
    database.local_thread.connection = None
    DBStructure().create_database_tables()
    yield Database()
    database.local_thread.connection = None


def seed(db, distribution, osrelease, interfaces):
    """A node with the given interfaces, each (columns, ipaddress); 10.142.x sits on cluster2, the rest on cluster."""
    from utils.helper import Helper
    db.insert('cluster', Helper().make_rows(
        {'name': 'cluster', 'security': 0, 'provision_method': 'http', 'provision_fallback': 'http'}))
    db.insert('network', Helper().make_rows(
        {'name': 'cluster', 'network': '10.141.0.0', 'subnet': '16', 'type': 'ethernet'}))
    db.insert('network', Helper().make_rows(
        {'name': 'cluster2', 'network': '10.142.0.0', 'subnet': '16', 'type': 'ethernet'}))
    image = db.insert('osimage', Helper().make_rows(
        {'name': 'image', 'distribution': distribution, 'osrelease': osrelease, 'imagefile': 'image.tar.bz2'}))
    group = db.insert('group', Helper().make_rows(
        {'name': 'compute', 'osimageid': image, 'provision_interface': 'BOOTIF'}))
    node = db.insert('node', Helper().make_rows({'name': 'node001', 'groupid': group}))
    for columns, ipaddress in interfaces:
        networkid = 2 if ipaddress and ipaddress.startswith('10.142.') else 1
        interface = db.insert('nodeinterface', Helper().make_rows(dict(columns, nodeid=node)))
        db.insert('ipaddress', Helper().make_rows(
            {'tableref': 'nodeinterface', 'tablerefid': interface, 'networkid': networkid, 'ipaddress': ipaddress}))


def rendered_files(distribution, osrelease):
    """Install script from the real route, split into {interface: (file it writes, its content)}."""
    from flask import Flask
    from routes.boot import boot_install
    with Flask(__name__).app_context():
        script, code = inspect.unwrap(boot_install)(node='node001')
    assert code == 200, script
    files = {'': (None, script)}
    heredoc = r'######### (\S+) #########\n.*?cat << LUNAEOF > "/lunatmp/interface_\$\{interface_name\}\.conf"\n(.*?)\nLUNAEOF\n'
    for name, content in re.findall(heredoc, script, re.S):
        path = re.search(r'^#FILE (\S+)', content, re.M)
        files[name] = (path.group(1) if path else None, content)
    return files


def keyfile(content):
    """NetworkManager keyfile as {section: [lines]}."""
    sections, current = {}, None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            current = sections.setdefault(line[1:-1], [])
        elif line and not line.startswith('#') and current is not None:
            current.append(line)
    return sections


def netplan(content):
    """
    Netplan YAML as a dict, after bash has expanded the heredoc the way the node
    does; only the MAC read from /sys is stood in for.
    """
    text = re.sub(r'\$\(cat /sys/class/net/[^)]*\)', '02:00:00:00:00:01', content)
    expanded = subprocess.run(
        ['bash', '-c', f'cat << LUNAEOF\n{text}\nLUNAEOF'], capture_output=True, text=True, check=True,
        env={'PATH': os.environ['PATH'], 'interface_name': 'IFACE', 'parent_name': 'PARENT',
             'interface_bootif': 'ens1', 'rootmnt': ''}).stdout
    return yaml.safe_load('\n'.join(l for l in expanded.splitlines() if not l.startswith('#'))) or {}


BOND_SELF_VLAN = [({'interface': 'bond0', 'vlanid': '100', 'bond_mode': '802.3ad', 'bond_slaves': 'ens1,ens2'},
                   '10.141.0.5')]
BOND_SELF_VLAN_BY_NAME = [({'interface': 'bond0', 'vlanid': '100', 'vlan_parent': 'bond0', 'bond_mode': '802.3ad',
                            'bond_slaves': 'ens1,ens2'}, '10.141.0.5')]
NIC_SELF_VLAN = [({'interface': 'eth1', 'vlanid': '200', 'macaddress': 'aa:bb:cc:dd:ee:01'}, '10.141.0.6')]
BARE_BOND_AND_VLAN = [({'interface': 'bond0', 'bond_mode': '802.3ad', 'bond_slaves': 'ens1,ens2'}, None),
                      ({'interface': 'vlan300', 'vlanid': '300', 'vlan_parent': 'bond0'}, '10.141.0.7')]


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS)
@pytest.mark.parametrize('interfaces,parent,vlan', [
    (BOND_SELF_VLAN, 'bond0', 'bond0.100'),
    (BOND_SELF_VLAN_BY_NAME, 'bond0', 'bond0.100'),
    (NIC_SELF_VLAN, 'eth1', 'eth1.200'),
])
def test_nm_writes_parent_and_vlan_as_two_profiles(db, distribution, osrelease, interfaces, parent, vlan):
    """The parent is a bare profile without DHCP and the vlan profile carries the address."""
    seed(db, distribution, osrelease, interfaces)
    files = rendered_files(distribution, osrelease)
    assert 'NetworkManager' in files[parent][0]
    bare, tagged = keyfile(files[parent][1]), keyfile(files[vlan][1])
    assert 'vlan' not in bare
    assert 'method=disabled' in bare['ipv4'] and not any(l.startswith('address') for l in bare['ipv4'])
    assert 'type=vlan' in tagged['connection']
    assert 'parent=${parent_name}' in tagged['vlan']
    assert any(l.startswith('address1=10.141.0.') for l in tagged['ipv4'])


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS)
def test_nm_bond_without_address_does_not_fall_back_to_dhcp(db, distribution, osrelease):
    """A keyfile without [ipv4] means DHCP to NetworkManager; a bare bond under a vlan must not ask."""
    seed(db, distribution, osrelease, BARE_BOND_AND_VLAN)
    files = rendered_files(distribution, osrelease)
    assert 'method=disabled' in keyfile(files['bond0'][1])['ipv4']
    assert any(l.startswith('address1=') for l in keyfile(files['vlan300'][1])['ipv4'])


@pytest.mark.parametrize('interfaces,parent,vlan_id', [
    (BOND_SELF_VLAN, 'bond0', 100),
    (BOND_SELF_VLAN_BY_NAME, 'bond0', 100),
    (NIC_SELF_VLAN, 'eth1', 200),
    (BARE_BOND_AND_VLAN, 'vlan300', 300),
])
def test_netplan_puts_the_address_on_the_vlan(db, interfaces, parent, vlan_id):
    """One file per Luna interface; the address belongs to the vlan device, never to its parent."""
    seed(db, 'ubuntu', '24', interfaces)
    files = rendered_files('ubuntu', '24')
    assert 'netplan' in files[parent][0]
    network = netplan(files[parent][1])['network']
    vlan = network['vlans']['vlan_IFACE']
    assert vlan['id'] == vlan_id
    assert vlan['addresses'] and vlan['addresses'][0].startswith('10.141.0.')
    for kind in ('bonds', 'ethernets'):
        for device in (network.get(kind) or {}).values():
            assert not (device or {}).get('addresses')
    assert all(not netplan(content) for name, (_, content) in files.items() if name and name not in
               {columns['interface'] for columns, _ in interfaces})


def test_netplan_bond_without_address_renders_an_empty_list(db):
    """netplan refuses an addresses key with nothing under it."""
    seed(db, 'ubuntu', '24', BARE_BOND_AND_VLAN)
    bond = netplan(rendered_files('ubuntu', '24')['bond0'][1])['network']['bonds']['IFACE']
    assert bond['addresses'] == []


BOOTIF_BOND = [({'interface': 'BOOTIF', 'bond_mode': '802.3ad', 'bond_slaves': 'BOOTIF,ens2'}, '10.141.0.8')]
BOOTIF_BOND_VLAN = [({'interface': 'BOOTIF', 'vlanid': '400', 'bond_mode': '802.3ad', 'bond_slaves': 'BOOTIF,ens2'},
                     '10.141.0.9')]


def shell_for(script, name):
    """The install script lines that set up one interface, ahead of its heredoc."""
    return script.split(f'######### {name} #########', 1)[0].rsplit('{%', 1)[-1].rsplit('fi\n', 1)[-1]


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS)
def test_nm_bootif_in_a_bond_is_left_as_it_was(db, distribution, osrelease):
    """No vlan id: the renamed bond keeps the address and nothing is split off."""
    seed(db, distribution, osrelease, BOOTIF_BOND)
    files = rendered_files(distribution, osrelease)
    assert not [name for name in files if name.startswith('bond0.')]
    bond = keyfile(files['bond0'][1])
    assert 'type=bond' in bond['connection'] and 'vlan' not in bond
    assert any(l.startswith('address1=10.141.0.8/') for l in bond['ipv4'])
    assert 'master=bond0' in keyfile(files['BOOTIF'][1])['connection']


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS)
def test_nm_bootif_in_a_bond_with_a_vlan_id(db, distribution, osrelease):
    """
    The provisioning bond is renamed before the split, so the vlan hangs off that
    name, and it keeps the defaults the boot interface is given when it has none.
    """
    seed(db, distribution, osrelease, BOOTIF_BOND_VLAN)
    files = rendered_files(distribution, osrelease)
    bond, tagged = keyfile(files['bond0'][1]), keyfile(files['bond0.400'][1])
    assert 'method=disabled' in bond['ipv4'] and 'vlan' not in bond
    assert 'type=vlan' in tagged['connection'] and 'id=400' in tagged['vlan']
    assert any(l.startswith('address1=10.141.0.9/') for l in tagged['ipv4'])
    assert any(l.startswith('route1=0.0.0.0/0,') for l in tagged['ipv4'])
    assert 'parent_name=bond0' in shell_for(files[''][1], 'bond0.400')
    assert 'master=bond0' in keyfile(files['BOOTIF'][1])['connection']


@pytest.mark.parametrize('interfaces,has_vlan', [(BOOTIF_BOND, False), (BOOTIF_BOND_VLAN, True)])
def test_netplan_bootif_in_a_bond(db, interfaces, has_vlan):
    """The boot interface stays a member of the bond; with a vlan id the address moves to the vlan."""
    seed(db, 'ubuntu', '24', interfaces)
    network = netplan(rendered_files('ubuntu', '24')['bond0'][1])['network']
    assert network['bonds']['IFACE']['interfaces'] == ['ens1', 'ens2']
    if has_vlan:
        assert network['vlans']['vlan_IFACE']['addresses'][0].startswith('10.141.0.9/')
        assert not network['bonds']['IFACE'].get('addresses')
    else:
        assert 'vlans' not in network
        assert network['bonds']['IFACE']['addresses'][0].startswith('10.141.0.8/')


UNTAGGED_AND_TAGGED = {
    'bond': [({'interface': 'prime01', 'bond_mode': '802.3ad', 'bond_slaves': 'ens1,ens2'}, '10.141.0.10'),
             ({'interface': 'second02', 'vlanid': '500', 'vlan_parent': 'prime01'}, '10.141.0.11')],
    'nic': [({'interface': 'prime01'}, '10.141.0.10'),
            ({'interface': 'second02', 'vlanid': '500', 'vlan_parent': 'prime01'}, '10.141.0.11')],
}


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS)
@pytest.mark.parametrize('kind', ['bond', 'nic'])
def test_nm_untagged_parent_and_tagged_child_both_carry_their_address(db, distribution, osrelease, kind):
    """A vlan with a parent of its own leaves that parent's untagged address where it is."""
    seed(db, distribution, osrelease, UNTAGGED_AND_TAGGED[kind])
    files = rendered_files(distribution, osrelease)
    assert not [name for name in files if '.' in name]
    parent, tagged = keyfile(files['prime01'][1]), keyfile(files['second02'][1])
    assert 'vlan' not in parent
    assert any(l.startswith('address1=10.141.0.10/') for l in parent['ipv4'])
    assert 'type=vlan' in tagged['connection'] and 'id=500' in tagged['vlan']
    assert any(l.startswith('address1=10.141.0.11/') for l in tagged['ipv4'])
    assert 'parent_name=prime01' in shell_for(files[''][1], 'second02')


@pytest.mark.parametrize('kind', ['bond', 'nic'])
def test_netplan_untagged_parent_and_tagged_child_both_carry_their_address(db, kind):
    """The parent keeps its address untagged; the child's address sits on its vlan device."""
    seed(db, 'ubuntu', '24', UNTAGGED_AND_TAGGED[kind])
    files = rendered_files('ubuntu', '24')
    parent = netplan(files['prime01'][1])['network']
    stanza = parent['bonds' if kind == 'bond' else 'ethernets']['IFACE']
    assert stanza['addresses'][0].startswith('10.141.0.10/') and 'vlans' not in parent
    child = netplan(files['second02'][1])['network']
    assert child['vlans']['vlan_IFACE']['link'] == 'PARENT'
    assert child['vlans']['vlan_IFACE']['addresses'][0].startswith('10.141.0.11/')


TWO_NETWORKS = {
    'bond': [({'interface': 'prime01', 'bond_mode': '802.3ad', 'bond_slaves': 'ens1,ens2'}, '10.141.0.1'),
             ({'interface': 'second02', 'vlanid': '500', 'vlan_parent': 'prime01'}, '10.142.0.1')],
    'nic': [({'interface': 'prime01'}, '10.141.0.1'),
            ({'interface': 'second02', 'vlanid': '500', 'vlan_parent': 'prime01'}, '10.142.0.1')],
}


@pytest.mark.parametrize('distribution,osrelease', NM_DISTRIBUTIONS + [('ubuntu', '24')])
@pytest.mark.parametrize('kind', ['bond', 'nic'])
def test_untagged_and_tagged_on_two_networks(db, distribution, osrelease, kind):
    """Each interface keeps its own network: the parent on cluster untagged, the vlan on cluster2."""
    seed(db, distribution, osrelease, TWO_NETWORKS[kind])
    files = rendered_files(distribution, osrelease)
    if distribution == 'ubuntu':
        parent = netplan(files['prime01'][1])['network']
        assert parent['bonds' if kind == 'bond' else 'ethernets']['IFACE']['addresses'] == ['10.141.0.1/16']
        assert 'vlans' not in parent
        vlan = netplan(files['second02'][1])['network']['vlans']['vlan_IFACE']
        assert vlan['id'] == 500 and vlan['link'] == 'PARENT' and vlan['addresses'] == ['10.142.0.1/16']
    else:
        parent, tagged = keyfile(files['prime01'][1]), keyfile(files['second02'][1])
        assert 'address1=10.141.0.1/16' in parent['ipv4'] and 'vlan' not in parent
        assert 'address1=10.142.0.1/16' in tagged['ipv4'] and 'id=500' in tagged['vlan']
        assert 'parent_name=prime01' in shell_for(files[''][1], 'second02')
