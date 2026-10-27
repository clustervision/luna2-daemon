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


def test_bootloader_accepts_every_spelling():
    for value in ("first", "grub", "yes", "true", "last", "no", "false", "none", True, False):
        doc = json.loads(json.dumps(VALID)); doc["sets"][0]["bootloader"] = value
        disklayout.validate(json.dumps(doc))


def test_bad_bootloader():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["bootloader"] = "xyzzy"
    _rejects(doc, "bootloader unsupported: 'xyzzy' "
                  "(allowed: first, grub, yes, true, last, no, false, none)")


def test_null_bootloader_rejected():
    """A key present with no value must not pass as absent: the default it would
    then silently take is not what the operator was trying to set."""
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["bootloader"] = None
    _rejects(doc, "bootloader unsupported")


def test_bootloader_on_data_set_rejected():
    doc = json.loads(json.dumps(VALID))
    doc["sets"].append({
        "name": "scratch", "role": "data", "selection": "discover", "raid": "none",
        "bootloader": "none", "volumes": [],
    })
    _rejects(doc, "bootloader is valid on the os set only")


def test_device_not_dev():
    doc = json.loads(json.dumps(VALID))
    doc["sets"][0]["selection"] = "manual"; doc["sets"][0]["devices"] = ["sda"]
    _rejects(doc, "must start with /dev/")


RAID1_OS = {
    "version": 2,
    "sets": [
        {"name": "os", "role": "os", "selection": "manual", "raid": "1",
         "devices": ["/dev/sda", "/dev/sdb"],
         "volumes": [
             {"name": "uefi", "mountpoint": "/boot/efi", "fs": "vfat", "provider": "partition", "size": "600M"},
             {"name": "swap", "mountpoint": "swap", "fs": "swap", "provider": "lvm", "size": "8G"},
             {"name": "root", "mountpoint": "/", "fs": "xfs", "provider": "lvm", "size": "100%"},
         ]},
        {"name": "scratch", "role": "data", "selection": "manual", "raid": "none",
         "devices": ["/dev/sdc"], "save": False, "persistent": True,
         "volumes": [
             {"name": "tmp", "mountpoint": "/tmp", "fs": "ext4", "provider": "partition", "size": "100G"},
             {"name": "scratch", "mountpoint": "/scratch", "fs": "xfs", "provider": "partition", "size": "100%"},
         ]},
    ],
}


def _raid1():
    return json.loads(json.dumps(RAID1_OS))


def test_raid1_os_with_a_data_set_accepts():
    disklayout.validate(json.dumps(RAID1_OS))


def test_second_os_set():
    doc = _raid1(); doc["sets"][1]["role"] = "os"
    _rejects(doc, "at most one set may have role=os")


def test_device_in_two_sets():
    doc = _raid1(); doc["sets"][1]["devices"] = ["/dev/sdb"]
    _rejects(doc, "appears in both set")


def test_save_needs_discover():
    doc = _raid1(); doc["sets"][1]["save"] = True
    _rejects(doc, "save is only valid on a selection=discover set")


def test_persistent_needs_manual():
    doc = _raid1(); doc["sets"][1]["selection"] = "discover"; del doc["sets"][1]["devices"]
    _rejects(doc, "persistent=true requires selection=manual")


def test_manual_needs_devices():
    doc = _raid1(); del doc["sets"][0]["devices"]
    _rejects(doc, "devices[] is required for selection=manual")


def test_negative_spares():
    doc = _raid1(); doc["sets"][0]["spares"] = -1
    _rejects(doc, "spares must be >= 0")


def test_empty_volumes():
    doc = _raid1(); doc["sets"][1]["volumes"] = []
    _rejects(doc, "volumes[] must be non-empty")


def test_parity_raid_os_set():
    doc = _raid1(); doc["sets"][0]["raid"] = "5"
    _rejects(doc, "is not supported for the OS set")


def test_os_set_without_root():
    doc = _raid1(); doc["sets"][0]["volumes"][2]["mountpoint"] = "/srv"
    _rejects(doc, "exactly one root volume")


def test_os_set_with_two_roots():
    doc = _raid1(); doc["sets"][0]["volumes"][1].update(mountpoint="/", fs="xfs")
    _rejects(doc, "exactly one root volume")


def test_direct_partition_on_raid_set():
    """The swap-on-raid case: a direct partition is not mirrored."""
    doc = _raid1(); doc["sets"][0]["volumes"][1]["provider"] = "partition"
    _rejects(doc, "direct partition volumes require raid=none")


def test_boot_partitions_on_raid_set_accept():
    doc = _raid1()
    doc["sets"][0]["volumes"].insert(1, {"name": "boot", "mountpoint": "/boot", "fs": "xfs",
                                         "provider": "partition", "size": "1G"})
    disklayout.validate(json.dumps(doc))


def test_two_rest_of_disk_partitions():
    doc = _raid1(); doc["sets"][1]["volumes"][0]["size"] = "100%"
    _rejects(doc, "at most one direct partition volume may use size=100%")


def test_rest_of_disk_partition_and_lvm():
    doc = _raid1()
    doc["sets"][1]["volumes"].append({"name": "data", "mountpoint": "/data", "fs": "xfs",
                                      "provider": "lvm", "size": "100%"})
    _rejects(doc, "cannot be mixed with lvm volumes")


def test_two_rest_of_disk_lvm_volumes():
    doc = _raid1(); doc["sets"][0]["volumes"][1]["size"] = "100%"
    _rejects(doc, "at most one lvm volume per set may use size=100%")


def test_relative_mountpoint():
    doc = _raid1(); doc["sets"][1]["volumes"][0]["mountpoint"] = "tmp"
    _rejects(doc, "mountpoint must be an absolute path or swap")


def test_swap_mountpoint_needs_swap_fs():
    doc = _raid1(); doc["sets"][0]["volumes"][1]["fs"] = "xfs"
    _rejects(doc, "mountpoint=swap requires fs=swap")


def test_swap_fs_needs_swap_mountpoint():
    doc = _raid1(); doc["sets"][0]["volumes"][1]["mountpoint"] = "/swap"
    _rejects(doc, "fs=swap requires mountpoint=swap")


def test_partition_needs_size():
    doc = _raid1(); del doc["sets"][1]["volumes"][0]["size"]
    _rejects(doc, "size is required for provider=partition")


def test_vfat_on_lvm():
    doc = _raid1(); doc["sets"][0]["volumes"][2]["fs"] = "vfat"
    _rejects(doc, "lvm volume fs must be xfs, ext4, or swap")


def test_allow_degraded_on_a_redundant_set_accepts():
    for value in (True, False):
        doc = _raid1(); doc["sets"][0]["allow_degraded"] = value
        disklayout.validate(json.dumps(doc))


def test_allow_degraded_on_a_set_without_redundancy():
    for raid in ("none", "0"):
        doc = _raid1(); doc["sets"][1]["raid"] = raid; doc["sets"][1]["allow_degraded"] = True
        _rejects(doc, "allow_degraded is valid on a redundant raid set only")


def test_include_san_on_a_discover_set_accepts():
    for value in (True, False):
        doc = json.loads(json.dumps(VALID)); doc["sets"][0]["include_san"] = value
        disklayout.validate(json.dumps(doc))


def test_include_san_on_a_manual_set():
    doc = _raid1(); doc["sets"][1]["include_san"] = True
    _rejects(doc, "include_san is only valid on a selection=discover set")


def test_include_san_must_be_a_boolean():
    doc = json.loads(json.dumps(VALID)); doc["sets"][0]["include_san"] = "true"
    _rejects(doc, "include_san must be true or false")


def test_allow_degraded_must_be_a_boolean():
    doc = _raid1(); doc["sets"][0]["allow_degraded"] = "true"
    _rejects(doc, "allow_degraded must be true or false")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); n += 1
    print(f"OK: {n} tests passed")
