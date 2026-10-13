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

SCOPE. This module mirrors the node-side validator -- luna2-client
advanced-partitioner internal/config/v2, the v2.Parse + Config.ValidateRaw pair
that lpart-storage-prepare and lpart-storage-check run, as of luna2-client
3a26667 -- rule for rule, for every rule that can be decided from the document
alone. In practice that is all of Parse/ValidateRaw:

  * grammar: JSON validity, no repeated object keys (internal/jsonstrict:
    compared case-insensitively, at any depth), allowed keys per object,
    required fields, enums, the exact JSON types encoding/json accepts for each
    field, a top-level comment that is a string;
  * topology: the OS-set raid policy (raid none/0/1/10 on 1, 2 or 4 active
    drives, parity raid refused), per-level member counts (raidlevel
    AllowsCount), spares (redundant levels only, active = members - spares),
    no negative count, save/persistent/bootloader placement, the OS-set root +
    ESP requirement;
  * volumes: fs/provider combinations, size grammar, the lvm size requirement,
    at most one lvm 100%, direct partitions only on raid=none, the
    100%-partition-last rule in builder order;
  * names: charset, reserved /dev entries and kernel device names, the
    22-character set-name cap, md-name fold and device-mapper prefix
    collisions, LVM-reserved LV names, unique volume names;
  * mountpoints: canonical form, no /, /boot or /boot/efi on a data set,
    uniqueness across the layout;
  * devices: path form (no blank or control character, clean, not /dev or
    /dev/disk, /dev/disk/<kind>/<name>), path style (by-uuid, by-label,
    by-partuuid, by-partlabel, by-diskseq, device-mapper refused; one style
    per set) and literal cross-set exclusivity;
  * match: min_size/max_size parsed exactly as diskresolve.ParseMatch,
    int64 overflow refused.

Each function names the Go function it mirrors; error messages keep Go's
wording ("config_validation: ...").

LEFT TO THE NODE: everything that needs the node's disks or its install mode
-- discover resolution against real disks, device existence and size, aliases
of one disk under different path styles, the disk-fit preflight, degraded
assembly, "a diskful mode needs an os set".

DESIGN INVARIANT -- soundness (no false rejections): daemon-reject =>
node-reject. A false rejection blocks a valid layout, which is worse than a
missed one. Getting there takes more than copying the rules, because Python
reads JSON differently from Go:

  * objects are read with object_pairs_hook, so repeated keys are seen (a
    dict keeps only the last) and refused as jsonstrict refuses them, keys
    lower-cased rune by rune as strings.ToLower does;
  * before that, the document is decoded the way encoding/json decodes it into
    the v2 structs, because v2.Parse runs first and its type errors are the
    node's first word: repeated keys merge into the struct, struct fields
    also match keys case-insensitively (Go's fold, including U+017F and
    U+212A), null leaves a field untouched, number literals are kept verbatim
    (1.0 and 2e0 are not ints, a bool is never a number, a 5000-digit literal
    is just text), invalid surrogates become U+FFFD; the raw-key checks see
    what Go's map[string]json.RawMessage sees (the last value of each key);
  * Go's helpers are ported, not approximated: strings.TrimSpace's Unicode
    white space (not str.strip()), path.Clean (not posixpath.normpath), RE2's
    end-of-text '$' (not Python's newline-tolerant '$');
  * a document nested deeper than Python's parser follows (about 1000 levels)
    is refused only because no layout the node accepts nests deeper than
    5 levels; anything this module cannot judge (an internal error) is
    accepted, and the node decides.

The invariant is checked by differential testing against the Go validator (the
repo's layouts and the layouts its Go tests parse, the lab matrix layouts, and
a generated mutation corpus): zero daemon-only rejections.

Stdlib-only and side-effect-free so it can be unit-tested in isolation.
"""

import json
import re

SCHEMA_VERSION = 2


class DisklayoutInvalid(ValueError):
    """A disklayout failed daemon-side validation. Message is operator-facing."""


class _DecodeError(Exception):
    """encoding/json would fail to decode the document into the v2 structs, so
    v2.Parse returns an error and the node refuses the layout."""


def _fail(msg):
    raise DisklayoutInvalid("config_validation: " + msg)


# --------------------------------------------------------------------------
# JSON, read the way Go's encoding/json reads it
# --------------------------------------------------------------------------

class _Num:
    """A JSON number, kept as its literal text. encoding/json decodes an int
    field with strconv.ParseInt on the literal, so 2.0 and 2e0 are not ints."""
    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text


class _Obj:
    """A JSON object as its (key, value) pairs in document order, duplicate
    keys kept (a Python dict would silently keep only the last)."""
    __slots__ = ("pairs",)

    def __init__(self, pairs):
        self.pairs = pairs

    def last(self):
        """The object as map[string]json.RawMessage sees it: last value wins."""
        return dict(self.pairs)


_JSON_NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?\Z")
_JSON_INT_RE = re.compile(r"-?[0-9]+\Z")
_SURROGATE_RE = re.compile("[\ud800-\udfff]")
_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1


def _go_string(text):
    """Go replaces an unpaired \\uD800-\\uDFFF escape (and every invalid UTF-8
    byte) with U+FFFD; Python's json keeps the lone surrogate."""
    if _SURROGATE_RE.search(text):
        return _SURROGATE_RE.sub("\ufffd", text)
    return text


def _number(text):
    # The C scanner only hands over ASCII literals; the pure-Python fallback
    # matches \d (any Unicode digit), which Go refuses as invalid JSON.
    if not _JSON_NUMBER_RE.match(text):
        raise ValueError(f"invalid number literal {text!r}")
    return _Num(text)


def _constant(name):
    raise ValueError(f"invalid character in literal {name}")  # NaN/Infinity are not JSON


def _object(pairs):
    return _Obj([(_go_string(k), v) for k, v in pairs])


def _parse_json(text):
    return json.loads(text, object_pairs_hook=_object, parse_int=_number,
                      parse_float=_number, parse_constant=_constant)


def _raw_text(value, depth=0):
    """The JSON text of a value, for messages that quote the raw document
    (depth-bounded: a message never needs a deeply nested value in full)."""
    if depth > 8 and isinstance(value, (list, _Obj)):
        return "[...]" if isinstance(value, list) else "{...}"
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, _Num):
        return value.text
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_raw_text(v, depth + 1) for v in value) + "]"
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + _raw_text(v, depth + 1)
                          for k, v in value.pairs) + "}"


def _json_kind(value):
    """UnmarshalTypeError.Value: the JSON type word encoding/json reports."""
    if value is True or value is False:
        return "bool"
    if isinstance(value, _Num):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _type_error(value, struct, path, gotype, literal=False):
    kind = _json_kind(value)
    if literal and isinstance(value, _Num):
        kind = "number " + value.text
    if struct:
        return _DecodeError(
            f"json: cannot unmarshal {kind} into Go struct field {struct}.{path} of type {gotype}")
    return _DecodeError(f"json: cannot unmarshal {kind} into Go value of type {gotype}")


def _go_fold(key):
    """encoding/json foldName for matching keys to the ASCII field names: ASCII
    upper-cased, U+017F (long s) -> S, U+212A (Kelvin) -> K. Every other
    non-ASCII rune folds to a non-ASCII rune, so it can never match a field."""
    out = []
    for char in key:
        if char < "\x80":
            out.append(char.upper())
        elif char == "\u017f":
            out.append("S")
        elif char == "\u212a":
            out.append("K")
        else:
            out.append(char)
    return "".join(out)


class _Slice:
    """A decoded Go slice ([]string devices, []Volume volumes)."""
    __slots__ = ("items",)

    def __init__(self, items=()):
        self.items = list(items)


class _Spec:
    """A v2 struct type (types.go): JSON field name -> (decoder, zero value)."""

    def __init__(self, name, fields):
        self.name = name
        self.fields = fields
        self.folded = {_go_fold(k): k for k in fields}

    def zero(self):
        return {k: zero() for k, (_, zero) in self.fields.items()}

    def field(self, key):
        """Exact field name first, then encoding/json's case-insensitive match."""
        if key in self.fields:
            return key
        return self.folded.get(_go_fold(key))

    def decode_into(self, target, value, path):
        """d.object into a struct: known keys decode in document order into the
        existing value (so a duplicate key merges), unknown keys are skipped."""
        for key, val in value.pairs:
            name = self.field(key)
            if name is None:
                continue
            target[name] = self.fields[name][0](target[name], val, self.name,
                                                f"{path}.{name}" if path else name)
        return target


def _dec_string(cur, value, struct, path):
    if value is None:
        return cur  # null leaves a string untouched
    if isinstance(value, str):
        return _go_string(value)
    raise _type_error(value, struct, path, "string")


def _dec_int(cur, value, struct, path):
    if value is None:
        return cur
    if isinstance(value, _Num) and _JSON_INT_RE.match(value.text) and len(value.text) <= 20:
        number = int(value.text)
        if _INT64_MIN <= number <= _INT64_MAX:
            return number
    raise _type_error(value, struct, path, "int", literal=True)


def _dec_bool(cur, value, struct, path):
    if value is None:
        return cur
    if value is True or value is False:
        return value
    raise _type_error(value, struct, path, "bool")


# types.go bootloaderSpellings: exact, case-sensitive.
_BOOTLOADER_SPELLINGS = {
    "first": "first", "grub": "first", "yes": "first", "true": "first",
    "last": "last",
    "none": "none", "no": "none", "false": "none",
}


def _dec_bootloader(cur, value, struct, path):
    """types.go Bootloader.UnmarshalJSON."""
    if value is None:
        return cur  # "null": absent, per the Unmarshaler convention
    if value is True:
        return "first"
    if value is False:
        return "none"
    if isinstance(value, str):
        text = _go_string(value)
        return _BOOTLOADER_SPELLINGS.get(text, text)
    raise _DecodeError(f"bootloader must be a string or a boolean, got {_raw_text(value)}")


def _dec_tags(cur, value, struct, path):
    # Match.Tags []string: only the types matter, the tags are never validated.
    if value is None:
        return None
    if not isinstance(value, list):
        raise _type_error(value, struct, path, "[]string")
    for item in value:
        if item is not None and not isinstance(item, str):
            raise _type_error(item, struct, path, "string")
    return None


def _dec_pointer(spec_ref):
    """*Match / *Origin: null sets nil; an object decodes into the existing
    struct when there is one (so a duplicate key merges), else a new one."""
    def dec(cur, value, struct, path):
        spec = spec_ref()
        if value is None:
            return None
        if not isinstance(value, _Obj):
            raise _type_error(value, struct, path, "v2." + spec.name)
        return spec.decode_into(cur if cur is not None else spec.zero(), value, path)
    return dec


def _dec_slice(elem_dec, elem_zero, gotype):
    """d.array into a slice: an existing element is decoded INTO (not reset),
    which is how a repeated "volumes" key merges into the earlier elements.

    A slot past the previous length but inside the previous backing array
    would show a stale element whose content depends on Go's allocator. It is
    decoded onto a zero element here; that is exact for every decode error
    (they depend on the JSON value only), and the content itself is never
    looked at: the same field filled twice in one object means a repeated key
    (jsonstrict refuses it) or a key that only folds to the field name (the
    object's unknown-key check refuses it), and both run before any check
    reads that object's values."""
    def dec(cur, value, struct, path):
        if value is None:
            return _Slice()
        if not isinstance(value, list):
            raise _type_error(value, struct, path, gotype)
        out = []
        for i, item in enumerate(value):
            base = cur.items[i] if i < len(cur.items) else elem_zero()
            out.append(elem_dec(base, item, struct, path))
        return _Slice(out)
    return dec


def _dec_volume(base, item, struct, path):
    if item is not None and not isinstance(item, _Obj):
        raise _type_error(item, struct, path, "v2.Volume")
    if item is None:
        return base  # null into a struct is ignored
    return _VOLUME.decode_into(dict(base), item, path)


_VOLUME = _Spec("Volume", {
    "name": (_dec_string, str), "mountpoint": (_dec_string, str),
    "fs": (_dec_string, str), "size": (_dec_string, str),
    "provider": (_dec_string, str), "options": (_dec_string, str),
    "clear_uefi_nvram": (_dec_bool, bool), "comment": (_dec_string, str),
})
_MATCH = _Spec("Match", {
    "tags": (_dec_tags, lambda: None), "min_size": (_dec_string, str),
    "max_size": (_dec_string, str), "model": (_dec_string, str),
})
_ORIGIN = _Spec("Origin", {
    "from": (_dec_string, str), "at": (_dec_string, str),
    "by": (_dec_string, str), "host": (_dec_string, str),
})
_SET = _Spec("Set", {
    "name": (_dec_string, str), "role": (_dec_string, str),
    "selection": (_dec_string, str), "raid": (_dec_string, str),
    "count": (_dec_int, int), "spares": (_dec_int, int),
    "match": (_dec_pointer(lambda: _MATCH), lambda: None),
    "devices": (_dec_slice(_dec_string, str, "[]string"), _Slice),
    "save": (_dec_bool, bool), "persistent": (_dec_bool, bool),
    "bootloader": (_dec_bootloader, str),
    "origin": (_dec_pointer(lambda: _ORIGIN), lambda: None),
    "volumes": (_dec_slice(_dec_volume, _VOLUME.zero, "[]v2.Volume"), _Slice),
    "comment": (_dec_string, str),
})


def _decode_sets(value):
    """json.Unmarshal(sets, &c.Sets) into a nil slice: every element is
    decoded into a fresh zero Set."""
    sets = []
    for item in value:
        if item is None:
            sets.append(_SET.zero())
        elif isinstance(item, _Obj):
            sets.append(_SET.decode_into(_SET.zero(), item, ""))
        else:
            raise _type_error(item, "", "", "v2.Set")
    return sets


def _raw_object(value):
    """objectFromRaw: an object's last-wins key map; null is an empty map. (A
    non-object never gets here: the typed decode has refused it already.)"""
    if isinstance(value, _Obj):
        return value.last()
    return {}


# --------------------------------------------------------------------------
# Go helpers, ported
# --------------------------------------------------------------------------

# unicode.IsSpace / the White_Space property: what strings.TrimSpace trims.
# NOT str.strip(), which also strips U+001C..U+001F.
_GO_SPACE = ("\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
             "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000")


def _go_trim_space(text):
    return text.strip(_GO_SPACE)


def _go_path_clean(path):
    """path.Clean (filepath.Clean on Linux). posixpath.normpath differs: it
    keeps a leading '//'."""
    if path == "":
        return "."
    rooted = path.startswith("/")
    out = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if out and out[-1] != "..":
                out.pop()
            elif not rooted:
                out.append("..")
            continue
        out.append(part)
    joined = "/".join(out)
    if rooted:
        return "/" + joined
    return joined or "."


def _q(text):
    """fmt's %q (strconv.Quote), close enough for messages."""
    out = ['"']
    for char in text:
        code = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif 0x20 <= code < 0x7f:
            out.append(char)
        elif char in "\a\b\f\n\r\t\v":
            out.append({"\a": "\\a", "\b": "\\b", "\f": "\\f", "\n": "\\n",
                        "\r": "\\r", "\t": "\\t", "\v": "\\v"}[char])
        elif code < 0x80:
            out.append(f"\\x{code:02x}")
        elif char.isprintable():
            out.append(char)
        elif code < 0x10000:
            out.append(f"\\u{code:04x}")
        else:
            out.append(f"\\U{code:08x}")
    out.append('"')
    return "".join(out)


def _wrap_int64(value):
    """Go int64 arithmetic wraps silently (only a message uses it now)."""
    value &= (1 << 64) - 1
    return value - (1 << 64) if value >= (1 << 63) else value


def _parse_int64(digits):
    """strconv.ParseInt(digits, 10, 64) for an all-digit string; None when it
    is out of range. (int() on more than 4300 digits raises in Python >= 3.9.14.)"""
    significant = digits.lstrip("0") or "0"
    if len(significant) > 19:
        return None
    number = int(significant)
    return number if number <= _INT64_MAX else None


# --------------------------------------------------------------------------
# internal/raidlevel
# --------------------------------------------------------------------------

_RAID_LEVELS = ("none", "0", "1", "5", "6", "10")
_RAID_MIN = {"none": 1, "0": 2, "1": 2, "5": 4, "6": 5, "10": 4}   # MinDisks
_RAID_MAX = {"none": 1, "0": 0, "1": 2, "5": 0, "6": 0, "10": 0}   # MaxDisks, 0 = unbounded


def _allows_count(raid, count):
    """raidlevel Raid.AllowsCount."""
    if count < _RAID_MIN[raid]:
        return False
    if _RAID_MAX[raid] and count > _RAID_MAX[raid]:
        return False
    if raid == "10" and count % 2 != 0:
        return False
    return True


def _count_spec(raid):
    """validate.go countSpec."""
    low, high = _RAID_MIN[raid], _RAID_MAX[raid]
    if high == 0:
        return f"at least {low} device(s)"
    if low == high:
        return f"exactly {low} device(s)"
    return f"{low}-{high} device(s)"


# --------------------------------------------------------------------------
# validate_names.go
# --------------------------------------------------------------------------

_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")  # nameRE, used with fullmatch (RE2 '$')

_RESERVED_SET_NAMES = frozenset((
    ".", "..", "block", "bsg", "bus", "char", "cpu", "disk", "dma_heap", "dri",
    "fd", "hugepages", "infiniband", "input", "lvm", "mapper", "md", "mqueue",
    "net", "pts", "raw", "serial", "shm", "snd", "usb", "vfio",
    "autofs", "btrfs-control", "console", "core", "cpu_dma_latency", "cuse",
    "full", "fuse", "hpet", "initctl", "kmsg", "kvm", "log", "loop-control",
    "mcelog", "mem", "nvme-fabrics", "nvram", "null", "port", "ppp", "ptmx",
    "random", "rfkill", "rtc", "snapshot", "stderr", "stdin", "stdout", "tty",
    "udmabuf", "uhid", "uinput", "urandom", "userfaultfd", "vga_arbiter",
    "vhost-net", "vhost-vsock", "vsock", "watchdog", "zero",
))

_KERNEL_DEV_NAME_RE = re.compile(  # kernelDevNameRE, used with fullmatch
    r"((sd|vd|xvd)[a-z]{1,2}|nvme[0-9]+(n[0-9]+)?|md[0-9]+|dm-[0-9]+|loop[0-9]+|"
    r"sr[0-9]+|sg[0-9]+|nbd[0-9]+|ram[0-9]+|zram[0-9]+|mmcblk[0-9]+|"
    r"tty([A-Z]+[0-9]*|[0-9]+)|vcs[au]?[0-9]*|hidraw[0-9]+|rtc[0-9]+|watchdog[0-9]+|tpm(rm)?[0-9]+)"
    r"(p?[0-9]+)?")

_LVM_RESERVED_LV_PREFIXES = ("snapshot", "pvmove")
_LVM_RESERVED_LV_SUBSTRINGS = (
    "_cdata", "_cmeta", "_corig", "_cpool", "_cvol", "_imeta", "_iorig",
    "_mimage", "_mlog", "_pmspare", "_rimage", "_rmeta", "_tdata", "_tmeta",
    "_vdata", "_vorigin", "_wcorig",
)

_MAX_SET_NAME_LEN = 22


def _set_ref(idx, name):
    return f"sets[{idx}] (set {_q(name)})"


def _vol_ref(set_idx, set_name, vol_idx, vol_name):
    return f"sets[{set_idx}].volumes[{vol_idx}] (set {_q(set_name)}, volume {_q(vol_name)})"


def _md_name(name):
    """accessors.go Set.MDName: non-alphanumerics fold to '_', trailing '_' trimmed."""
    folded = "".join(c if ("a" <= c <= "z" or "A" <= c <= "Z" or "0" <= c <= "9") else "_"
                     for c in name)
    return folded.rstrip("_")


def _dm_mapper_name(vg, lv):
    """validate_names.go dmMapperName."""
    return vg.replace("-", "--") + "-" + lv.replace("-", "--")


def _validate_set_name(idx, name):
    """validate_names.go validateSetName."""
    ref = _set_ref(idx, name)
    if not _NAME_RE.fullmatch(name):
        _fail(f"{ref}: name may only contain letters, digits, '_' and '-' (it becomes the LVM "
              "volume group, the md array name and a path under /dev)")
    if name.startswith("-"):
        _fail(f"{ref}: name must not start with '-' (LVM refuses such a volume group name)")
    if len(name) > _MAX_SET_NAME_LEN:
        _fail(f"{ref}: name is {len(name)} characters, at most {_MAX_SET_NAME_LEN} are allowed: "
              "the set's md arrays (/dev/md/<name>, <name>-efi, <name>-boot) must fit mdadm's "
              "32-character array name together with the \"any:\" homehost prefix")
    if _md_name(name) == "":
        _fail(f"{ref}: name must contain a letter or digit (the md array name /dev/md/<name> is "
              "the name with every other character folded to '_' and trailing '_' trimmed, "
              "which leaves nothing)")
    if name in _RESERVED_SET_NAMES or _KERNEL_DEV_NAME_RE.fullmatch(name):
        _fail(f"{ref}: name is reserved: /dev/{name} exists on the installer, and cleanup removes "
              "/dev/<set name> (rm -rf) while LVM puts the volume group there; choose another "
              "set name")


def _validate_volume_name(set_idx, set_name, vol_idx, name, lvm):
    """validate_names.go validateVolumeName."""
    ref = _vol_ref(set_idx, set_name, vol_idx, name)
    if not _NAME_RE.fullmatch(name):
        _fail(f"{ref}: name may only contain letters, digits, '_' and '-' (it becomes the LV "
              "name or the GPT partition label)")
    if name.startswith("-"):
        _fail(f"{ref}: name must not start with '-' (lvcreate refuses such a logical volume name)")
    if not lvm:
        return
    if name.startswith("_"):
        _fail(f"{ref}: an lvm volume name must not start with '_' (LVM reserves it for internal "
              "volumes)")
    for prefix in _LVM_RESERVED_LV_PREFIXES:
        if name.startswith(prefix):
            _fail(f"{ref}: lvm volume names starting with {_q(prefix)} are reserved by LVM "
                  "(lvcreate refuses them)")
    for sub in _LVM_RESERVED_LV_SUBSTRINGS:
        if sub in name:
            _fail(f"{ref}: lvm volume names containing {_q(sub)} are reserved by LVM for "
                  "internal sub-volumes (lvcreate refuses them)")


def _validate_volume_names_unique(s, idx):
    """validate_names.go Set.validateVolumeNamesUnique."""
    seen = {}
    for j, vol in enumerate(s["volumes"].items):
        if vol["name"] in seen:
            _fail(f"{_set_ref(idx, s['name'])}: volume name {_q(vol['name'])} is used by "
                  f"volumes[{seen[vol['name']]}] and volumes[{j}]; volume names must be unique "
                  "within a set (they are the LV names of the volume group)")
        seen[vol["name"]] = j


def _validate_set_name_collisions(sets):
    """validate_names.go Config.validateSetNameCollisions."""
    by_name, by_md = {}, {}
    for i, s in enumerate(sets):
        name = s["name"]
        if name in by_name:
            _fail(f"sets[{by_name[name]}] and sets[{i}] are both named {_q(name)}; set names must "
                  "be unique (each is a volume group, an md array and a cleanup target)")
        by_name[name] = i
        md = _md_name(name)
        if md in by_md:
            prev = by_md[md]
            _fail(f"set names {_q(sets[prev]['name'])} (sets[{prev}]) and {_q(name)} (sets[{i}]) "
                  f"both map to the md array /dev/md/{md} (non-alphanumerics fold to '_'); "
                  "rename one of them")
        by_md[md] = i
    for i, a_set in enumerate(sets):
        prefix = a_set["name"] + "-"
        for j, b_set in enumerate(sets):
            if i == j:
                continue
            for vol in b_set["volumes"].items:
                if vol["provider"] != "lvm":
                    continue
                mapper = _dm_mapper_name(b_set["name"], vol["name"])
                if mapper.startswith(prefix):
                    _fail(f"set names {_q(a_set['name'])} (sets[{i}]) and {_q(b_set['name'])} "
                          f"(sets[{j}]) clash: cleanup of set {_q(a_set['name'])} removes every "
                          f"/dev/mapper/{prefix}* entry, which includes /dev/mapper/{mapper} "
                          f"(volume {_q(vol['name'])} of set {_q(b_set['name'])}); rename one of "
                          "the sets")


# --------------------------------------------------------------------------
# validate_sizes.go and diskresolve.ParseMatch
# --------------------------------------------------------------------------

_SIZE_REST = "100%"
_VOLUME_SIZE_RE = re.compile(r"([0-9]+)([KMGT])")                 # volumeSizeRE (fullmatch)
_MATCH_SIZE_RE = re.compile(r"([0-9]+)[\t\n\f\r ]*([TGMK]?)B?")   # diskresolve sizeRE; RE2 \s is ASCII
_UNITS = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}


class _SizeError(Exception):
    pass


def _parse_volume_size(size):
    """validate_sizes.go parseVolumeSize. Returns nothing; raises _SizeError."""
    if size == _SIZE_REST:
        return
    match = _VOLUME_SIZE_RE.fullmatch(size)
    if not match:
        raise _SizeError(
            f"size {_q(size)} is not valid: use \"100%\" (the rest of the disk or volume group) "
            "or a whole number with a K, M, G or T suffix, e.g. 600M or 20G (no decimals, other "
            "percentages, \"GB\" suffixes or bare numbers)")
    number = _parse_int64(match.group(1))
    if number is None:
        raise _SizeError(f"size {_q(size)} is too large")
    if number == 0:
        raise _SizeError(f"size {_q(size)} must be greater than zero")
    if number > _INT64_MAX // _UNITS[match.group(2)]:
        raise _SizeError(f"size {_q(size)} is too large")


def _parse_match_size(raw):
    """diskresolve.ParseSize: TrimSpace (Unicode), ToUpper, then the regexp;
    a value beyond int64 is refused (since 3a26667; it used to wrap). Every
    non-ASCII rune left after the trim upper-cases to a rune the regexp
    refuses (U+0131 -> I and U+017F -> S included), so any is a parse error."""
    text = _go_trim_space(raw)
    match = _MATCH_SIZE_RE.fullmatch(text.upper()) if text.isascii() else None
    if not match:
        raise _SizeError(f"cannot parse size {_q(raw)}; use a form like 400G, 8T, 512M")
    number = _parse_int64(match.group(1))
    if number is None:
        raise _SizeError(f"cannot parse size {_q(raw)}: strconv.ParseInt: parsing "
                         f"{_q(match.group(1))}: value out of range")
    mult = _UNITS[match.group(2)]
    if number > _INT64_MAX // mult:
        raise _SizeError(f"size {_q(raw)} is too large")
    return number * mult


def _validate_volume_size(set_idx, set_name, vol_idx, vol):
    """validate_sizes.go validateVolumeSize."""
    if vol["provider"] not in ("partition", "lvm"):
        return
    ref = _vol_ref(set_idx, set_name, vol_idx, vol["name"])
    if vol["size"] == "":
        rest = "volume group" if vol["provider"] == "lvm" else "disk"
        _fail(f"{ref}: size is required for provider={vol['provider']} (a fixed size such as "
              f"20G, or \"100%\" for the rest of the {rest})")
    try:
        _parse_volume_size(vol["size"])
    except _SizeError as err:
        _fail(f"{ref}: {err}")


def _validate_match(s, idx):
    """validate_sizes.go Set.validateMatch (via diskresolve.ParseMatch)."""
    match = s["match"]
    if match is None:
        return
    ref = _set_ref(idx, s["name"])
    bounds = {}
    for key in ("min_size", "max_size"):
        bounds[key] = 0
        if match[key] != "":
            try:
                bounds[key] = _parse_match_size(match[key])
            except _SizeError as err:
                _fail(f"{ref}: match.{key}: {err}")
    if 0 < bounds["max_size"] < bounds["min_size"]:
        _fail(f"{ref}: match.min_size {_q(match['min_size'])} is larger than match.max_size "
              f"{_q(match['max_size'])}, so no disk can match")


# --------------------------------------------------------------------------
# validate_layout.go
# --------------------------------------------------------------------------

def _is_boot_mount(mountpoint):
    return mountpoint in ("/boot", "/boot/efi")


def _partition_order(s):
    """validate_layout.go Set.partitionOrder (messages only)."""
    parts = []
    vols = s["volumes"].items

    def add(vol):
        parts.append(f"{vol['name']} ({vol['mountpoint']}, {vol['size']})")
    if s["role"] == "os":
        for mountpoint in ("/boot/efi", "/boot"):
            for vol in vols:
                if vol["provider"] == "partition" and vol["mountpoint"] == mountpoint:
                    add(vol)
                    break
    generic = lvm = 0
    for vol in vols:
        if vol["provider"] == "lvm":
            lvm += 1
        elif vol["provider"] == "partition" and not _is_boot_mount(vol["mountpoint"]):
            generic += 1
            add(vol)
    if lvm > 0 or (s["role"] == "data" and generic == 0):
        parts.append("lvm storage (rest of disk)")
    return " -> ".join(parts)


def _validate_partition_order(s, idx):
    """validate_layout.go Set.validatePartitionOrder."""
    ref = _set_ref(idx, s["name"])
    vols = s["volumes"].items
    generic, lvm_names = [], []
    for j, vol in enumerate(vols):
        if vol["provider"] == "lvm":
            lvm_names.append(_q(vol["name"]))
        elif vol["provider"] == "partition" and _is_boot_mount(vol["mountpoint"]):
            if s["role"] == "os" and vol["size"] == _SIZE_REST:
                _fail(f"{_vol_ref(idx, s['name'], j, vol['name'])}: the {vol['mountpoint']} "
                      "partition needs a fixed size, not 100%: the builder creates it ahead of "
                      f"every other partition (partition order: {_partition_order(s)})")
        elif vol["provider"] == "partition":
            generic.append(j)
    if not generic:
        return
    if s["raid"] != "none":
        _fail(f"{ref}: direct partition volumes require raid=none (volume "
              f"{_q(vols[generic[0]]['name'])} is provider=partition; use provider=lvm on a raid "
              "set)")
    for k, j in enumerate(generic):
        vol = vols[j]
        if vol["size"] != _SIZE_REST:
            continue
        vref = _vol_ref(idx, s["name"], j, vol["name"])
        if k < len(generic) - 1:
            _fail(f"{vref}: size=100% takes the rest of the disk, but direct partition "
                  f"{_q(vols[generic[k + 1]]['name'])} is created after it (partition order: "
                  f"{_partition_order(s)}); only the last direct partition may use 100%")
        if lvm_names:
            _fail(f"{vref}: size=100% takes the rest of the disk, but lvm volume(s) "
                  f"{', '.join(lvm_names)} need a storage partition after the direct partitions "
                  f"(partition order: {_partition_order(s)}); give {_q(vol['name'])} a fixed size")


def _validate_mountpoints(s, idx):
    """validate_layout.go Set.validateMountpoints."""
    for j, vol in enumerate(s["volumes"].items):
        ref = _vol_ref(idx, s["name"], j, vol["name"])
        mountpoint = vol["mountpoint"]
        if mountpoint != "swap" and _go_path_clean(mountpoint) != mountpoint:
            _fail(f"{ref}: mountpoint {_q(mountpoint)} is not in canonical form; write it as "
                  f"{_q(_go_path_clean(mountpoint))}")
        if s["role"] != "data":
            continue
        if mountpoint in ("/boot", "/boot/efi"):
            _fail(f"{ref}: a data set cannot carry {mountpoint}: the builder creates /boot and "
                  "/boot/efi on the os set's disks only (declare it on the os set)")
        if mountpoint == "/":
            _fail(f"{ref}: a data set cannot be mounted at \"/\": the root filesystem belongs to "
                  "the os set (or, on a memboot node, the RAM root)")


def _validate_unique_mountpoints(sets):
    """validate_layout.go Config.validateUniqueMountpoints."""
    seen = {}
    for i, s in enumerate(sets):
        for j, vol in enumerate(s["volumes"].items):
            if vol["mountpoint"] == "swap":
                continue
            ref = f"sets[{i}].volumes[{j}]"
            if vol["mountpoint"] in seen:
                p_set, p_vol, p_ref = seen[vol["mountpoint"]]
                _fail(f"mountpoint {_q(vol['mountpoint'])} is declared twice: set {_q(p_set)} "
                      f"volume {_q(p_vol)} ({p_ref}) and set {_q(s['name'])} volume "
                      f"{_q(vol['name'])} ({ref}); each mountpoint may be used once")
            seen[vol["mountpoint"]] = (s["name"], vol["name"], ref)


# --------------------------------------------------------------------------
# validate.go and accessors.go
# --------------------------------------------------------------------------

_ALLOWED_TOP = ("version", "sets", "comment")
_ALLOWED_SET = ("name", "role", "selection", "raid", "count", "spares", "match", "devices",
                "save", "persistent", "bootloader", "origin", "volumes", "comment")
_ALLOWED_MATCH = ("tags", "min_size", "max_size", "model")
_ALLOWED_ORIGIN = ("from", "at", "by", "host")
_ALLOWED_VOLUME = ("name", "mountpoint", "fs", "size", "provider", "options",
                   "clear_uefi_nvram", "comment")


def _unknown_key(obj, allowed, label):
    """keys.go unknownKey: the first unknown key in lexical (byte) order --
    code-point order is the same order for UTF-8."""
    bad = sorted(k for k in obj if k not in allowed)
    if bad:
        _fail(f"{label}: unknown field '{bad[0]}'")


def _selector_type_of(dev):
    """accessors.go selectorTypeOf."""
    if dev.startswith("/dev/disk/by-id/"):
        return "by_id_paths"
    if dev.startswith("/dev/disk/by-path/"):
        return "physical_paths"
    if dev.startswith("/dev/disk/by-uuid/"):
        return "by_uuid_paths"
    if dev.startswith("/dev/"):
        return "device_paths"
    _fail(f"device path must start with /dev/: {dev}")


def _check_device_path_form(idx, set_name, dev):
    """validate.go checkDevicePathForm: no blank or control character (an ASCII
    rule: NBSP passes), clean form, not /dev or /dev/disk, and a /dev/disk
    link exactly /dev/disk/<kind>/<name>."""
    def bad(why):
        _fail(f"{_set_ref(idx, set_name)}: device {_q(dev)} {why}")
    for char in dev:
        if char <= " " or char == "\x7f":
            bad("contains a blank or control character")
    if _go_path_clean(dev) != dev:
        bad(f"is not a clean path (write it as {_q(_go_path_clean(dev))})")
    if dev in ("/dev", "/dev/disk"):
        bad("is a directory, not a disk")
    if dev.startswith("/dev/disk/"):
        link_dir, found, name = dev[len("/dev/disk/"):].partition("/")
        if not found or name == "" or "/" in name:
            bad(f"must be /dev/disk/{link_dir}/<link name>")


def _check_disk_link_style(idx, set_name, dev):
    """validate.go checkDiskLinkStyle."""
    if not dev.startswith("/dev/disk/"):
        return
    link_dir = dev[len("/dev/disk/"):].split("/", 1)[0]
    if link_dir in ("by-id", "by-path"):
        return
    if link_dir == "by-uuid":
        _fail(f"{_set_ref(idx, set_name)}: device {_q(dev)} is a by-uuid link, which names the "
              "filesystem on the disk, not the disk: partitioning removes it, so the next boot "
              "fails \"device not found\"; use the disk's /dev/disk/by-id or /dev/disk/by-path "
              "link or its kernel name")
    _fail(f"{_set_ref(idx, set_name)}: device {_q(dev)} is a /dev/disk/{link_dir} link, which "
          "does not name the whole disk stably across partitioning and reboots; use the disk's "
          "/dev/disk/by-id or /dev/disk/by-path link or its kernel name")


def _validate_devices_consistent(s, idx):
    """validate.go Set.validateDevicesConsistent (EffectiveDevices = devices,
    whatever the selection)."""
    style = None
    for i, dev in enumerate(s["devices"].items):
        if dev.startswith("/dev/mapper/") or dev.startswith("/dev/dm-"):
            _fail(f"sets[{idx}].devices: device-mapper/multipath path {_q(dev)} is not supported "
                  "as a set device (dm partition naming has no reliable convention); use the "
                  "underlying disk's by-id, by-path, or kernel name")
        _check_device_path_form(idx, s["name"], dev)
        _check_disk_link_style(idx, s["name"], dev)
        this_style = _selector_type_of(dev)
        if i == 0:
            style = this_style
            continue
        if this_style != style:
            _fail(f"sets[{idx}].devices: all paths must use the same style (/dev/..., by-id, "
                  "by-path)")


def _validate_volume(vol, set_idx, vol_idx, raw):
    """validate.go Volume.validate."""
    vpfx = f"sets[{set_idx}].volumes[{vol_idx}]"
    _unknown_key(_raw_object(raw), _ALLOWED_VOLUME, vpfx)
    if vol["name"] == "":
        _fail(f"{vpfx}.name is required")
    if vol["mountpoint"] == "":
        _fail(f"{vpfx}.mountpoint is required")
    fs, provider, mountpoint = vol["fs"], vol["provider"], vol["mountpoint"]
    if fs not in ("vfat", "xfs", "ext4", "swap"):
        if fs == "":
            _fail(f"{vpfx}.fs is required")
        if fs == "tmpfs":
            _fail(f"{vpfx}.fs=tmpfs is reserved for the memboot RAM root and not valid in a "
                  "disklayout")
        _fail(f"{vpfx}.fs unsupported: '{fs}' (allowed: vfat, xfs, ext4, swap)")
    if provider not in ("partition", "lvm"):
        if provider == "":
            _fail(f"{vpfx}.provider is required (partition|lvm)")
        if provider == "memory":
            _fail(f"{vpfx}.provider=memory is reserved for the memboot RAM root and not valid "
                  "in a disklayout")
        if provider == "zfs":
            _fail(f"{vpfx}.provider=zfs is reserved for future implementation")
        _fail(f"{vpfx}.provider unsupported: '{provider}' (allowed: partition, lvm)")
    if mountpoint != "swap" and not mountpoint.startswith("/"):
        _fail(f"{vpfx}.mountpoint must be an absolute path or swap, got: {mountpoint}")
    if provider == "partition":
        if vol["size"] == "":
            _fail(f"{vpfx}.size is required for provider=partition")
        if not ((mountpoint == "/boot/efi" and fs == "vfat")
                or (mountpoint == "swap" and fs == "swap")
                or fs in ("xfs", "ext4", "vfat")):
            _fail(f"{vpfx}: unsupported provider=partition combination mountpoint={mountpoint} "
                  f"fs={fs}")
    if provider == "lvm" and fs not in ("xfs", "ext4", "swap"):
        _fail(f"{vpfx}: lvm volume fs must be xfs, ext4, or swap, got: {fs}")
    if mountpoint == "swap" and fs != "swap":
        _fail(f"{vpfx}: mountpoint=swap requires fs=swap")
    if fs == "swap" and mountpoint != "swap":
        _fail(f"{vpfx}: fs=swap requires mountpoint=swap")


def _validate_set(s, idx, raw):
    """validate.go Set.validate, in Go's order (the first failure is Go's)."""
    pfx = f"sets[{idx}]"
    set_raw = _raw_object(raw)
    _unknown_key(set_raw, _ALLOWED_SET, pfx)
    if "match" in set_raw:
        _unknown_key(_raw_object(set_raw["match"]), _ALLOWED_MATCH, pfx + ".match")
    if "origin" in set_raw:
        _unknown_key(_raw_object(set_raw["origin"]), _ALLOWED_ORIGIN, pfx + ".origin")

    name = s["name"]
    if name == "":
        _fail(f"{pfx}.name is required")
    _validate_set_name(idx, name)
    ref = _set_ref(idx, name)

    role = s["role"]
    if role not in ("os", "data"):
        if role == "":
            _fail(f"{pfx}.role is required")
        _fail(f"{pfx}.role unsupported: '{role}' (allowed: os, data)")

    selection = s["selection"]
    if selection not in ("discover", "manual"):
        if selection == "":
            _fail(f"{pfx}.selection is required (discover|manual)")
        _fail(f"{pfx}.selection unsupported: '{selection}' (allowed: discover, manual)")

    _validate_match(s, idx)

    if s["save"] and selection != "discover":
        _fail(f"{pfx}.save is only valid on a selection=discover set")
    if s["persistent"] and role != "data":
        _fail(f"{ref}: persistent=true is only valid on a role=data set (the os set's root is "
              "rewritten by every osimage install, so it cannot be hands-off)")
    if s["persistent"] and selection != "manual":
        _fail(f"{pfx}: persistent=true requires selection=manual \u2014 a hands-off guarantee "
              "needs pinned devices (use save:true to pin a discovered layout first)")

    if "bootloader" in set_raw:  # the key's presence, whatever its value (null included)
        if s["bootloader"] not in ("first", "last", "none"):
            _fail(f"{pfx}.bootloader unsupported: '{s['bootloader']}' "
                  "(allowed: first, grub, yes, true, last, no, false, none)")
        if role != "os":
            _fail(f"{pfx}.bootloader is valid on the os set only")

    raid = s["raid"]
    if raid == "":
        _fail(f"{pfx}.raid is required (none|0|1|5|6|10)")
    if raid not in _RAID_LEVELS:
        _fail(f"{pfx}.raid unsupported raid {_q(raid)} (allowed: none, 0, 1, 5, 6, 10)")

    spares = s["spares"]
    if spares < 0:
        _fail(f"{pfx}.spares must be >= 0, got: {spares}")
    if spares > 0 and raid in ("none", "0"):
        _fail(f"{ref}: raid={raid} takes no spares, got spares={spares} (a hot spare only "
              "replaces a failed member of a redundant array: raid 1, 5, 6 or 10)")

    if s["count"] < 0:
        _fail(f"{ref}: count={s['count']} must not be negative")
    devices = s["devices"].items
    if selection == "manual":
        active = len(devices) - spares
        if devices and active < 1:
            _fail(f"{ref}: spares={spares} leaves {active} active device(s) of the "
                  f"{len(devices)} in devices[] (devices[] lists every member, spares included)")
    else:
        active = s["count"]

    if role == "os":
        if raid in ("5", "6"):
            _fail(f"{pfx}: raid={raid} is not supported for the OS set -- the OS uses 1, 2 or 4 "
                  "drives with raid none/1/0/10 (parity RAID cannot boot degraded, NB-10); "
                  f"raid{raid} remains available for data sets")
        if active not in (0, 1, 2, 4):
            if spares > 0:
                _fail(f"{ref}: the OS set uses exactly 1, 2 or 4 drives (raid none/1/0/10), got "
                      f"{active} active ({_wrap_int64(active + spares)} devices minus "
                      f"spares={spares})")
            _fail(f"{pfx}: the OS set uses exactly 1, 2 or 4 drives (raid none/1/0/10), got "
                  f"{active}")

    if selection == "manual":
        if not devices:
            _fail(f"{pfx}.devices[] is required for selection=manual")
        if not _allows_count(raid, active):
            if spares > 0:
                _fail(f"{ref}: raid={raid} needs {_count_spec(raid)} active, but devices[] lists "
                      f"{len(devices)} with spares={spares} ({active} active)")
            _fail(f"{pfx}: raid={raid} needs {_count_spec(raid)}, but devices[] lists "
                  f"{len(devices)}")
    elif s["count"] != 0 and not _allows_count(raid, s["count"]):
        _fail(f"{pfx}: raid={raid} needs {_count_spec(raid)}, but count={s['count']}")

    volumes = s["volumes"].items
    if not volumes:
        _fail(f"{pfx}.volumes[] must be non-empty")
    vol_raws = set_raw.get("volumes")
    vol_raws = vol_raws if isinstance(vol_raws, list) else []
    for j, vol in enumerate(volumes):
        _validate_volume(vol, idx, j, vol_raws[j] if j < len(vol_raws) else None)
        _validate_volume_name(idx, name, j, vol["name"], vol["provider"] == "lvm")
        _validate_volume_size(idx, name, j, vol)
    _validate_volume_names_unique(s, idx)
    _validate_mountpoints(s, idx)

    # volumes[].raid (unreachable behind the unknown-key check, kept like Go)
    for vol_raw in vol_raws:
        if isinstance(vol_raw, _Obj) and "raid" in vol_raw.last():
            _fail(f"{pfx}: volumes[].raid is not supported; use the set raid field")

    _validate_partition_order(s, idx)
    if sum(1 for v in volumes if v["provider"] == "lvm" and v["size"] == _SIZE_REST) > 1:
        _fail(f"{pfx}: at most one lvm volume per set may use size=100%")

    if role == "os":
        root_count = sum(1 for v in volumes
                         if v["mountpoint"] == "/" and v["provider"] in ("partition", "lvm"))
        has_esp = any(v["provider"] == "partition" and v["mountpoint"] == "/boot/efi"
                      and v["fs"] == "vfat" for v in volumes)
        if root_count != 1:
            _fail(f"{pfx}: an os set must have exactly one root volume (mountpoint=/ "
                  f"provider=partition|lvm), found: {root_count}")
        if not has_esp:
            _fail(f"{pfx}: an os set must declare a /boot/efi vfat partition (UEFI ESP)")

    _validate_devices_consistent(s, idx)


# Go's simple lowercase mapping (unicode.ToLower) where Python's str.lower()
# differs: U+0130 lower-cases to "i" + U+0307 in Python. (Per-character
# lowering also keeps Python's final-sigma rule out.)
_GO_LOWER_SPECIAL = {"\u0130": "i"}


def _go_lower(text):
    """strings.ToLower, rune by rune."""
    return "".join(_GO_LOWER_SPECIAL.get(c) or (c.lower() if len(c.lower()) == 1 else c)
                   for c in text)


def _jsonstrict_check(doc):
    """internal/jsonstrict Check (3a26667): no object repeats a key, keys
    compared with strings.ToLower, at any depth, the first offender in
    document order, named by its path (top-level, sets[1], sets[1].volumes[0]).
    (Its other rule, data after the document, never gets here: v2.Parse has
    refused it already.)"""
    stack = [(doc, "top-level")]
    while stack:
        node, path = stack.pop()
        if isinstance(node, list):
            stack.extend(reversed([(v, f"{path}[{i}]") for i, v in enumerate(node)]))
        elif isinstance(node, _Obj):
            seen, children = {}, []
            for key, value in node.pairs:
                lowered = _go_lower(key)
                if lowered in seen:
                    # Go walks the earlier keys' values first: they go on top
                    stack.append((_DUPLICATE, (path, seen[lowered], key)))
                    stack.extend(reversed(children))
                    break
                seen[lowered] = key
                children.append((value, key if path == "top-level" else f"{path}.{key}"))
            else:
                stack.extend(reversed(children))
        elif node is _DUPLICATE:
            where, prev, key = path
            if prev == key:
                _fail(f"{where}: key {_q(key)} appears twice")
            _fail(f"{where}: keys {_q(prev)} and {_q(key)} are the same field (JSON keys match "
                  "case-insensitively)")


_DUPLICATE = object()  # marker on _jsonstrict_check's stack

# The deepest a layout the node accepts can nest: top-level {} > sets [] >
# set {} > volumes [] / match {} > volume {} / tags []. Every other position
# takes a scalar (the top-level comment too, since 3a26667).
_MAX_LAYOUT_DEPTH = 5


def _nesting_depth(text):
    """The deepest [ / { nesting of a JSON text, without recursion."""
    depth = deepest = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            deepest = max(deepest, depth)
        elif char in "]}":
            depth -= 1
    return deepest


def _validate_document(text):
    """v2.Parse followed by Config.ValidateRaw."""
    # --- v2.Parse
    try:
        doc = _parse_json(text)
    except RecursionError:
        # Python's parser stops near 1000 levels, Go's at 10000; but no layout
        # the node accepts nests deeper than _MAX_LAYOUT_DEPTH.
        depth = _nesting_depth(text)
        if depth <= _MAX_LAYOUT_DEPTH:
            raise
        _fail(f"the document nests {depth} levels deep; a disklayout nests at most "
              f"{_MAX_LAYOUT_DEPTH} (top-level > sets > set > volumes > volume)")
    except ValueError as err:
        _fail(f"config is not valid JSON: {err}")
    if doc is not None and not isinstance(doc, _Obj):
        _fail(f"config is not valid JSON: json: cannot unmarshal {_json_kind(doc)} into Go value "
              "of type map[string]json.RawMessage")
    top = doc.last() if doc is not None else {}
    version = 0
    if "version" in top:
        try:  # Parse ignores the decode error: a bad value stays 0
            version = _dec_int(0, top["version"], "", "")
        except _DecodeError:
            version = 0
    sets = []
    if isinstance(top.get("sets"), list):
        try:
            sets = _decode_sets(top["sets"])
        except _DecodeError as err:
            _fail(f"config is not valid JSON: sets: {err}")
    # (Parse ignores a top-level "comment" that is no string; ValidateRaw not)

    # --- Config.ValidateRaw
    _jsonstrict_check(doc)
    if "comment" in top and top["comment"] is not None and not isinstance(top["comment"], str):
        _fail("top-level: comment must be a string")  # json.Unmarshal into a string: null is fine
    _unknown_key(top, _ALLOWED_TOP, "top-level")
    if version != SCHEMA_VERSION:
        got = _raw_text(top["version"]) if "version" in top else "null"
        _fail(f"version must be 2, got: {got}")
    if not isinstance(top.get("sets"), list):
        _fail("sets must be an array")
    if not sets:
        _fail("sets[] must be non-empty")
    os_count = sum(1 for s in sets if s["role"] == "os")
    if os_count > 1:
        _fail(f"at most one set may have role=os, found: {os_count}")
    for idx, a_set in enumerate(sets):
        _validate_set(a_set, idx, top["sets"][idx])
    _validate_set_name_collisions(sets)
    _validate_unique_mountpoints(sets)

    # cross-set device exclusivity, literal level (cleanDevicePath)
    seen = {}
    for a_set in sets:
        for dev in a_set["devices"].items:
            key = _go_trim_space(dev)
            if key == "":
                continue
            key = _go_path_clean(key)
            if key in seen:
                _fail(f"device {dev} appears in both set {_q(seen[key])} and set "
                      f"{_q(a_set['name'])} \u2014 a device may belong to exactly one set")
            seen[key] = a_set["name"]


def validate(raw):
    """Validate a disklayout JSON document (bytes or str). Raises
    :class:`DisklayoutInvalid` with an operator-facing reason (Go's wording),
    or returns None when the node's validator would accept the document too.
    An empty/blank document is accepted (no layout declared is a legal node
    state)."""
    if isinstance(raw, (bytes, bytearray)):
        # One U+DC80+byte per invalid byte, folded to U+FFFD like Go does.
        raw = bytes(raw).decode("utf-8", "surrogateescape")
    if raw is None or raw.strip() == "":
        return  # no disklayout declared -- legal
    try:
        _validate_document(raw)
    except DisklayoutInvalid:
        raise
    except Exception:  # pylint: disable=broad-except
        # a bug in this module (or a RecursionError on a document that does
        # not nest deeply): the store must not fail on the daemon's account --
        # that would be a false rejection; the node's validator decides.
        return
