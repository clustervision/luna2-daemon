# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Daemon-side disklayout validation (one of two locations; the node's Go v2
validator is the other).

This is a SOUND SUBSET of the node-side validator
(luna2-client internal/config/v2/validate.go): it rejects the common, stable,
high-frequency authoring mistakes -- malformed JSON, wrong version, empty sets,
unknown keys, missing required fields, bad enum values, non-/dev device paths --
so a bad disklayout is caught at STORE time (every client, not just the CLI),
with a clear message, instead of only failing later on the node.

DESIGN INVARIANT -- soundness (no false rejections): every rule here mirrors a
Go rule exactly, so anything this rejects the node would also reject
(daemon-reject => node-reject). It deliberately does NOT replicate the deep
topology rules (raid member-count maths, the OS-set ESP/root requirement,
cross-set device exclusivity): those are rarely mis-authored and the node stays
authoritative for them. Keeping the subset shallow keeps it low-drift -- it
depends only on the stable grammar (allowed keys, required fields, enums), not
on the evolving topology logic. The soundness invariant is regression-tested
against the shared layout corpus (daemon-reject => Go-reject on every file).

Stdlib-only and side-effect-free so it can be unit-tested in isolation.
"""

import json

# Allowed keys per object (mirrors v2 types.go, INCLUDING the `comment` field
# added by the luna2-client comment-field patch -- so a commented layout the node
# now accepts is not falsely rejected here).
_ALLOWED_TOP = {"version", "sets", "comment"}
_ALLOWED_SET = {
    "name", "role", "selection", "raid", "count", "spares",
    "match", "devices", "save", "persistent", "origin", "volumes", "comment",
}
_ALLOWED_MATCH = {"tags", "min_size", "max_size", "model"}
_ALLOWED_ORIGIN = {"from", "at", "by", "host"}
_ALLOWED_VOLUME = {
    "name", "mountpoint", "fs", "size", "provider", "options", "clear_uefi_nvram", "comment",
}

# Enumerated values (mirrors v2 validate.go). tmpfs/memory/zfs are omitted on
# purpose: the node rejects them (reserved), so rejecting them here is sound.
_ROLES = {"os", "data"}
_SELECTIONS = {"discover", "manual"}
_FILESYSTEMS = {"vfat", "xfs", "ext4", "swap"}
_PROVIDERS = {"partition", "lvm"}
_RAID_LEVELS = {"none", "0", "1", "5", "6", "10"}

SCHEMA_VERSION = 2


class DisklayoutInvalid(ValueError):
    """A disklayout failed daemon-side validation. Message is operator-facing."""


def _unknown_key(obj, allowed, label):
    bad = sorted(k for k in obj if k not in allowed)
    if bad:
        raise DisklayoutInvalid(f"config_validation: {label}: unknown field '{bad[0]}'")


def _require_str(obj, key, label):
    value = obj.get(key)
    if not isinstance(value, str) or value == "":
        raise DisklayoutInvalid(f"config_validation: {label}.{key} is required")
    return value


def _validate_volume(vol, label):
    if not isinstance(vol, dict):
        raise DisklayoutInvalid(f"config_validation: {label} must be an object")
    _unknown_key(vol, _ALLOWED_VOLUME, label)
    _require_str(vol, "name", label)
    _require_str(vol, "mountpoint", label)
    fs = _require_str(vol, "fs", label)
    if fs not in _FILESYSTEMS:
        raise DisklayoutInvalid(
            f"config_validation: {label}.fs unsupported: '{fs}' (allowed: vfat, xfs, ext4, swap)")
    provider = _require_str(vol, "provider", label)
    if provider not in _PROVIDERS:
        raise DisklayoutInvalid(
            f"config_validation: {label}.provider unsupported: '{provider}' (allowed: partition, lvm)")


def _validate_set(a_set, idx):
    label = f"sets[{idx}]"
    if not isinstance(a_set, dict):
        raise DisklayoutInvalid(f"config_validation: {label} must be an object")
    _unknown_key(a_set, _ALLOWED_SET, label)
    if "match" in a_set and isinstance(a_set["match"], dict):
        _unknown_key(a_set["match"], _ALLOWED_MATCH, label + ".match")
    if "origin" in a_set and isinstance(a_set["origin"], dict):
        _unknown_key(a_set["origin"], _ALLOWED_ORIGIN, label + ".origin")

    _require_str(a_set, "name", label)
    role = _require_str(a_set, "role", label)
    if role not in _ROLES:
        raise DisklayoutInvalid(
            f"config_validation: {label}.role unsupported: '{role}' (allowed: os, data)")
    selection = _require_str(a_set, "selection", label)
    if selection not in _SELECTIONS:
        raise DisklayoutInvalid(
            f"config_validation: {label}.selection unsupported: '{selection}' (allowed: discover, manual)")
    raid = _require_str(a_set, "raid", label)
    if raid not in _RAID_LEVELS:
        raise DisklayoutInvalid(
            f"config_validation: {label}.raid unsupported: '{raid}' (allowed: none, 0, 1, 5, 6, 10)")

    for key in ("count", "spares"):
        if key in a_set and not isinstance(a_set[key], int):
            raise DisklayoutInvalid(f"config_validation: {label}.{key} must be a whole number")

    devices = a_set.get("devices")
    if devices is not None:
        if not isinstance(devices, list):
            raise DisklayoutInvalid(f"config_validation: {label}.devices must be a list")
        for dev in devices:
            if not isinstance(dev, str) or not dev.startswith("/dev/"):
                raise DisklayoutInvalid(f"config_validation: device path must start with /dev/: {dev}")

    volumes = a_set.get("volumes")
    if not isinstance(volumes, list):
        raise DisklayoutInvalid(f"config_validation: {label}.volumes must be a list")
    for vidx, vol in enumerate(volumes):
        _validate_volume(vol, f"{label}.volumes[{vidx}]")


def validate(raw):
    """Validate a disklayout JSON document (bytes or str). Raises
    :class:`DisklayoutInvalid` with an operator-facing reason, or returns None
    when the document passes this (subset) check. An empty/blank document is
    accepted (no layout declared is a legal node state)."""
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8", "strict")
    if raw is None or raw.strip() == "":
        return  # no disklayout declared -- legal
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as err:
        raise DisklayoutInvalid(f"config_validation: not valid JSON: {err}")
    if not isinstance(doc, dict):
        raise DisklayoutInvalid("config_validation: top-level: must be an object with a 'sets' list")
    _unknown_key(doc, _ALLOWED_TOP, "top-level")
    if doc.get("version") != SCHEMA_VERSION:
        raise DisklayoutInvalid(f"config_validation: version must be 2, got: {doc.get('version')!r}")
    sets = doc.get("sets")
    if not isinstance(sets, list):
        raise DisklayoutInvalid("config_validation: sets must be an array")
    if len(sets) == 0:
        raise DisklayoutInvalid("config_validation: sets[] must be non-empty")
    for idx, a_set in enumerate(sets):
        _validate_set(a_set, idx)
