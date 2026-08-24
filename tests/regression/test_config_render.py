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
# luna stores the prefix length in network.subnet; the dotted form is what the ISC
# template derives from it, and what kea refuses ("prefix length is not an integer").
PREFIX = "16"
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
    _insert("network", name=NETWORK, network=NETWORK_CIDR, subnet=PREFIX, dhcp=1,
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


def _kea(content):
    """Parse a rendered kea config. The templates emit shell-style comments, which kea accepts and
    json does not."""
    import json
    import re
    return json.loads("\n".join(re.sub(r"#.*$", "", line) for line in content.splitlines()))


def _kea_accepts(content, family="4"):
    """Run the render through kea's own parser where one is installed.

    kea is the authority on its own syntax and a regex is an opinion: the plural class spelling,
    a duplicate subnet prefix and a forward class reference all read fine and are all refused. The
    check is skipped, never faked, when no binary is present."""
    import shutil
    import subprocess
    import tempfile
    binary = shutil.which(f"kea-dhcp{family}") or f"/usr/sbin/kea-dhcp{family}"
    if not os.path.exists(binary):
        pytest.skip(f"kea-dhcp{family} not installed")
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as handle:
        handle.write(content)
        path = handle.name
    try:
        done = subprocess.run([binary, "-t", path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    assert done.returncode == 0, f"kea-dhcp{family} refused the render:\n{done.stdout}{done.stderr}"

def _assert_classes_resolve(family):
    """Every class named anywhere must be defined, and defined before it is named.

    kea reads an unknown client-class as a name that never matches: the subnet or pool carrying it
    silently drops out of selection, with nothing reported at parse time or at run time. A member()
    reference to a class defined later in the list is refused outright. Both have shipped."""
    import re
    defined = []
    for entry in family.get("client-classes", []):
        for named in re.findall(r"member\('([^']+)'\)", entry.get("test", "")):
            assert named in defined, (
                f"class {entry['name']!r} names {named!r}, which is defined later or not at all; "
                f"kea refuses a forward reference and the whole configuration with it")
        defined.append(entry["name"])
    def _walk(subnets):
        for subnet in subnets:
            names = [subnet["client-class"]] if "client-class" in subnet else []
            names += [pool["client-class"] for pool in subnet.get("pools", []) if "client-class" in pool]
            for name in names:
                assert name in defined, (
                    f"subnet {subnet['subnet']} names class {name!r}, which is never defined; kea "
                    f"takes it out of selection and says nothing")
                assert not re.search(r"[ ()']", name), (
                    f"subnet {subnet['subnet']} carries the expression {name!r} where kea expects a "
                    f"class name; it matches nothing and the subnet is never selected")
    _walk(family.get("subnet4", []) + family.get("subnet6", []))
    for block in family.get("shared-networks", []):
        _walk(block.get("subnet4", []) + block.get("subnet6", []))

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
    """TRIX-1921/-: a network with dhcp_link_subnet gets a pool-less anchor on the link prefix
    beside its boot subnet, with the pool fenced on the option-82.5 path. The anchor belongs to the
    whole link, so it joins the network's shared group -- a group sibling left outside the block is
    unreachable from the anchor, and a node reserved there is served from the wrong network."""
    from utils.config import Config

    _insert("network", name="edge", network="10.160.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.160.10.1", dhcp_range_end="10.160.10.254",
            nameserver_ip="10.141.0.1", ntp_server="10.141.0.1", zone="edge",
            shared=NETWORK, dhcp_relay="10.160.0.1", dhcp_link_subnet="10.170.35.0/24")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    blocks = {block["name"]: block for block in parsed["Dhcp4"]["shared-networks"]}

    assert list(blocks) == ["cluster-edge"], (
        f"expected the anchor to join the shared group, got {list(blocks)}")
    subnets = {subnet["subnet"]: subnet for subnet in blocks["cluster-edge"]["subnet4"]}

    # the pool-less anchor on the link prefix: suppress, rather than NAK, for foreign clients
    assert subnets["10.170.35.0/24"]["pools"] == []
    assert subnets["10.170.35.0/24"]["authoritative"] is False
    # both the anchor-carrying network and its group sibling are inside the same block, so kea can
    # reach either from the anchor and finds a reservation wherever it lives
    assert "10.160.0.0/16" in subnets and "10.141.0.0/16" in subnets
    assert any(host["ip-address"] == NODE_IP
               for host in subnets["10.141.0.0/16"].get("reservations", []))
    # every pool in an anchored block is fenced, or the foreign devices on that link take addresses
    # from a cluster pool -- which is what the anchor's empty pool exists to prevent
    for prefix in ("10.160.0.0/16", "10.141.0.0/16"):
        for pool in subnets[prefix]["pools"]:
            assert "client-class" in pool, f"unfenced pool in an anchored block: {prefix}"
    assert "relay4[5].exists" in content
    _kea_accepts(content)

    # nothing may reference a class that is not defined, and not before it is defined: kea reads an
    # unknown name as a class that never matches and silently drops the subnet out of selection
    _assert_classes_resolve(parsed["Dhcp4"])


@pytest.mark.regression
def test_dhcp_kea_shared_group_is_one_shared_network(config_env, seeded, constant):
    """A luna shared group is one kea shared-networks block. Flattened into subnet4 it is not a
    group at all: kea selects one subnet and can only move to a sibling inside a shared network, so
    two networks behind one relay resolve by config order and a reservation in the other is never
    found."""
    from utils.config import Config

    _insert("network", name="ipmi", network="10.148.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.148.10.1", dhcp_range_end="10.148.10.254",
            nameserver_ip="10.141.0.1", zone="ipmi", shared=NETWORK)
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    _kea_accepts(content)

    assert parsed["Dhcp4"].get("subnet4") == [], "a grouped network must not also be a flat subnet"
    block = parsed["Dhcp4"]["shared-networks"][0]
    assert {subnet["subnet"] for subnet in block["subnet4"]} == {"10.141.0.0/16", "10.148.0.0/16"}
    # the allow/deny policy ISC writes per pool: it belongs on the pool, and it is a class NAME
    for subnet in block["subnet4"]:
        for pool in subnet["pools"]:
            assert pool["client-class"] in {c["name"] for c in parsed["Dhcp4"]["client-classes"]}
    _assert_classes_resolve(parsed["Dhcp4"])


@pytest.mark.regression
def test_dhcp_kea_honours_link_selection_by_default(config_env, seeded, constant):
    """Off by default, and it must stay that way. Where a relay uses option 82 sub-option 5 to tell
    apart several links behind one giaddr, the sub-option is the only thing that identifies the
    link: ignoring it hands the client a lease from a sibling subnet, with the wrong gateway and no
    error anywhere. Measured on kea 3.0.3 -- two links, one giaddr, second client moved subnet."""
    from utils.config import Config

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    parsed = _kea(open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read())
    assert "compatibility" not in parsed["Dhcp4"]


@pytest.mark.regression
def test_dhcp_kea_ignore_link_selection_is_opt_in(config_env, seeded, constant):
    """Turned on, kea selects on giaddr -- which luna knows from dhcp_relay -- so a relay naming a
    prefix luna does not manage no longer takes every client it forwards out of subnet selection,
    and nothing luna does not own appears in the config."""
    from utils.config import Config

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["IGNORE_LINK_SELECTION"] = "yes"
    assert Config().dhcp_overwrite() is True
    parsed = _kea(open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read())
    assert parsed["Dhcp4"]["compatibility"]["ignore-rai-link-selection"] is True


@pytest.mark.regression
def test_dhcp_kea_anchor_beats_the_ignore_setting(config_env, seeded, constant):
    """The two contradict: an anchor exists because the sub-option carries information we want. The
    anchor is the more specific statement and wins, and the render says so rather than quietly
    dropping one of them."""
    from utils.config import Config

    _insert("network", name="edge", network="10.160.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.160.10.1", dhcp_range_end="10.160.10.254",
            nameserver_ip="10.141.0.1", zone="edge",
            dhcp_relay="10.160.0.1", dhcp_link_subnet="10.170.35.0/24")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["IGNORE_LINK_SELECTION"] = "yes"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    assert "compatibility" not in parsed["Dhcp4"]
    assert '"subnet": "10.170.35.0/24"' in content


@pytest.mark.regression
def test_dhcp_kea_relayed_pool_takes_no_policy_class(config_env, seeded, constant):
    """A relayed member is picked out by its relay, so its pool must carry no policy class.

    Every member class in a group holds the same udhcp test, so classing a relayed pool refuses
    that network's own PXE clients -- which then fall through to the carrier's pool and boot on the
    wrong subnet, with the wrong gateway. Measured on kea 3.0.3: an unknown node arriving over the
    relay was offered the carrier's address instead of its own network's."""
    from utils.config import Config

    _insert("network", name="remote", network="10.150.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.150.10.1", dhcp_range_end="10.150.10.254",
            nameserver_ip="10.141.0.1", zone="remote", shared=NETWORK, dhcp_relay="10.150.0.1")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    _kea_accepts(content)
    subnets = {s["subnet"]: s for s in parsed["Dhcp4"]["shared-networks"][0]["subnet4"]}
    for pool in subnets["10.150.0.0/16"]["pools"]:
        assert "client-class" not in pool, (
            "a relayed member's pool carries a policy class; its own PXE clients are refused it "
            "and fall through to the carrier's pool")
    # the network on the wire still gets one -- that is what tells host from BMC
    for pool in subnets["10.141.0.0/16"]["pools"]:
        assert "client-class" in pool
    _assert_classes_resolve(parsed["Dhcp4"])


@pytest.mark.regression
def test_dhcp_kea_anchor_keeps_its_own_block_when_the_group_spans_links(config_env, seeded, constant):
    """An anchor joins its shared group only where the group really is one link.

    luna's 'shared' means one wire for a host and its BMC, and is only the precondition dhcp_relay
    insists on for a relayed network -- so a group can hold relayed networks on quite separate
    links. Merged there, the anchor is reachable from every relayed member and selection lands on
    whichever the render put first: measured, a link-selection client was served the other relayed
    network's pool. Relays in common are the evidence that the link is shared."""
    from utils.config import Config

    _insert("network", name="remote", network="10.150.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.150.10.1", dhcp_range_end="10.150.10.254",
            nameserver_ip="10.141.0.1", zone="remote", shared=NETWORK, dhcp_relay="10.150.0.1")
    _insert("network", name="edge", network="10.160.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.160.10.1", dhcp_range_end="10.160.10.254",
            nameserver_ip="10.141.0.1", zone="edge", shared=NETWORK,
            dhcp_relay="10.160.0.1", dhcp_link_subnet="10.170.35.0/24")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    _kea_accepts(content)
    blocks = {b["name"]: [s["subnet"] for s in b["subnet4"]] for b in parsed["Dhcp4"]["shared-networks"]}
    assert "edge-linksel" in blocks, (
        f"the anchor was merged into a group spanning two relayed links: {list(blocks)}")
    assert set(blocks["edge-linksel"]) == {"10.170.35.0/24", "10.160.0.0/16"}
    # ...and it is not also a member of the group block, which would render it twice
    other = [name for name in blocks if name != "edge-linksel"]
    assert "10.160.0.0/16" not in blocks[other[0]]
    _assert_classes_resolve(parsed["Dhcp4"])


@pytest.mark.regression
def test_dhcp_kea_anchor_joins_a_group_that_shares_the_relay(config_env, seeded, constant):
    """The other half of the same rule: relays in common mean one link, so the anchor merges and
    the sibling reachable over that relay is inside the block with it."""
    from utils.config import Config

    _insert("network", name="inband", network="10.145.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.145.10.1", dhcp_range_end="10.145.10.254",
            nameserver_ip="10.141.0.1", zone="inband", shared=NETWORK,
            dhcp_relay="10.160.0.1,10.160.0.2")
    from utils.database import Database
    Database().update("network", [
        {"column": "dhcp_relay", "value": "10.160.0.1,10.160.0.2"},
        {"column": "dhcp_link_subnet", "value": "10.170.35.0/24"},
    ], where=[{"column": "name", "value": NETWORK}])
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    _kea_accepts(content)
    assert len(parsed["Dhcp4"]["shared-networks"]) == 1
    block = parsed["Dhcp4"]["shared-networks"][0]
    assert {s["subnet"] for s in block["subnet4"]} == {
        "10.170.35.0/24", "10.141.0.0/16", "10.145.0.0/16"}
    _assert_classes_resolve(parsed["Dhcp4"])


def _dualstack(database, network):
    """Give the seeded network a v6 side, and the controller an address in it."""
    database.update("network", [
        {"column": "network_ipv6", "value": "2001:db8:141::"},
        {"column": "subnet_ipv6", "value": "64"},
        {"column": "dhcp_range_begin_ipv6", "value": "2001:db8:141::10"},
        {"column": "dhcp_range_end_ipv6", "value": "2001:db8:141::ff"},
    ], where=[{"column": "name", "value": network}])
    ctrl = database.get_record(table="controller", where='hostname="controller"')[0]["id"]
    database.update("ipaddress", [{"column": "ipaddress_ipv6", "value": "2001:db8:141::fe"}],
                    where=[{"column": "tablerefid", "value": ctrl},
                           {"column": "tableref", "value": "controller"}])


@pytest.mark.regression
def test_dhcp_kea6_plain_subnet_is_a_config_kea_accepts(config_env, seeded, constant):
    """The simplest DHCPv6 case there is: one plain network, and kea must load it.

    The per-network arch classes carry the bootfile-url, and the ipxe_kernel classes name them with
    member(). Emitted after them, the reference is forward and kea refuses the whole file -- 'Not
    defined client class arch-x86-<network>'. Both families install together, so that takes the
    DHCPv4 configuration down with it. Measured on kea 3.0.3."""
    from utils.config import Config
    from utils.database import Database

    _dualstack(Database(), NETWORK)
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["TEMPLATE6"] = "templ_kea-dhcp6.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd6.conf"), encoding="utf-8").read()
    _kea_accepts(content, "6")
    _assert_classes_resolve(_kea(content)["Dhcp6"])


@pytest.mark.regression
def test_dhcp_kea6_link_selection_network_gets_its_boot_classes(config_env, seeded, constant):
    """DHCPv6 carries the boot file in a class built per network, so a link-selection network needs
    its own as much as any other. Without them a node there cannot do first-stage PXE and its
    ipxe_kernel choice has nothing to act on -- the alternative kernel is simply unreachable."""
    from utils.config import Config
    from utils.database import Database

    _dualstack(Database(), NETWORK)
    Database().update("network", [
        {"column": "dhcp_relay", "value": "10.160.0.1,2001:db8:160::1"},
        {"column": "dhcp_link_subnet", "value": "10.170.35.0/24,2001:db8:170::/64"},
        {"column": "shared", "value": "ipmi"},
    ], where=[{"column": "name", "value": NETWORK}])
    _insert("network", name="ipmi", network="10.148.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.148.10.1", dhcp_range_end="10.148.10.254",
            network_ipv6="2001:db8:148::", subnet_ipv6="64",
            dhcp_range_begin_ipv6="2001:db8:148::10", dhcp_range_end_ipv6="2001:db8:148::ff",
            nameserver_ip="10.141.0.1", zone="ipmi", dhcp_relay="10.150.0.1")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["TEMPLATE6"] = "templ_kea-dhcp6.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd6.conf"), encoding="utf-8").read()
    parsed = _kea(content)
    _kea_accepts(content, "6")
    names = {entry["name"] for entry in parsed["Dhcp6"]["client-classes"]}
    # the group does not share a link, so the anchor keeps its own block - and that block's network
    # still needs the classes that make a boot file reachable
    for wanted in (f"arch-x86-{NETWORK}", f"arch-arm64-{NETWORK}",
                   f"ipxe-kernel-alternative-x86-{NETWORK}",
                   f"ipxe-kernel-default-x86-{NETWORK}"):
        assert wanted in names, f"a link-selection network has no {wanted}"
    _assert_classes_resolve(parsed["Dhcp6"])


def _alt_kernel_node(name, mac, netid, ip=None, ip6=None):
    """A node selecting the ALTERNATIVE iPXE kernel, with a single-family boot interface. (A node
    interface carrying both families renders only its v6 reservation -- if/elif in dhcp_config -- so
    each family is exercised on its own interface.)"""
    from utils.database import Database
    _insert("group", name=f"{name}grp")
    gid = Database().get_record(table="group", where=f'name="{name}grp"')[0]["id"]
    _insert("node", name=name, groupid=gid, ipxe_kernel="alternative")
    nid = Database().get_record(table="node", where=f'name="{name}"')[0]["id"]
    _insert("nodeinterface", nodeid=nid, interface="BOOTIF", macaddress=mac)
    ifid = Database().get_record(table="nodeinterface", where=f"nodeid={nid}")[0]["id"]
    _insert("ipaddress", ipaddress=ip, ipaddress_ipv6=ip6,
            tableref="nodeinterface", tablerefid=ifid, networkid=netid)


ALT_CLASS = '"client-classes": [ "ipxe-kernel-alternative" ]'


@pytest.mark.regression
def test_alternative_ipxe_kernel_across_network_topologies(config_env, constant):
    """TRIX-1921: the alternative iPXE kernel (luna_snponly.efi) is selected per node by the
    ipxe-kernel-alternative client-class on that node's DHCP reservation. That class must survive in
    ALL THREE boot topologies -- a regular network, a relayed (dhcp_relay) shared network, and a
    relay + option-82.5 link-selection (dhcp_link_subnet) network -- in both address families.

    The link-selection column of this matrix was the regression: a link-sel network lives only in
    the link-sel render bucket, but the two node reservation-nextserver calls omitted that bucket
    (while the switch calls passed it), so a link-sel node's reservation lost its next-server and its
    ipxe_kernel class and silently booted the DEFAULT luna_ipxe.efi -- with a config kea still
    accepts. The matrix pins every topology x family so the class cannot silently drop from any one
    of them; the switch reservation in the link-sel net is the device-type parity anchor."""
    from utils.config import Config
    from utils.database import Database

    _insert("cluster", name="mycluster", nameserver_ip="10.141.0.1", ntp_server="10.141.0.1")
    # (1) REGULAR: the boot network itself, controller present -> serves next-server directly.
    _insert("network", name="cluster", network="10.141.0.0", subnet="16",
            network_ipv6="2001:db8:141::", subnet_ipv6="64", dhcp=1,
            dhcp_range_begin="10.141.10.1", dhcp_range_end="10.141.10.254",
            dhcp_range_begin_ipv6="2001:db8:141::10", dhcp_range_end_ipv6="2001:db8:141::ff",
            nameserver_ip="10.141.0.1", nameserver_ip_ipv6="2001:db8:141::1",
            ntp_server="10.141.0.1", zone="cluster")
    _insert("controller", hostname="controller", beacon=1, clusterid=1)
    ctrlid = Database().get_record(table="controller", where='hostname="controller"')[0]["id"]
    clnet = Database().get_record(table="network", where='name="cluster"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.255.254", ipaddress_ipv6="2001:db8:141::fe",
            tableref="controller", tablerefid=ctrlid, networkid=clnet)
    _alt_kernel_node("regn4", "aa:bb:cc:00:00:a1", clnet, ip="10.141.0.50")
    _alt_kernel_node("regn6", "aa:bb:cc:00:00:a6", clnet, ip6="2001:db8:141::50")

    # (2) RELAY: shared + dhcp_relay. gateway is the off-link route that lets next-server be served.
    _insert("network", name="relayed", network="10.150.0.0", subnet="16",
            network_ipv6="2001:db8:150::", subnet_ipv6="64", dhcp=1,
            dhcp_range_begin="10.150.10.1", dhcp_range_end="10.150.10.254", gateway="10.150.0.1",
            dhcp_range_begin_ipv6="2001:db8:150::10", dhcp_range_end_ipv6="2001:db8:150::ff",
            gateway_ipv6="2001:db8:150::1", nameserver_ip="10.141.0.1",
            nameserver_ip_ipv6="2001:db8:150::1", ntp_server="10.141.0.1", zone="relayed",
            shared=NETWORK, dhcp_relay="10.150.0.1,2001:db8:150::1")
    rid = Database().get_record(table="network", where='name="relayed"')[0]["id"]
    _alt_kernel_node("relayn4", "aa:bb:cc:00:00:b1", rid, ip="10.150.10.50")
    _alt_kernel_node("relayn6", "aa:bb:cc:00:00:b6", rid, ip6="2001:db8:150::50")

    # (3) RELAY + LINK (82.5): shared + dhcp_relay + dhcp_link_subnet -- the regressed column.
    _insert("network", name="linksel", network="10.160.0.0", subnet="16",
            network_ipv6="2001:db8:160::", subnet_ipv6="64", dhcp=1,
            dhcp_range_begin="10.160.10.1", dhcp_range_end="10.160.10.254", gateway="10.160.0.1",
            dhcp_range_begin_ipv6="2001:db8:160::10", dhcp_range_end_ipv6="2001:db8:160::ff",
            gateway_ipv6="2001:db8:160::1", nameserver_ip="10.141.0.1",
            nameserver_ip_ipv6="2001:db8:160::1", ntp_server="10.141.0.1", zone="linksel",
            shared=NETWORK, dhcp_relay="10.160.0.1,2001:db8:160::1",
            dhcp_link_subnet="10.170.35.0/24,2001:db8:170::/64")
    lid = Database().get_record(table="network", where='name="linksel"')[0]["id"]
    _alt_kernel_node("linkn4", "aa:bb:cc:00:00:c1", lid, ip="10.160.10.50")
    _alt_kernel_node("linkn6", "aa:bb:cc:00:00:c6", lid, ip6="2001:db8:160::50")
    # device-type parity anchor: a netboot switch in the same link-sel segment.
    _insert("switch", name="linksw", netboot=1, ostype="cumulus", default_url="http://edge")
    swid = Database().get_record(table="switch", where='name="linksw"')[0]["id"]
    _insert("switchinterface", switchid=swid, interface="eth0", macaddress="aa:bb:cc:00:00:c2", mgmt=1)
    swifid = Database().get_record(table="switchinterface", where=f"switchid={swid}")[0]["id"]
    _insert("ipaddress", ipaddress="10.160.10.6", tableref="switchinterface",
            tablerefid=swifid, networkid=lid)

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    constant["DHCP"]["TEMPLATE6"] = "templ_kea-dhcp6.cfg"
    assert Config().dhcp_overwrite() is True
    v4 = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    v6 = open(os.path.join(config_env, "dhcpd6.conf"), encoding="utf-8").read()

    def reservation(content, mac):
        import re
        m = re.search(r'"hw-address": "' + mac + r'".*?\}', content, re.S)
        return m.group(0) if m else ""

    # every topology x family keeps the alternative-kernel class on its node reservation
    for mac in ("aa:bb:cc:00:00:a1", "aa:bb:cc:00:00:b1", "aa:bb:cc:00:00:c1"):   # v4 reg/relay/link
        assert ALT_CLASS in reservation(v4, mac), f"v4 {mac} lost its alternative-kernel class"
    for mac in ("aa:bb:cc:00:00:a6", "aa:bb:cc:00:00:b6", "aa:bb:cc:00:00:c6"):   # v6 reg/relay/link
        assert ALT_CLASS in reservation(v6, mac), f"v6 {mac} lost its alternative-kernel class"
    # exactly the six node reservations carry it -- no over-emission at subnet/global scope
    assert v4.count(ALT_CLASS) == 3 and v6.count(ALT_CLASS) == 3
    # switch reservation in the link-sel net keeps its ZTP boot-file-name (parity anchor)
    assert '"hw-address": "aa:bb:cc:00:00:c2"' in v4 and "boot/switch/linksw" in v4
    # the richest fixture in the suite - dual-stack, three topologies in one group, both anchors,
    # nodes and a switch - so it is where both families are put in front of kea's own parser
    _kea_accepts(v4)
    _kea_accepts(v6, "6")
    _assert_classes_resolve(_kea(v4)["Dhcp4"])
    _assert_classes_resolve(_kea(v6)["Dhcp6"])


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
def test_dns_switch_interfaces_resolve_as_switch_dash_interface(config_env, seeded):
    """A switch's own IP keeps its bare <switch> name; each switch interface with an IP on a
    network resolves as <switch>-<interface> (so interfaces on the same zone do not collide);
    a mac-only interface with no network is absent from DNS."""
    from utils.config import Config
    from utils.database import Database

    netid = seeded["netid"]
    _insert("switch", name="nvsw01", netboot=1)
    swid = Database().get_record(table="switch", where='name="nvsw01"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.20", tableref="switch", tablerefid=swid, networkid=netid)
    _insert("switchinterface", switchid=swid, interface="eth1", macaddress="aa:bb:cc:00:00:e1")
    eth1id = Database().get_record(table="switchinterface",
                                   where=f'switchid={swid} AND interface="eth1"')[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.21", tableref="switchinterface",
            tablerefid=eth1id, networkid=netid)
    # mac-only interface: no ipaddress row, so no network/zone -> must not reach DNS
    _insert("switchinterface", switchid=swid, interface="mgmtonly", macaddress="aa:bb:cc:00:00:e2")

    assert Config().dns_configure() is True
    zone = open(os.path.join(config_env, f"{NETWORK}.luna.zone"), encoding="utf-8").read()

    def a_record(name, ip):
        return any(parts and parts[0] == name and "A" in parts and ip in parts
                   for parts in (line.split() for line in zone.splitlines()))

    assert a_record("nvsw01", "10.141.0.20")           # primary keeps bare name
    assert a_record("nvsw01-eth1", "10.141.0.21")      # interface suffixed, distinct
    # mac-only interface is silently and correctly skipped (no zone to live in)
    first_labels = {line.split()[0] for line in zone.splitlines() if line.split()}
    assert "mgmtonly" not in first_labels
    assert "nvsw01-mgmtonly" not in first_labels
    # reverse PTR carries the same distinct names
    rev = open(os.path.join(config_env, "0.141.10.in-addr.arpa.luna.zone"), encoding="utf-8").read()
    assert "nvsw01-eth1.cluster." in rev


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
