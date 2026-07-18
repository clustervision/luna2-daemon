#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for the Config rendering / networking methods.

These exercise the real code paths against a temporary SQLite database seeded
with a minimal but complete cluster (cluster, controller, network, group, node,
interface, ipaddress). dhcp_overwrite and dns_configure render the daemon's own
Jinja templates and write config files into a temp directory; we assert on the
rendered content.

System side effects are neutralised: the dhcpd/named syntax-check subprocess is
stubbed to succeed, and shutil.copyfile / os.makedirs are no-ops, so nothing is
written to /etc or /var/named. The temp-directory outputs are produced
regardless, and are what we assert on.
"""

import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "daemon", "templates"))

# Fixed seed values reused across assertions.
NETWORK = "cluster"
NETWORK_CIDR = "10.141.0.0"
NETMASK = "255.255.0.0"
RANGE_BEGIN = "10.141.10.1"
RANGE_END = "10.141.10.254"
CONTROLLER_IP = "10.141.255.254"
NODE_IP = "10.141.0.5"
NODE_MAC = "aa:bb:cc:dd:ee:ff"


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


@pytest.fixture
def seeded(sqlite_db):
    """Seed a minimal, self-consistent cluster into the temp database."""
    from utils.database import Database

    _insert("cluster", name="mycluster", nameserver_ip="10.141.0.1", ntp_server="10.141.0.1")
    _insert("network", name=NETWORK, network=NETWORK_CIDR, subnet=NETMASK, dhcp=1,
            dhcp_range_begin=RANGE_BEGIN, dhcp_range_end=RANGE_END,
            nameserver_ip="10.141.0.1", ntp_server="10.141.0.1", zone=NETWORK)
    netid = Database().get_record(table="network", where=f'name="{NETWORK}"')[0]["id"]

    _insert("controller", hostname="controller", beacon=1, clusterid=1)
    ctrlid = Database().get_record(table="controller", where='hostname="controller"')[0]["id"]
    _insert("ipaddress", ipaddress=CONTROLLER_IP, tableref="controller",
            tablerefid=ctrlid, networkid=netid)

    _insert("group", name="compute")
    gid = Database().get_record(table="group", where='name="compute"')[0]["id"]
    _insert("node", name="node001", groupid=gid)
    nid = Database().get_record(table="node", where='name="node001"')[0]["id"]
    _insert("nodeinterface", nodeid=nid, interface="BOOTIF", macaddress=NODE_MAC)
    ifid = Database().get_record(table="nodeinterface", where=f"nodeid={nid}")[0]["id"]
    _insert("ipaddress", ipaddress=NODE_IP, tableref="nodeinterface",
            tablerefid=ifid, networkid=netid)
    return {"netid": netid}


@pytest.fixture
def config_env(sqlite_db, constant, tmp_path, monkeypatch):
    """
    Wire Config at the temp database + temp output dir, and neutralise all
    system-touching side effects. Yields the output directory path.
    """
    import utils.config as cfgmod

    saved = {section: dict(constant[section]) for section in ("API", "TEMPLATES", "DHCP")}
    constant["TEMPLATES"].update({"TEMPLATE_FILES": TEMPLATES_DIR, "TMP_DIRECTORY": str(tmp_path)})
    constant["API"].update({"PROTOCOL": "http", "VERIFY_CERTIFICATE": "no",
                            "ENDPOINT": "controller:7050"})
    constant["DHCP"].update({"OMAPIKEY": None, "TEST": "/bin/true", "TEST6": "/bin/true",
                             "CONFIG_PATH": str(tmp_path / "dhcpd.conf.live"),
                             "CONFIG6_PATH": str(tmp_path / "dhcpd6.conf.live")})

    class _Proc:
        returncode = 0

    monkeypatch.setattr(cfgmod.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(cfgmod.shutil, "copyfile", lambda *a, **k: None)
    monkeypatch.setattr(cfgmod.os, "makedirs", lambda *a, **k: None)

    yield str(tmp_path)

    for section, original in saved.items():
        constant[section].clear()
        constant[section].update(original)


@pytest.mark.regression
def test_dhcp_overwrite_renders_subnet_and_host(config_env, seeded):
    from utils.config import Config

    assert Config().dhcp_overwrite() is True

    dhcpd_conf = os.path.join(config_env, "dhcpd.conf")
    assert os.path.exists(dhcpd_conf)
    content = open(dhcpd_conf, encoding="utf-8").read()

    # subnet block for the seeded network
    assert f"subnet {NETWORK_CIDR} netmask {NETMASK}" in content
    assert f"range {RANGE_BEGIN} {RANGE_END}" in content
    assert f"next-server {CONTROLLER_IP}" in content
    # host reservation for the seeded node
    assert "host node001.cluster" in content
    assert f"hardware ethernet {NODE_MAC}" in content
    assert f"fixed-address {NODE_IP}" in content


@pytest.mark.regression
def test_dhcp_kea_renders_relay_on_shared_network(config_env, seeded, constant):
    """TRIX-1921: a shared network carrying dhcp_relay renders a Kea 'relay' ip-addresses block."""
    from utils.config import Config

    _insert("network", name="remote", network="10.150.0.0", subnet="255.255.0.0", dhcp=1,
            dhcp_range_begin="10.150.10.1", dhcp_range_end="10.150.10.254",
            nameserver_ip="10.141.0.1", ntp_server="10.141.0.1", zone="remote",
            shared=NETWORK, dhcp_relay="10.150.0.1,10.150.0.2")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert '"relay"' in content
    assert '"10.150.0.1"' in content and '"10.150.0.2"' in content


@pytest.mark.regression
def test_dhcp_kea_no_relay_block_when_unset(config_env, seeded, constant):
    """Without dhcp_relay, the Kea render must not emit a subnet 'relay' block."""
    from utils.config import Config

    _insert("network", name="remote", network="10.150.0.0", subnet="255.255.0.0", dhcp=1,
            dhcp_range_begin="10.150.10.1", dhcp_range_end="10.150.10.254",
            nameserver_ip="10.141.0.1", ntp_server="10.141.0.1", zone="remote",
            shared=NETWORK)
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert '"relay"' not in content


@pytest.mark.regression
def test_dhcp_kea_link_selection_renders_shared_network(config_env, seeded, constant):
    """TRIX-1921: a network with dhcp_link_subnet is lifted into a Kea shared-networks block -- a
    pool-less anchor on the link prefix (authoritative:false) beside the boot subnet, with the pool
    fenced only on the option-82.5 path."""
    from utils.config import Config

    _insert("network", name="edge", network="10.160.0.0", subnet="255.255.0.0", dhcp=1,
            dhcp_range_begin="10.160.10.1", dhcp_range_end="10.160.10.254",
            nameserver_ip="10.141.0.1", ntp_server="10.141.0.1", zone="edge",
            shared=NETWORK, dhcp_relay="10.160.0.1", dhcp_link_subnet="10.170.35.0/24")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert '"shared-networks"' in content
    assert '"edge-linksel"' in content
    assert '"subnet": "10.170.35.0/24"' in content        # the pool-less anchor
    assert '"authoritative": false' in content            # suppress, not NAK, for foreign clients
    assert '"edge-boot-class"' in content                 # the boot-pool fence
    assert "relay4[5].exists" in content                  # fence gates only the 82.5 path
    assert '"subnet": "10.160.0.0/' in content            # the boot subnet moved into the block
    # the boot network no longer appears as a plain top-level subnet4 entry (it is inside the block)
    assert content.index('"shared-networks"') < content.index('"subnet": "10.160.0.0/')


@pytest.mark.regression
def test_dhcp_kea_ntp_v4_emitted_only_for_ipv4(config_env, seeded, constant):
    """TRIX-1939: dhcp4 ntp-servers (option 42) is emitted only for an IPv4 ntp_server. A network
    whose ntp_server is an IPv6 address or a host name must not emit it -- that value fails the
    whole subnet4 element in kea."""
    from utils.config import Config

    # seeded 'cluster' has an IPv4 ntp_server (emitted). Add one IPv6-ntp and one host-name-ntp net.
    _insert("network", name="n6", network="10.161.0.0", subnet="255.255.0.0", dhcp=1,
            dhcp_range_begin="10.161.10.1", dhcp_range_end="10.161.10.254",
            nameserver_ip="10.141.0.1", ntp_server="2001:db8::9", zone="n6")
    _insert("network", name="nf", network="10.162.0.0", subnet="255.255.0.0", dhcp=1,
            dhcp_range_begin="10.162.10.1", dhcp_range_end="10.162.10.254",
            nameserver_ip="10.141.0.1", ntp_server="ntp.example.org", zone="nf")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # three DHCP networks, three ntp_server values, but only the IPv4 one may emit ntp-servers
    assert content.count('"ntp-servers"') == 1


@pytest.mark.regression
def test_dhcp_kea_ntp_v6_srv_addr_and_srv_fqdn(config_env, seeded, constant):
    """TRIX-1939: dhcp6 carries an IPv6 ntp_server as the srv-addr sub-option and a host name as
    the srv-fqdn sub-option of option 56 (RFC 5908); an IPv4 value is dropped."""
    from utils.config import Config

    _insert("network", name="v6addr", network="10.163.0.0", subnet="255.255.0.0",
            network_ipv6="2001:db8:163::", subnet_ipv6="64", dhcp=1,
            dhcp_range_begin_ipv6="2001:db8:163::10", dhcp_range_end_ipv6="2001:db8:163::ff",
            nameserver_ip="10.141.0.1", ntp_server="2001:db8::9", zone="v6addr")
    _insert("network", name="v6fqdn", network="10.164.0.0", subnet="255.255.0.0",
            network_ipv6="2001:db8:164::", subnet_ipv6="64", dhcp=1,
            dhcp_range_begin_ipv6="2001:db8:164::10", dhcp_range_end_ipv6="2001:db8:164::ff",
            nameserver_ip="10.141.0.1", ntp_server="ntp.example.org", zone="v6fqdn")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["TEMPLATE6"] = "templ_kea-dhcp6.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd6.conf"), encoding="utf-8").read()

    assert '"space": "ntp-server"' in content                 # the sub-option definitions exist
    assert '"name": "ntp-server-srv-addr"' in content         # IPv6 address -> srv-addr
    assert '"name": "ntp-server-srv-fqdn"' in content         # host name -> srv-fqdn
    # the old plain-address form (rejected by kea 3.0) must be gone
    assert '"name": "ntp-server", "csv-format"' not in content


@pytest.mark.regression
def test_dns_configure_renders_zone_and_named_conf(config_env, seeded):
    from utils.config import Config

    assert Config().dns_configure() is True

    assert os.path.exists(os.path.join(config_env, "named.conf"))
    assert os.path.exists(os.path.join(config_env, "named.luna.zones"))

    zone_file = os.path.join(config_env, f"{NETWORK}.luna.zone")
    assert os.path.exists(zone_file)
    zone = open(zone_file, encoding="utf-8").read()

    # A records for controller and node (serial is a timestamp -> not asserted)
    assert "SOA" in zone
    assert "controller.cluster." in zone
    assert f"node001                    IN A {NODE_IP}" in zone
    assert f"controller                    IN A {CONTROLLER_IP}" in zone


@pytest.mark.regression
def test_get_dhcp_range_ips_from_network(config_env, seeded):
    from utils.config import Config

    ips = Config().get_dhcp_range_ips_from_network(NETWORK)
    assert len(ips) == 254
    assert ips[0] == RANGE_BEGIN
    assert ips[-1] == RANGE_END


@pytest.mark.regression
def test_get_all_occupied_ips_from_network(config_env, seeded):
    from utils.config import Config

    ips = Config().get_all_occupied_ips_from_network(NETWORK)
    # 254 range IPs + the controller and node addresses assigned in this network
    assert len(ips) == 256
    assert NODE_IP in ips
    assert CONTROLLER_IP in ips
