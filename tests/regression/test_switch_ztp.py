#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regression tests for NVOS/NVLink switch boot + ZTP support (TRIX-1880).

Two angles are exercised against the real code:

* dhcp_overwrite renders the switch DHCP reservation fields (option 114
  default-url, filename/boot-file-name, next-server) into both the ISC and Kea
  templates when a switch carries default_url/bootfile/next_server.
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
SWITCH_NAME = "nvlink-sw01"
DEFAULT_URL = "http://10.141.255.254/images/nvos-amd64-25.02.2225.bin"
BOOTFILE = "http://10.141.255.254:7050/boot/switch/nvlink-sw01"
NEXT_SERVER = "10.141.200.50"


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


def _seed_cluster_with_switch(netboot=None):
    """Seed a minimal cluster with one switch carrying the ZTP DHCP fields.

    netboot is left at the column default (None -> treated as enabled) unless a
    value is passed, so the disabled path can be exercised explicitly.
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

    switch_cols = dict(name=SWITCH_NAME, macaddress=SWITCH_MAC,
                       default_url=DEFAULT_URL, bootfile=BOOTFILE, next_server=NEXT_SERVER)
    if netboot is not None:
        switch_cols["netboot"] = netboot
    _insert("switch", **switch_cols)
    sid = Database().get_record(table="switch", where=f'name="{SWITCH_NAME}"')[0]["id"]
    _insert("ipaddress", ipaddress=SWITCH_IP, tableref="switch",
            tablerefid=sid, networkid=netid)
    return {"netid": netid, "switchid": sid}


@pytest.fixture
def seeded_switch(sqlite_db):
    """A minimal cluster carrying one switch with the ZTP DHCP fields set (netboot default)."""
    return _seed_cluster_with_switch()


@pytest.fixture
def config_env(sqlite_db, constant, tmp_path, monkeypatch):
    """Wire Config at the temp DB + output dir and neutralise system side effects."""
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


def _render(template, **context):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    return env.get_template(template).render(**context)


@pytest.mark.regression
def test_dhcp_isc_renders_switch_reservation(config_env, seeded_switch):
    from utils.config import Config

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert "option default-url code 114 = text;" in content
    assert f"host {SWITCH_NAME}.{NETWORK}" in content
    assert f"hardware ethernet {SWITCH_MAC}" in content
    assert f'option default-url "{DEFAULT_URL}";' in content
    assert f'filename "{BOOTFILE}";' in content
    assert f"next-server {NEXT_SERVER};" in content


@pytest.mark.regression
def test_dhcp_isc_netboot_disabled_suppresses_boot_options(config_env, sqlite_db):
    from utils.config import Config

    _seed_cluster_with_switch(netboot=0)

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    # the IP reservation is still emitted...
    assert f"host {SWITCH_NAME}.{NETWORK}" in content
    assert f"hardware ethernet {SWITCH_MAC}" in content
    assert f"fixed-address {SWITCH_IP}" in content
    # ...but with netboot disabled, no boot options are handed out
    assert DEFAULT_URL not in content
    assert BOOTFILE not in content
    assert f"next-server {NEXT_SERVER};" not in content


@pytest.mark.regression
def test_dhcp_kea_renders_switch_reservation(config_env, constant, seeded_switch):
    from utils.config import Config

    constant["DHCP"]["TEMPLATE"] = "templ_kea-dhcp4.cfg"

    assert Config().dhcp_overwrite() is True

    content = open(os.path.join(config_env, "dhcpd.conf"), encoding="utf-8").read()

    assert f'"hw-address": "{SWITCH_MAC}"' in content
    assert f'"boot-file-name": "{BOOTFILE}"' in content
    assert f'"next-server": "{NEXT_SERVER}"' in content
    assert f'"name": "v4-captive-portal", "data": "{DEFAULT_URL}"' in content


@pytest.mark.regression
def test_switch_ztp_json_renders_valid(seeded_switch):
    rendered = _render(
        "templ_switch_ztp.json",
        SWITCH_NAME=SWITCH_NAME,
        IMAGE_URL=DEFAULT_URL,
        COMMANDS_URL=f"{BOOTFILE}/commands",
        CONNECTIVITY_HOST=CONTROLLER_IP,
    )
    recipe = json.loads(rendered)

    assert recipe["ztp"]["01-image"]["image"]["install"]["url"] == DEFAULT_URL
    assert recipe["ztp"]["02-commands-list"]["url"] == f"{BOOTFILE}/commands"
    assert recipe["ztp"]["03-connectivity-check"]["connectivity-check"]["ping-hosts"] == [CONTROLLER_IP]


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
