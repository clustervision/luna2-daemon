# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
Daemon-side validation of the network mounts document, the network twin of the
disklayout validator beside it.

The document is one declaration of what the cluster serves and what its machines
mount: an array of entries keyed on the mountpoint, each optionally carrying an
export block for the machine that serves it. It is stored as base64 JSON on the
cluster, the group and the node, and resolves by strict override, the highest
level that holds one winning outright.

What is checked here is the grammar: shape, keys, enumerations, uniqueness, and
the two structural rules an export block has to meet. Anything only the consuming
machine can answer, whether an option is valid for its mount helper, whether a
Luna network named in a client list exists, is left to the render stage. A
document this accepts is well formed; the machine stays authoritative for the
rest.

Stdlib-only and side-effect-free so it can be unit-tested in isolation. The one
rule that needs data, an export block naming a server the stack configures,
takes the known names as an argument rather than reading them here.
"""

import json
from base64 import b64decode

_ALLOWED_TOP = {"version", "comment", "mounts"}
_ALLOWED_MOUNT = {
    "path", "type", "server", "source", "export", "options", "state",
    "owner", "group", "mode", "comment",
}
_ALLOWED_EXPORT = {"options", "clients", "comment"}
_ALLOWED_CLIENT = {"to", "options", "comment"}

# mmfs is an alias of gpfs, accepted and never a separate value
_TYPES = {"nfs", "lustre", "beegfs", "gpfs", "mmfs", "panfs", "manual"}
_STATES = {"mounted", "present", "absent"}
# the words that stand for the machine serving the cluster: the controller, and
# the host the daemon runs on. both may carry an export block
RESERVED_SERVERS = {"controller", "self"}
_MODE_DIGITS = set("01234567")

SCHEMA_VERSION = 1


class MountsInvalid(ValueError):
    """A mounts document failed daemon-side validation. Message is operator-facing."""


def known_servers(node_rows, controller_rows=None):
    """The names an export block may name as its server: the nodes by name and
    the controllers by hostname, beside the reserved words."""
    names = {row['name'] for row in (node_rows or []) if row.get('name')}
    names |= {row['hostname'] for row in (controller_rows or []) if row.get('hostname')}
    return names


def _unknown_key(obj, allowed, label):
    bad = sorted(k for k in obj if k not in allowed)
    if bad:
        raise MountsInvalid(f"config_validation: {label}: unknown field '{bad[0]}'")


def _optional_str(obj, key, label):
    value = obj.get(key)
    if value is not None and not isinstance(value, str):
        raise MountsInvalid(f"config_validation: {label}.{key} must be text")
    return value


def _server_label(server):
    """A dotted server name is matched on its first label, so node001 and
    node001.cluster both name node001."""
    return server.split('.', 1)[0]


def _validate_client(client, label):
    if not isinstance(client, dict):
        raise MountsInvalid(f"config_validation: {label} must be an object")
    _unknown_key(client, _ALLOWED_CLIENT, label)
    to = client.get("to")
    if not isinstance(to, str) or to == "":
        raise MountsInvalid(f"config_validation: {label}.to is required")
    _optional_str(client, "options", label)
    _optional_str(client, "comment", label)


def _validate_export(export, label, mount_type, server, node_names):
    if not isinstance(export, dict):
        raise MountsInvalid(f"config_validation: {label} must be an object")
    _unknown_key(export, _ALLOWED_EXPORT, label)
    if mount_type != "nfs":
        raise MountsInvalid(
            f"config_validation: {label} is only valid on an nfs entry, not {mount_type}")
    if not server:
        raise MountsInvalid(f"config_validation: {label} needs a server to render on")
    if server not in RESERVED_SERVERS and node_names is not None \
            and _server_label(server) not in node_names:
        raise MountsInvalid(
            f"config_validation: {label}: server '{server}' is not a controller or a node, "
            "so the export could never render")
    _optional_str(export, "options", label)
    _optional_str(export, "comment", label)
    clients = export.get("clients")
    if clients is not None:
        if not isinstance(clients, list):
            raise MountsInvalid(f"config_validation: {label}.clients must be a list")
        for cidx, client in enumerate(clients):
            _validate_client(client, f"{label}.clients[{cidx}]")


def _validate_mount(mount, idx, node_names):
    label = f"mounts[{idx}]"
    if not isinstance(mount, dict):
        raise MountsInvalid(f"config_validation: {label} must be an object")
    _unknown_key(mount, _ALLOWED_MOUNT, label)
    path = mount.get("path")
    if not isinstance(path, str) or path == "":
        raise MountsInvalid(f"config_validation: {label}.path is required")
    if not path.startswith("/"):
        raise MountsInvalid(f"config_validation: {label}.path must be absolute: {path}")
    mount_type = _optional_str(mount, "type", label) or "nfs"
    if mount_type not in _TYPES:
        raise MountsInvalid(
            f"config_validation: {label}.type unsupported: '{mount_type}' "
            f"(allowed: {', '.join(sorted(_TYPES))})")
    state = _optional_str(mount, "state", label)
    if state is not None and state not in _STATES:
        raise MountsInvalid(
            f"config_validation: {label}.state unsupported: '{state}' "
            f"(allowed: {', '.join(sorted(_STATES))})")
    for key in ("server", "source", "options", "owner", "group", "comment"):
        _optional_str(mount, key, label)
    mode = _optional_str(mount, "mode", label)
    if mode is not None and (len(mode) not in (3, 4) or not set(mode) <= _MODE_DIGITS):
        raise MountsInvalid(f"config_validation: {label}.mode must be octal digits, got '{mode}'")
    export = mount.get("export")
    if export is not None:
        _validate_export(export, f"{label}.export", mount_type, mount.get("server"), node_names)
    return path, mount_type, export is not None


def validate(raw, node_names=None):
    """Validate a mounts JSON document (bytes or str). Raises :class:`MountsInvalid`
    with an operator-facing reason, or returns None when the document passes.
    An empty document is accepted: nothing declared is a legal state.

    node_names is the set of node names an export block may name as its server,
    beside the reserved words. None skips that one check."""
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8", "strict")
    if raw is None or raw.strip() == "":
        return
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as err:
        raise MountsInvalid(f"config_validation: not valid JSON: {err}")
    if not isinstance(doc, dict):
        raise MountsInvalid("config_validation: top-level: must be an object with a 'mounts' list")
    _unknown_key(doc, _ALLOWED_TOP, "top-level")
    if doc.get("version") != SCHEMA_VERSION:
        raise MountsInvalid(
            f"config_validation: version must be {SCHEMA_VERSION}, got: {doc.get('version')!r}")
    _optional_str(doc, "comment", "top-level")
    mounts = doc.get("mounts")
    if not isinstance(mounts, list):
        raise MountsInvalid("config_validation: mounts must be an array")
    seen_paths = {}
    seen_exports = {}
    for idx, mount in enumerate(mounts):
        path, mount_type, exported = _validate_mount(mount, idx, node_names)
        if path in seen_paths:
            raise MountsInvalid(
                f"config_validation: mounts[{idx}].path '{path}' is already declared "
                f"by mounts[{seen_paths[path]}]")
        seen_paths[path] = idx
        if exported:
            # one line per exported directory is what /etc/exports allows
            exported_dir = (mount["server"], mount.get("source") or path)
            if exported_dir in seen_exports:
                raise MountsInvalid(
                    f"config_validation: mounts[{idx}] exports {exported_dir[1]} from "
                    f"{exported_dir[0]} which mounts[{seen_exports[exported_dir]}] already exports")
            seen_exports[exported_dir] = idx


def validate_b64(value, node_names=None):
    """Validate a mounts document as it travels in a request: base64 JSON. A value
    that is not base64 is refused, since nothing downstream can read it either."""
    try:
        raw = b64decode(value, validate=True).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        raise MountsInvalid("config_validation: mounts must be base64-encoded JSON")
    validate(raw, node_names)


# --- what a document means for one machine ----------------------------------------
# The renderers below are pure as well: they take the names a machine answers to,
# the addresses its reserved servers resolve to and the networks a client may name,
# and answer which entries it mounts and which it exports. Reading those from the
# database and writing the files is the render module's business.

def entries_from_b64(value):
    """The entries of a stored document. Nothing stored is no entries; a stored
    document passed validation when it was stored."""
    if not value:
        return []
    raw = b64decode(value).decode('utf-8')
    if not raw.strip():
        return []
    return json.loads(raw).get('mounts') or []


def mount_type(entry):
    """The filesystem type of an entry, with the alias folded away."""
    mtype = entry.get('type') or 'nfs'
    return 'gpfs' if mtype == 'mmfs' else mtype


def server_matches(server, names):
    """Whether an entry's server is one of the names this machine answers to. An
    absent server is the cluster share at this path, which the controller serves."""
    if not server:
        return 'controller' in names
    if server in RESERVED_SERVERS:
        return server in names
    return server in names or _server_label(server) in names


def serves(entry, names):
    """Whether this machine renders an export line for the entry."""
    return mount_type(entry) == 'nfs' and entry.get('export') is not None \
        and server_matches(entry.get('server'), names)


def mounts(entry, names):
    """Whether this machine carries the entry in its fstab. A manual entry is a
    mountpoint and nothing else. A machine mounts what it serves only as a
    cross-mount: the exported directory differs from the mountpoint, so the
    mountpoint is reached through the server like everywhere else. Same
    directory, nothing to mount, it is already there."""
    if mount_type(entry) == 'manual':
        return True
    if not server_matches(entry.get('server'), names):
        return True
    source = entry.get('source')
    return bool(source) and source != entry['path']


def resolve_server(server, addresses):
    """The device host for a mount: a reserved word becomes the address the caller
    supplies for it, an absent server is the controller, anything else passes."""
    if not server:
        return addresses.get('controller') or 'controller'
    if server in RESERVED_SERVERS:
        return addresses.get(server) or server
    return server


def client_specs(to, networks):
    """The client specifications one `to` stands for: every family a Luna network
    has, or the literal as written."""
    if to in networks:
        return list(networks[to])
    return [to]
