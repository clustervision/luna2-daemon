# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
# GPL-3.0-or-later

"""Unit tests for the daemon-side disklayout validator (a sound subset of the
node's Go v2 validator). Run: python3 -m pytest utils/test_disklayout.py"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import disklayout  # noqa: E402

VALID = {
    "version": 2,
    "sets": [{
        "name": "os", "role": "os", "selection": "discover", "raid": "none",
        "volumes": [
            {"name": "uefi", "mountpoint": "/boot/efi", "fs": "vfat", "provider": "partition", "size": "600M"},
            {"name": "root", "mountpoint": "/", "fs": "xfs", "provider": "lvm", "size": "100%"},
        ],
    }],
}


def _rejects(doc, needle=None):
    try:
        disklayout.validate(json.dumps(doc))
    except disklayout.DisklayoutInvalid as e:
        assert needle is None or needle in str(e), f"got: {e}"
        return
    raise AssertionError(f"expected rejection ({needle}); accepted: {doc}")


def test_valid_accepts():
    disklayout.validate(json.dumps(VALID))


def test_empty_is_legal():
    disklayout.validate("")
    disklayout.validate("   ")
    disklayout.validate(b"")


def test_commented_accepts():
    doc = json.loads(json.dumps(VALID))
    doc["comment"] = "layout note"
    doc["sets"][0]["comment"] = "set note"
    doc["sets"][0]["volumes"][0]["comment"] = "vol note"
    disklayout.validate(json.dumps(doc))


def test_not_json():
    _rejects_raw("{not json", "not valid JSON")


def _rejects_raw(raw, needle):
    try:
        disklayout.validate(raw)
    except disklayout.DisklayoutInvalid as e:
        assert needle in str(e), f"got: {e}"
        return
    raise AssertionError(f"expected rejection ({needle})")


def test_not_object():
    _rejects_raw("[1,2,3]", "must be an object")


def test_bad_version():
    doc = json.loads(json.dumps(VALID)); doc["version"] = 1
    _rejects(doc, "version must be 2")


def test_empty_sets():
    _rejects({"version": 2, "sets": []}, "sets[] must be non-empty")


def test_unknown_top_key():
    doc = json.loads(json.dumps(VALID)); doc["preserve"] = 1
    _rejects(doc, "unknown field 'preserve'")


def test_unknown_set_key():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["stray"] = 1
    _rejects(doc, "unknown field 'stray'")


def test_unknown_volume_key():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["volumes"][0]["oops"] = 1
    _rejects(doc, "unknown field 'oops'")


def test_bad_role():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["role"] = "scratch"
    _rejects(doc, "role unsupported")


def test_missing_selection():
    doc = json.loads(json.dumps(VALID)); del doc["sets"][0]["selection"]
    _rejects(doc, "selection is required")


def test_bad_raid():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["raid"] = "7"
    _rejects(doc, "raid unsupported")


def test_bad_fs():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["volumes"][1]["fs"] = "btrfs"
    _rejects(doc, "fs unsupported")


def test_reserved_fs_tmpfs_rejected():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["volumes"][1]["fs"] = "tmpfs"
    _rejects(doc, "fs unsupported")  # reserved on the node -> sound to reject here


def test_bad_provider():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["volumes"][1]["provider"] = "memory"
    _rejects(doc, "provider unsupported")


def test_missing_volume_field():
    doc = json.loads(json.dumps(VALID)); del doc["sets"][0]["volumes"][0]["mountpoint"]
    _rejects(doc, "mountpoint is required")


def test_device_not_dev():
    doc = json.loads(json.dumps(VALID))
    doc["sets"][0]["selection"] = "manual"; doc["sets"][0]["devices"] = ["sda"]
    _rejects(doc, "must start with /dev/")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1
    print(f"OK: {n} tests passed")
