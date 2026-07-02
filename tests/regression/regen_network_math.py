#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Regenerate the network_math.json golden file from the current Helper behaviour.

Run this ONLY after an intended change to the network helpers, then review the
diff before committing. Inputs are fixed here; outputs are recomputed.

    python tests/regression/regen_network_math.py
"""

import json
import os
import sys
import types

from cryptography.fernet import Fernet

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "daemon"))

_stub = types.ModuleType("common.constant")
_stub.CONSTANT = {
    "LOGGER": {"LEVEL": "error", "LOGFILE": None},
    "DATABASE": {"DRIVER": "SQLite3", "DATABASE": ":memory:"},
    "FILES": {"KEYFILE": None}, "SECRETS": {"ENCRYPT_SECRETS": "yes"},
    "API": {}, "SERVICES": {}, "PLUGINS": {}, "TEMPLATES": {}, "BMCCONTROL": {}, "DHCP": {},
}
_stub.LUNAKEY = Fernet.generate_key().decode()
sys.modules["common.constant"] = _stub

from utils.log import Log  # noqa: E402

Log.init_log("error")
from utils.helper import Helper  # noqa: E402

NETWORK_INPUTS = [("10.141.0.0", "16"), ("10.141.0.0", "24"),
                  ("192.168.1.0", "255.255.255.0"), ("172.16.0.0", "12")]
RANGE_INPUTS = [("10.141.0.1", "10.141.0.5"), ("10.141.0.1", "10.141.0.1"),
                ("10.141.255.250", "10.141.255.254")]


def build():
    helper = Helper()
    networks = []
    for ipaddr, subnet in NETWORK_INPUTS:
        network = helper.get_network(ipaddr, subnet)
        networks.append({
            "ipaddr": ipaddr, "subnet": subnet, "network": network,
            "netmask": helper.get_netmask(network),
            "size": helper.get_network_size(ipaddr, subnet),
        })
    ranges = []
    for start, end in RANGE_INPUTS:
        ranges.append({
            "start": start, "end": end,
            "size": helper.get_ip_range_size(start, end),
            "ips": helper.get_ip_range_ips(start, end),
        })
    return {"networks": networks, "ranges": ranges}


def main():
    target = os.path.join(os.path.dirname(__file__), "golden", "network_math.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(build(), handle, indent=2)
        handle.write("\n")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
