#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for switch boot + ZTP support (TRIX-1880).

Two angles are exercised against the real code:

* dhcp_overwrite renders the switch DHCP reservation fields (option 114
  default-url, filename/boot-file-name, next-server) into both the ISC and Kea
  templates when a switch carries default_url/bootfile (controller prepended).
* the served ZTP recipe (templ_switch_ztp.json) and the generated commands-list
  (templ_switch_commands.cfg) render into valid, expected content.

System side effects are neutralised exactly as in test_config_render.
"""

import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "daemon", "templates"))

NETWORK = "cluster"
NETWORK_CIDR = "10.141.0.0"
NETMASK = "255.255.0.0"
RANGE_BEGIN = "10.141.10.1"
RANGE_END = "10.141.10.254"
CONTROLLER_IP = "10.141.255.254"
SWITCH_IP = "10.141.253.1"
SWITCH_MAC = "aa:bb:cc:00:11:22"
SWITCH_NAME = "leaf-sw01"
# default_url / bootfile are stored as controller-relative paths; the templates
# prepend http://<nextserver>:<nextport>/ (the controller, reused from the node logic).
DEFAULT_URL = "files/image-amd64-25.02.2225.bin"
BOOTFILE = "boot/switch/leaf-sw01"


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


def _seed_cluster_with_switch(netboot=1, default_url=DEFAULT_URL, bootfile=BOOTFILE,
                              ostype=None, tftp_enable=None):
    """Seed a minimal cluster with one switch.

    netboot defaults to enabled here so the rendering tests have something to
    assert; the off-by-default and missing-file paths pass explicit values.
    ostype/tftp_enable default to NULL (= nvos / off) unless set explicitly.
    """
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

    switch_cols = dict(name=SWITCH_NAME, macaddress=SWITCH_MAC)
    if netboot is not None:
        switch_cols["netboot"] = netboot
    if default_url is not None:
        switch_cols["default_url"] = default_url
    if bootfile is not None:
        switch_cols["bootfile"] = bootfile
    if ostype is not None:
        switch_cols["ostype"] = ostype
    if tftp_enable is not None:
        switch_cols["tftp_enable"] = tftp_enable
    _insert("switch", **switch_cols)
    sid = Database().get_record(table="switch", where=f'name="{SWITCH_NAME}"')[0]["id"]
    _insert("ipaddress", ipaddress=SWITCH_IP, tableref="switch",
            tablerefid=sid, networkid=netid)
    return {"netid": netid, "switchid": sid}


@pytest.fixture
def seeded_switch(sqlite_db):
    """A minimal cluster carrying one switch with netboot enabled and the ZTP fields set."""
    return _seed_cluster_with_switch()


@pytest.fixture
def config_env(sqlite_db, constant, tmp_path, monkeypatch):
    """Wire Config at the temp DB + output dir and neutralise system side effects."""
    import utils.config as cfgmod

    saved = {section: dict(constant[section]) for section in ("API", "TEMPLATES", "DHCP", "SERVICES")}
    constant["SERVICES"].update({"DHCP": "kea-dhcp4", "DHCP6": "kea-dhcp6", "DNS": "named",
                                 "CONTROL": "systemd", "COMMAND": "/bin/true", "COOLDOWN": "1s"})
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
    # neutralise the service queue (it otherwise spawns a real background restart thread)
    monkeypatch.setattr("utils.service.Service.queue", lambda *a, **k: None)

    yield str(tmp_path)

    for section, original in saved.items():
        constant[section].clear()
        constant[section].update(original)


def _render(template, **context):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    return env.get_template(template).render(**context)


@pytest.mark.regression
def test_dhcp_isc_renders_switch_reservation(config_env, seeded_switch):
    from utils.config import Config

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert f"host {SWITCH_NAME}.{NETWORK}" in content
    assert f"hardware ethernet {SWITCH_MAC}" in content
    # the recipe URL (bootfile) is advertised; controller (== subnet nextserver) is prepended
    assert f'filename "http://{CONTROLLER_IP}:' in content
    assert f'/{BOOTFILE}";' in content
    assert f"next-server {CONTROLLER_IP};" in content
    # the image is no longer advertised via DHCP (it is carried inside the ZTP recipe's 01-image)
    assert 'option default-url "http' not in content
    assert DEFAULT_URL not in content


# netboot=0 is explicitly disabled; netboot=None leaves the column NULL, which is
# the default and must also be treated as off.
@pytest.mark.regression
@pytest.mark.parametrize("netboot", [0, None])
def test_dhcp_isc_netboot_off_suppresses_boot_options(config_env, sqlite_db, netboot):
    from utils.config import Config

    _seed_cluster_with_switch(netboot=netboot)

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # the IP reservation is still emitted...
    assert f"host {SWITCH_NAME}.{NETWORK}" in content
    assert f"hardware ethernet {SWITCH_MAC}" in content
    assert f"fixed-address {SWITCH_IP}" in content
    # ...but with netboot off, no boot options are handed out
    assert 'option default-url "http' not in content
    assert DEFAULT_URL not in content
    assert BOOTFILE not in content


@pytest.mark.regression
def test_netboot_enabled_without_boot_file_warns_and_skips(config_env, sqlite_db, caplog):
    import logging
    from utils.config import Config

    _seed_cluster_with_switch(netboot=1, default_url=None, bootfile=None)

    with caplog.at_level(logging.WARNING, logger="luna2-daemon"):
        assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # reservation kept, but netboot is not performed (no boot options)
    assert f"host {SWITCH_NAME}.{NETWORK}" in content
    assert 'option default-url "http' not in content
    # and the misconfiguration is surfaced to the logger
    assert any("netboot is enabled" in r.message and SWITCH_NAME in r.message
               for r in caplog.records)


@pytest.mark.regression
def test_dhcp_kea_renders_switch_reservation(config_env, constant, seeded_switch):
    from utils.config import Config

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert f'"hw-address": "{SWITCH_MAC}"' in content
    assert f'"next-server": "{CONTROLLER_IP}"' in content
    # the recipe URL is delivered as DHCP option 67 (boot-file-name) inside option-data (the NVOS trigger)
    assert '"name": "boot-file-name"' in content
    assert f'http://{CONTROLLER_IP}:' in content and f'/{BOOTFILE}"' in content
    # tftp_enable defaults off -> option 66 suppressed for the switch via never-send
    assert '"name": "tftp-server-name"' in content and '"never-send": true' in content
    # the image is no longer advertised via DHCP (it is carried inside the recipe's 01-image)
    assert 'v4-captive-portal' not in content
    assert DEFAULT_URL not in content
    # ostype defaults to nvos -> the switch reservation carries no Cumulus option 239 data
    # (the global option-def declaration is always present; only the per-host option-data is gated)
    assert '"name": "cumulus-provision-url", "data"' not in content


@pytest.mark.regression
def test_kea_cumulus_ostype_emits_option239(config_env, constant, sqlite_db):
    """ostype=cumulus adds cumulus-provision-url (option 239); nvos/generic do not."""
    from utils.config import Config

    _seed_cluster_with_switch(ostype="cumulus")
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert '"name": "cumulus-provision-url", "data"' in content
    # 239 points at the same recipe URL as option 67, not the image
    assert f'/{BOOTFILE}"' in content
    # and the option is declared
    assert '"code": 239' in content


@pytest.mark.regression
def test_motherload_linksel_plus_switch_ztp(config_env, constant, sqlite_db, tmp_path):
    """THE MOTHER LOAD: TRIX-1921 (option-82.5 link-selection) + TRIX-1880 (switch ZTP: nvos eth0+eth1,
    cumulus opt-239, tftp never-send) in ONE rendered kea-dhcp4.conf via the real dhcp_overwrite().
    Also writes the config to a stable path so it can be kea -t'd on a live controller."""
    from utils.database import Database
    from base.interface import Interface
    from utils.config import Config

    # --- a relay / link-selection network (TRIX-1921) that also carries the ZTP switches ---
    _insert("cluster", name="mc", nameserver_ip="10.143.0.1", ntp_server="10.143.0.1")
    _insert("network", name="cluster", network="10.143.0.0", subnet="24", dhcp=1,
            dhcp_range_begin="10.143.0.20", dhcp_range_end="10.143.0.99",
            nameserver_ip="10.143.0.1", ntp_server="10.143.0.1", zone="cluster",
            dhcp_relay="10.144.53.7", dhcp_link_subnet="10.144.35.0/24")   # <- link-selection anchor
    netid = Database().get_record(table="network", where='name="cluster"')[0]["id"]
    _insert("controller", hostname="controller", beacon=1, clusterid=1)
    cid = Database().get_record(table="controller", where='hostname="controller"')[0]["id"]
    _insert("ipaddress", ipaddress="10.143.0.254", tableref="controller", tablerefid=cid, networkid=netid)

    # NVOS switch: netboot, plain (webserver) URL, tftp off (default suppress); eth0 = its own IP
    _insert("switch", name="nvsw", macaddress="aa:bb:cc:00:00:a0", netboot=1, ostype="nvos",
            url_protocol="plain", default_url="files/nvos.bin", bootfile="boot/switch/nvsw")
    nvid = Database().get_record(table="switch", where='name="nvsw"')[0]["id"]
    _insert("ipaddress", ipaddress="10.143.0.10", tableref="switch", tablerefid=nvid, networkid=netid)
    # ...plus an eth1 interface (own mac/ip -> own reservation)
    Interface().change_switch_interface("nvsw", {'config': {'switch': {'nvsw': {'interfaces': [
        {'interface': 'eth1', 'macaddress': 'aa:bb:cc:00:00:a1', 'network': 'cluster', 'ipaddress': '10.143.0.11'}]}}}})

    # Cumulus switch: gets the extra option-239
    _insert("switch", name="cusw", macaddress="aa:bb:cc:00:00:b0", netboot=1, ostype="cumulus",
            bootfile="boot/switch/cusw")
    cuid = Database().get_record(table="switch", where='name="cusw"')[0]["id"]
    _insert("ipaddress", ipaddress="10.143.0.20", tableref="switch", tablerefid=cuid, networkid=netid)

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # ---- TRIX-1921: link-selection shared-network rendered ----
    assert '"shared-networks"' in content
    assert '"authoritative": false' in content          # the pool-less anchor
    assert '10.144.35.0/24' in content                   # the link anchor prefix

    # ---- TRIX-1880: three switch reservations (nvsw eth0, nvsw eth1, cusw) inside the boot subnet ----
    for mac in ("aa:bb:cc:00:00:a0", "aa:bb:cc:00:00:a1", "aa:bb:cc:00:00:b0"):
        assert f'"hw-address": "{mac}"' in content
    assert content.count('"name": "boot-file-name"') >= 3        # opt 67 recipe on each
    assert content.count('"never-send": true') >= 3             # tftp suppressed on each (tftp_enable off)
    assert '"name": "cumulus-provision-url", "data"' in content  # opt 239 for the cumulus switch only
    assert 'v4-captive-portal' not in content                    # image not advertised via DHCP

    # write it out for live kea -t
    open("/home/claude/trix-motherload-kea4.conf", "w").write(content)


@pytest.mark.regression
def test_switch_interface_gets_its_own_reservation(config_env, constant, seeded_switch):
    """An added switch interface (eth1) yields its own Kea reservation; eth0 (switch IP) stays."""
    from base.interface import Interface
    from utils.config import Config

    IF_MAC = "aa:bb:cc:00:11:33"
    IF_IP = "10.141.253.2"
    req = {'config': {'switch': {SWITCH_NAME: {'interfaces': [
        {'interface': 'eth1', 'macaddress': IF_MAC, 'network': NETWORK, 'ipaddress': IF_IP}]}}}}
    status, msg = Interface().change_switch_interface(SWITCH_NAME, req)
    assert status is True, msg

    status, resp = Interface().get_all_switch_interface(SWITCH_NAME)
    assert status is True
    ifaces = resp['config']['switch'][SWITCH_NAME]['interfaces']
    assert any(i['interface'] == 'eth1' and i.get('macaddress') == IF_MAC for i in ifaces)

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()
    assert f'"hw-address": "{IF_MAC}"' in content        # eth1 reservation present
    assert f'"hw-address": "{SWITCH_MAC}"' in content     # eth0 (switch's own IP) still there
    # eth1 carries the recipe too (parent switch's ZTP config): >=2 boot-file-name option-data entries
    assert content.count('"name": "boot-file-name"') >= 2

    status, msg = Interface().delete_switch_interface(SWITCH_NAME, 'eth1')
    assert status is True, msg
    status, resp = Interface().get_all_switch_interface(SWITCH_NAME)
    assert status is False  # no interfaces left


@pytest.mark.regression
def test_kea_tftp_enable_on_keeps_option66(config_env, constant, sqlite_db):
    """tftp_enable=on stops the per-switch never-send, so the switch keeps option 66 (TFTP install)."""
    from utils.config import Config

    _seed_cluster_with_switch(tftp_enable=1)
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # no per-switch never-send suppression when the toggle is on
    assert '"never-send": true' not in content


@pytest.mark.regression
def test_kea_tftp_enable_with_url_server_points_option66_at_override(config_env, constant, sqlite_db):
    """tftp_enable=on + url_server: option 66 (tftp-server-name) follows the url_server override —
    like next-server and the boot URL — instead of the switch inheriting the subnet default."""
    from utils.config import Config
    from utils.database import Database

    _seed_cluster_with_switch(tftp_enable=1)
    Database().update("switch", [{"column": "url_server", "value": "10.141.0.9"}],
                      [{"column": "name", "value": SWITCH_NAME}])
    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"
    assert Config().dhcp_overwrite() is True
    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert '"never-send": true' not in content                                  # enabled -> not suppressed
    assert '"name": "tftp-server-name", "data": "10.141.0.9"' in content        # host-level, follows url_server


@pytest.mark.regression
def test_switch_ztp_json_renders_valid(seeded_switch):
    image = f"http://{CONTROLLER_IP}:7050/{DEFAULT_URL}"
    commands = f"http://{CONTROLLER_IP}:7050/boot/switch/{SWITCH_NAME}/commands"
    rendered = _render(
        "templ_switch_ztp.json",
        SWITCH_NAME=SWITCH_NAME,
        IMAGE_URL=image,
        ZTP_FORMAT="commands",
        COMMANDS_URL=commands,
        CONNECTIVITY_HOST=CONTROLLER_IP,
    )
    recipe = json.loads(rendered)

    assert recipe["ztp"]["01-image"]["image"]["install"]["url"] == image
    assert recipe["ztp"]["02-commands-list"]["url"] == commands
    assert "02-startup-file" not in recipe["ztp"]
    assert recipe["ztp"]["03-connectivity-check"]["connectivity-check"]["ping-hosts"] == [CONTROLLER_IP]


@pytest.mark.regression
def test_switch_ztp_json_yaml_format_uses_startup_file():
    commands = f"http://{CONTROLLER_IP}:7050/boot/switch/{SWITCH_NAME}/commands"
    rendered = _render(
        "templ_switch_ztp.json",
        SWITCH_NAME=SWITCH_NAME,
        IMAGE_URL=None,
        ZTP_FORMAT="yaml",
        COMMANDS_URL=commands,
        CONNECTIVITY_HOST=CONTROLLER_IP,
    )
    recipe = json.loads(rendered)

    # yaml format swaps the section to 02-startup-file (declarative), same URL
    assert "02-commands-list" not in recipe["ztp"]
    assert recipe["ztp"]["02-startup-file"]["url"] == commands


@pytest.mark.regression
def test_switch_ztp_json_omits_image_when_no_url():
    rendered = _render(
        "templ_switch_ztp.json",
        SWITCH_NAME=SWITCH_NAME,
        IMAGE_URL=None,
        COMMANDS_URL=f"{BOOTFILE}/commands",
        CONNECTIVITY_HOST=CONTROLLER_IP,
    )
    recipe = json.loads(rendered)

    assert "01-image" not in recipe["ztp"]
    assert "02-commands-list" in recipe["ztp"]


@pytest.mark.regression
def test_switch_commands_default_renders():
    rendered = _render("templ_switch_commands.cfg", SWITCH_NAME=SWITCH_NAME)

    assert f"nv set system hostname {SWITCH_NAME}" in rendered
    assert rendered.strip().endswith("nv config apply -y")


# Clearing a ZTP field from the CLI sends an empty string; it must be stored as
# NULL so it reads back identically to a never-set field ("None"), not as blank.
@pytest.mark.regression
@pytest.mark.parametrize("field", ["bootfile", "default_url", "ztpconfig", "ztpformat"])
def test_clearing_ztp_field_stores_null(sqlite_db, field):
    from utils.database import Database
    from base.switch import Switch

    _seed_cluster_with_switch()
    Database().update(
        "switch",
        [{"column": "ztpconfig", "value": "hostname leaf-sw01"},
         {"column": "ztpformat", "value": "commands"}],
        [{"column": "name", "value": SWITCH_NAME}],
    )

    request_data = {"config": {"switch": {SWITCH_NAME: {field: ""}}}}
    status, _ = Switch().update_switch(name=SWITCH_NAME, request_data=request_data)
    assert status is True

    record = Database().get_record(table="switch", where=f'name="{SWITCH_NAME}"')[0]
    assert record[field] is None


@pytest.mark.regression
def test_delete_switch_cascades_to_switchinterface(config_env, seeded_switch):
    """Deleting a switch removes its switchinterface rows and their ipaddress rows,
    rather than orphaning them."""
    from base.switch import Switch
    from utils.database import Database

    sid = seeded_switch["switchid"]
    _insert("switchinterface", switchid=sid, interface="eth1", macaddress="aa:bb:cc:00:00:e1")
    ifid = Database().get_record(table="switchinterface", where=f"switchid={sid}")[0]["id"]
    _insert("ipaddress", ipaddress="10.141.0.30", tableref="switchinterface",
            tablerefid=ifid, networkid=seeded_switch["netid"])

    ok, _ = Switch().delete_switch(SWITCH_NAME)
    assert ok is True
    assert not Database().get_record(table="switchinterface", where=f"switchid={sid}")
    assert not Database().get_record(table="ipaddress",
                                     where=f'tableref="switchinterface" AND tablerefid={ifid}')
