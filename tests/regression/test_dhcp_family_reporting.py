#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1939 regression tests for how a one-family DHCP fault is reported.

dhcp_overwrite renders a v4 and a v6 configuration in one pass and the two are reloaded
together, so a fault in either holds both back. That coupling is deliberate and is not what
these tests question. What they pin is that the fault is attributed correctly:

* the family that failed is named, with the server's own reason, so an administrator has
  somewhere to start rather than "containing errors";
* the family that validated clean is stated to be clean and held back, not blamed;
* neither configuration is installed while one of them is refused, so the file on disk and
  the running service cannot disagree until some later restart applies the difference.

The harness stubs the syntax checker, so these drive the real dhcp_overwrite with one family
failing and one succeeding.
"""

import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "daemon", "templates"))


def _insert(table, **columns):
    from utils.database import Database
    Database().insert(table, [{"column": k, "value": v} for k, v in columns.items()])


@pytest.fixture
def dual_stack(sqlite_db, constant, tmp_path, monkeypatch):
    """A cluster with one dual-stack DHCP network, and every install captured rather than done."""
    import utils.config as cfgmod

    saved = {section: dict(constant[section]) for section in ("API", "TEMPLATES", "DHCP")}
    constant["TEMPLATES"].update({"TEMPLATE_FILES": TEMPLATES_DIR, "TMP_DIRECTORY": str(tmp_path)})
    constant["API"].update({"PROTOCOL": "http", "VERIFY_CERTIFICATE": "no",
                            "ENDPOINT": "controller:7050"})
    constant["DHCP"].update({"OMAPIKEY": None,
                             "TEMPLATE": "templ_kea-dhcp4.cfg", "TEST": "/bin/true",
                             "CONFIG_PATH": str(tmp_path / "kea-dhcp4.conf.live"),
                             "TEMPLATE6": "templ_kea-dhcp6.cfg", "TEST6": "/bin/true",
                             "CONFIG6_PATH": str(tmp_path / "kea-dhcp6.conf.live")})

    installed = []
    monkeypatch.setattr(cfgmod.shutil, "copyfile", lambda src, dst: installed.append(dst))
    monkeypatch.setattr(cfgmod.os, "makedirs", lambda *a, **k: None)

    _insert("cluster", name="mycluster", nameserver_ip="10.141.0.1", ntp_server="10.141.0.1")
    _insert("network", name="cluster", network="10.141.0.0", subnet="16", dhcp=1,
            dhcp_range_begin="10.141.10.1", dhcp_range_end="10.141.10.254",
            network_ipv6="fd00:141::", subnet_ipv6="64",
            dhcp_range_begin_ipv6="fd00:141::10", dhcp_range_end_ipv6="fd00:141::ff",
            nameserver_ip="10.141.0.1", nameserver_ip_ipv6="fd00:141::1", zone="cluster")

    yield {"installed": installed, "tmp": tmp_path}

    for section, original in saved.items():
        constant[section].clear()
        constant[section].update(original)


@pytest.mark.regression
def test_a_failing_v6_names_v6_and_clears_v4(dual_stack, constant, caplog):
    """The v4 config is fine; the log must say so and must not report it as the fault."""
    from utils.config import Config

    constant["DHCP"]["TEST6"] = "/bin/false"
    with caplog.at_level("ERROR"):
        assert Config().dhcp_overwrite() is False

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "DHCP6 file" in messages, "the failing family must be named"
    assert "DHCPv4 configuration validated clean" in messages, (
        "the healthy family must be reported as clean and held back. Reporting the failure "
        "against it sends an administrator to a file with nothing wrong in it.")
    assert "DHCPv4 file" not in messages, "the healthy family must not be reported as failing"


@pytest.mark.regression
def test_a_failing_v4_names_v4_and_clears_v6(dual_stack, constant, caplog):
    """The mirror case, so the reporting cannot be right in one direction only."""
    from utils.config import Config

    constant["DHCP"]["TEST"] = "/bin/false"
    with caplog.at_level("ERROR"):
        assert Config().dhcp_overwrite() is False

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "DHCP file" in messages
    assert "DHCPv6 configuration validated clean" in messages


@pytest.mark.regression
def test_nothing_is_installed_while_one_family_is_refused(dual_stack, constant):
    """Installing the good family while the other is refused leaves disk and service disagreeing."""
    from utils.config import Config

    constant["DHCP"]["TEST6"] = "/bin/false"
    Config().dhcp_overwrite()
    assert dual_stack["installed"] == [], (
        f"a configuration was copied into place while the other family was refused: "
        f"{dual_stack['installed']}. The services are reloaded together, so that file sits "
        f"unapplied until an unrelated restart picks it up silently.")


@pytest.mark.regression
def test_both_families_install_when_both_validate(dual_stack, constant):
    """The ordinary case must be untouched: both good, both installed, True."""
    from utils.config import Config

    assert Config().dhcp_overwrite() is True
    assert sorted(dual_stack["installed"]) == sorted([
        constant["DHCP"]["CONFIG_PATH"], constant["DHCP"]["CONFIG6_PATH"]])


@pytest.mark.regression
def test_the_checkers_own_reason_reaches_the_log(dual_stack, constant, caplog):
    """'containing errors' with no reason is where diagnosis used to stop."""
    from utils.config import Config

    # A stand-in for kea-dhcp6 -t: refuses the file and says why, as the real one does. The
    # command is split on whitespace before the file is appended, so it has to be a script.
    checker = dual_stack["tmp"] / "refuse.sh"
    checker.write_text("#!/bin/sh\necho 'interface ens6 is not present in the system' >&2\nexit 1\n")
    constant["DHCP"]["TEST6"] = f"/bin/sh {checker}"
    with caplog.at_level("ERROR"):
        Config().dhcp_overwrite()

    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "not present in the system" in messages, (
        "the syntax checker's own output must be logged; without it the operator is told a file "
        "contains errors and never which one.")
