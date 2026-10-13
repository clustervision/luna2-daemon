# This code is part of the TrinityX software suite
# GPL-3.0-or-later

"""
Unit tests for luna2-daemon utils/disklayout.py (the store-time disklayout
validator), parity edition.

Every case below was checked against the node-side Go validator (luna2-client,
v2.Parse + Config.ValidateRaw): ACCEPT cases are layouts the node
accepts -- the daemon must not reject them (soundness) -- and REJECT cases are
layouts the node refuses, with a fragment of Go's message.

Run with pytest from the repository root, or against a deployed module:

    python3 -m pytest tests/unit/test_disklayout_node_parity.py
    DISKLAYOUT=/trinity/local/luna/daemon/utils/disklayout.py python3 -m pytest tests/unit/test_disklayout_node_parity.py
"""

import json
import os
import unittest

if os.environ.get("DISKLAYOUT"):  # a deployed module, e.g. /trinity/local/luna/daemon/utils/disklayout.py
    import importlib.util
    _SPEC = importlib.util.spec_from_file_location("disklayout", os.environ["DISKLAYOUT"])
    dl = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(dl)
else:  # the repository's module (pytest puts daemon/ on the path, see pytest.ini)
    from utils import disklayout as dl

ESP = {"name": "uefi", "mountpoint": "/boot/efi", "fs": "vfat", "provider": "partition", "size": "600M"}
BOOT = {"name": "boot", "mountpoint": "/boot", "fs": "xfs", "provider": "partition", "size": "1G"}
ROOT = {"name": "root", "mountpoint": "/", "fs": "xfs", "provider": "lvm", "size": "100%"}
DATA = {"name": "data", "mountpoint": "/data", "fs": "xfs", "provider": "lvm", "size": "100%"}
ESP_J, ROOT_J, DATA_J = json.dumps(ESP), json.dumps(ROOT), json.dumps(DATA)


def os_set(**over):
    s = {"name": "os", "role": "os", "selection": "discover", "raid": "none", "volumes": [ESP, ROOT]}
    s.update(over)
    return s


def data_set(**over):
    s = {"name": "d", "role": "data", "selection": "manual", "raid": "none",
         "devices": ["/dev/sdz"], "volumes": [DATA]}
    s.update(over)
    return s


def doc(*sets, **top):
    d = {"version": 2, "sets": list(sets)}
    d.update(top)
    return json.dumps(d)


def raw_os(extra="", vols=None):
    """An os set as JSON text, for what json.dumps cannot write (duplicate keys)."""
    vols = vols if vols is not None else ESP_J + "," + ROOT_J
    return ('{"name":"os","role":"os","selection":"discover","raid":"none"%s,"volumes":[%s]}'
            % (extra, vols))


def raw_doc(*sets):
    return '{"version":2,"sets":[%s]}' % ",".join(sets)


def disks(n, style="/dev/sd%s"):
    return [style % chr(ord("a") + i) for i in range(n)]


class Base(unittest.TestCase):
    def accept(self, text):
        try:
            dl.validate(text)
        except dl.DisklayoutInvalid as err:
            self.fail(f"false rejection (the node accepts this layout): {err}\n{text[:300]}")

    def reject(self, text, fragment):
        with self.assertRaises(dl.DisklayoutInvalid) as ctx:
            dl.validate(text)
        msg = str(ctx.exception)
        self.assertTrue(msg.startswith("config_validation: "), msg)
        self.assertIn(fragment, msg)


class TestAccepted(Base):
    """Layouts the node accepts: the daemon must accept them too."""

    def test_blank_documents(self):
        for text in ("", "   ", "\n", None, b""):
            dl.validate(text)

    def test_minimal_os_set(self):
        self.accept(doc(os_set()))

    def test_typical_layouts(self):
        self.accept(doc(os_set(selection="manual", raid="1", devices=disks(2),
                               bootloader="first", volumes=[ESP, BOOT, dict(ROOT, size="20G"),
                                                            {"name": "swap", "mountpoint": "swap", "fs": "swap",
                                                             "provider": "lvm", "size": "4G"}]),
                        data_set(raid="5", spares=1, persistent=True, devices=disks(5, "/dev/vd%s"))))
        self.accept(doc(os_set(selection="manual", raid="10", spares=1,
                               devices=["/dev/disk/by-id/ata-%d" % i for i in range(5)])))
        self.accept(doc(os_set(raid="1", count=2, save=True, match={"tags": ["ssd"], "min_size": "100G",
                                                                    "max_size": "2T", "model": "X"},
                               origin={"from": "discover", "at": "t", "by": "b", "host": "h"},
                               comment="pinned")))

    def test_data_only_layout(self):
        self.accept(doc({"name": "scratch", "role": "data", "selection": "discover",
                         "raid": "6", "count": 5, "spares": 2, "volumes": [DATA]}))

    def test_direct_partitions_on_raid_none(self):
        self.accept(doc(os_set(selection="manual", devices=["/dev/nvme0n1"], volumes=[
            ESP, BOOT, {"name": "swap", "mountpoint": "swap", "fs": "swap", "provider": "partition", "size": "4G"},
            dict(ROOT, provider="partition")])))

    def test_os_drive_counts(self):
        for raid, n in (("none", 1), ("0", 2), ("1", 2), ("0", 4), ("10", 4)):
            self.accept(doc(os_set(selection="manual", raid=raid, devices=disks(n))))
            self.accept(doc(os_set(raid=raid, count=n)))
        # spares come on top of the 1/2/4 active drives
        self.accept(doc(os_set(selection="manual", raid="1", spares=2, devices=disks(4))))

    def test_data_member_counts(self):
        for raid, n in (("5", 4), ("5", 9), ("6", 5), ("10", 6), ("0", 3), ("1", 2)):
            self.accept(doc(data_set(raid=raid, devices=disks(n))))
        self.accept(doc(data_set(raid="1", spares=1, devices=disks(3))))  # 2 active

    def test_bootloader_spellings(self):
        for value in ("first", "grub", "yes", "true", "last", "none", "no", "false", True, False):
            self.accept(doc(os_set(bootloader=value)))
        self.accept(raw_doc(raw_os(',"bootloader":"\\u0066irst"')))

    def test_go_number_semantics(self):
        self.accept(raw_doc(raw_os(',"count":-0')))
        self.accept(raw_doc(raw_os(',"count":null,"spares":null')))
        # the largest int64 is a valid (if unresolvable) discover count
        self.accept(doc({"name": "scratch", "role": "data", "selection": "discover", "raid": "0",
                         "count": 9223372036854775807, "volumes": [DATA]}))

    def test_top_level_comment_string_or_null(self):
        for value in ("x", "", None, "multi\nline \u00e9"):
            self.accept(doc(os_set(), comment=value))

    def test_similar_but_distinct_keys_are_not_repeats(self):
        # strings.ToLower keeps U+017F (long s) and the final sigma apart; the
        # set's unknown-key check is what refuses them (see TestRejected)
        self.accept(doc(os_set(volumes=[ESP, dict(ROOT, comment="\u00e9")]), comment="a\u03a3 a\u03c2"))

    def test_go_string_helpers(self):
        # strings.TrimSpace trims Unicode white space (NBSP, NEL, U+3000) ...
        self.accept(doc(os_set(match={"min_size": "1G\u00a0"})))
        self.accept(doc(os_set(match={"min_size": "\u30001T", "max_size": " 2t "})))
        # ... ParseSize upper-cases, allows an optional B and inner ASCII space
        self.accept(doc(os_set(match={"min_size": " 1 gb ", "max_size": "8TB"})))
        # ... up to the int64 limit: 8388607T is 2^63 - 2^40 bytes
        self.accept(doc(os_set(match={"min_size": "8388607T", "max_size": "9223372036854775807"})))
        # NBSP is no blank or control character for the device-path form rule
        self.accept(doc(data_set(devices=["/dev/sda\u00a0"])))

    def test_device_corners(self):
        self.accept(doc(os_set(devices=["/dev/sda"])))           # devices on a discover set
        self.accept(doc(data_set(devices=["/dev/disk/by-id/wwn-0x5000c500a1b2c3d4"])))
        self.accept(doc(data_set(devices=["/dev/disk/by-path/pci-0000:00:1f.2-ata-1"])))
        self.accept(doc(data_set(devices=["/dev/md/x"])))         # clean, under /dev, not /dev/disk

    def test_name_limits(self):
        self.accept(doc(os_set(name="a" * 22)))
        self.accept(doc(os_set(name="os"), data_set(name="osa")))
        self.accept(doc(os_set(volumes=[dict(ESP, name="_uefi"), ROOT])))  # '_' only reserved for LVs

    def test_invalid_utf8_inside_a_string(self):
        body = raw_doc(raw_os(vols=ESP_J + "," + ROOT_J + ',{"name":"a","mountpoint":"/a@",'
                              '"fs":"xfs","provider":"lvm","size":"1G"}')).encode()
        self.accept(body.replace(b"@", b"\xff\xfe"))


class TestRejected(Base):
    """Layouts the node refuses, with Go's wording."""

    def test_json_and_types(self):
        self.reject("{", "not valid JSON")
        self.reject(doc(os_set()) + " x", "not valid JSON")
        self.reject("\ufeff" + doc(os_set()), "not valid JSON")
        self.reject(raw_doc(raw_os(',"count":NaN')), "not valid JSON")
        self.reject("[]", "not valid JSON")
        self.reject("null", "version must be 2, got: null")
        for bad, frag in (("1.0", "number 1.0 into Go struct field Set.count of type int"),
                          ("1e0", "number 1e0"), ("true", "bool into Go struct field Set.count"),
                          ('"2"', "string into Go struct field Set.count"),
                          ("99999999999999999999", "of type int")):
            self.reject(raw_doc(raw_os(',"count":%s' % bad)), frag)
        self.reject(raw_doc(raw_os(',"comment":5')), "Set.comment of type string")
        self.reject(raw_doc(raw_os(',"match":{"tags":[1]}')), "Match.match.tags of type string")
        # v2.Parse type-checks every occurrence of a repeated key before
        # jsonstrict refuses the repeat
        self.reject(raw_doc(raw_os(',"origin":{"from":5},"origin":{}')), "Origin.origin.from")
        self.reject(raw_doc(raw_os(',"persistent":"true"')), "of type bool")

    def test_version(self):
        for bad in ("2.0", "2e0", '"2"', "true", "1", "3"):
            self.reject('{"version":%s,"sets":[%s]}' % (bad, raw_os()), "version must be 2, got: " + bad)
        self.reject('{"sets":[%s]}' % raw_os(), "version must be 2, got: null")

    def test_shape_and_keys(self):
        self.reject('{"version":2,"sets":{}}', "sets must be an array")
        self.reject('{"version":2,"sets":[]}', "sets[] must be non-empty")
        self.reject(doc(os_set(), extra=1), "top-level: unknown field 'extra'")
        self.reject(doc(os_set(stray=1)), "sets[0]: unknown field 'stray'")
        self.reject(doc(os_set(Name="os")), 'sets[0]: keys "name" and "Name" are the same field')
        self.reject(doc(os_set(Nam="os")), "sets[0]: unknown field 'Nam'")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, raid="1")])), "unknown field 'raid'")
        self.reject(doc(os_set(match={"bogus": 1})), "sets[0].match: unknown field 'bogus'")
        self.reject(doc(os_set(), os_set(name="os2")), "at most one set may have role=os, found: 2")

    def test_bootloader(self):
        for value in ("maybe", "First", "YES", "", None):
            self.reject(doc(os_set(bootloader=value)), "bootloader unsupported: '%s'" % (value or ""))
        self.reject(doc(os_set(bootloader=1)), "bootloader must be a string or a boolean, got 1")
        self.reject(doc(os_set(bootloader=["first"])), "bootloader must be a string or a boolean")
        self.reject(doc(os_set(), data_set(bootloader="last")), "sets[1].bootloader is valid on the os set only")

    def test_os_raid_policy(self):
        self.reject(doc(os_set(selection="manual", raid="5", devices=disks(4))),
                    "raid=5 is not supported for the OS set")
        self.reject(doc(os_set(raid="6", count=5)), "raid=6 is not supported for the OS set")
        self.reject(doc(os_set(selection="manual", raid="0", devices=disks(3))),
                    "the OS set uses exactly 1, 2 or 4 drives (raid none/1/0/10), got 3")
        self.reject(doc(os_set(selection="manual", raid="1", spares=1, devices=disks(4))),
                    "got 3 active (4 devices minus spares=1)")
        self.reject(doc(os_set(raid="10", count=6)), "got 6")

    def test_member_counts(self):
        self.reject(doc(data_set(raid="5", devices=disks(3))), "raid=5 needs at least 4 device(s), but devices[] lists 3")
        self.reject(doc(data_set(raid="6", devices=disks(4))), "raid=6 needs at least 5 device(s)")
        self.reject(doc(data_set(raid="10", devices=disks(5))), "raid=10 needs at least 4 device(s)")
        self.reject(doc(data_set(raid="1", devices=disks(3))), "raid=1 needs exactly 2 device(s), but devices[] lists 3")
        self.reject(doc(data_set(raid="none", devices=disks(2))), "raid=none needs exactly 1 device(s)")
        self.reject(doc(data_set(raid="5", spares=1, devices=disks(4))),
                    "raid=5 needs at least 4 device(s) active, but devices[] lists 4 with spares=1 (3 active)")
        self.reject(doc({"name": "d", "role": "data", "selection": "discover", "raid": "5", "count": 2,
                         "volumes": [DATA]}), "raid=5 needs at least 4 device(s), but count=2")
        self.reject(doc(data_set(selection="manual", devices=[])), "devices[] is required for selection=manual")

    def test_spares(self):
        self.reject(doc(data_set(raid="0", spares=1, devices=disks(3))), "raid=0 takes no spares")
        self.reject(doc(data_set(raid="none", spares=1)), "raid=none takes no spares")
        self.reject(doc(data_set(raid="1", spares=-1, devices=disks(2))), "spares must be >= 0, got: -1")
        self.reject(doc(data_set(raid="1", spares=2, devices=disks(2))), "spares=2 leaves 0 active device(s)")

    def test_partition_rules(self):
        self.reject(doc(os_set(raid="1", count=2, volumes=[ESP, dict(ROOT, provider="partition")])),
                    "direct partition volumes require raid=none")
        part = {"name": "p", "mountpoint": "/p", "fs": "xfs", "provider": "partition", "size": "100%"}
        self.reject(doc(os_set(volumes=[ESP, part, dict(ROOT, provider="partition", size="10G")])),
                    "size=100% takes the rest of the disk, but direct partition \"root\" is created after it")
        self.reject(doc(os_set(volumes=[ESP, part, ROOT])),
                    "need a storage partition after the direct partitions")
        self.reject(doc(os_set(volumes=[dict(ESP, size="100%"), ROOT])),
                    "the /boot/efi partition needs a fixed size, not 100%")

    def test_sizes(self):
        self.reject(doc(os_set(volumes=[ESP, {k: v for k, v in ROOT.items() if k != "size"}])),
                    "size is required for provider=lvm")
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, name="b")])),
                    "at most one lvm volume per set may use size=100%")
        for bad in ("1.5G", "1GB", "50%", "1024", "1g", " 1G", "10G\n"):
            self.reject(doc(os_set(volumes=[ESP, dict(ROOT, size=bad)])), "is not valid")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, size="0G")])), "must be greater than zero")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, size="9007199254740992K")])), "is too large")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, size="99999999999999999999G")])), "is too large")

    def test_match_sizes(self):
        self.reject(doc(os_set(match={"min_size": "2T", "max_size": "1T"})),
                    'match.min_size "2T" is larger than match.max_size "1T"')
        for bad in ("1G\x1c", "1\u00a0G", "1.5T", "-1G", "1\u017f", "\u0661G", "1\x0bG"):
            self.reject(doc(os_set(match={"min_size": bad})), "match.min_size: cannot parse size")
        self.reject(doc(os_set(match={"max_size": "99999999999999999999"})), "value out of range")
        # int64 overflow is refused (3a26667; it used to wrap to 0 = no bound)
        self.reject(doc(os_set(match={"min_size": "16777216T", "max_size": "1G"})),
                    'match.min_size: size "16777216T" is too large')
        self.reject(doc(os_set(match={"max_size": "8388608T"})), "is too large")
        self.reject(doc(os_set(match={"min_size": "9007199254740992K"})), "is too large")

    def test_set_names(self):
        for bad in ("a b", "os\n", "\u00f6s", "x.y"):
            self.reject(doc(os_set(name=bad)), "name may only contain letters, digits")
        self.reject(doc(os_set(name="-os")), "name must not start with '-'")
        self.reject(doc(os_set(name="a" * 23)), "name is 23 characters, at most 22 are allowed")
        self.reject(doc(os_set(name="__")), "name must contain a letter or digit")
        for bad in ("disk", "md", "mapper", "log", "null", "sda", "sdab1", "nvme0n1p2", "md0", "dm-0", "ttyS0", "vcs"):
            self.reject(doc(os_set(name=bad)), "name is reserved: /dev/%s exists" % bad)
        self.reject(doc(os_set(), data_set(name="os")), 'sets[0] and sets[1] are both named "os"')
        self.reject(doc(os_set(name="data-1"), data_set(name="data_1")), "both map to the md array /dev/md/data_1")
        self.reject(doc(os_set(), data_set(name="os-a")), 'cleanup of set "os" removes every /dev/mapper/os-* entry')

    def test_volume_names(self):
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, name="a b")])), "it becomes the LV name or the GPT partition label")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, name="-r")])), "lvcreate refuses such a logical volume name")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, name="_r")])), "must not start with '_'")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, name="snapshot1")])), 'starting with "snapshot" are reserved')
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, name="x_rimage_0")])), 'containing "_rimage" are reserved')
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, name="root", size="1G")])),
                    'volume name "root" is used by volumes[1] and volumes[2]')

    def test_volume_fields(self):
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, fs="tmpfs")])), "fs=tmpfs is reserved")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, fs="btrfs")])), "fs unsupported: 'btrfs'")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, provider="memory")])), "provider=memory is reserved")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, provider="zfs")])), "provider=zfs is reserved")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, mountpoint="data")])), "must be an absolute path or swap")
        self.reject(doc(os_set(volumes=[ESP, dict(ROOT, fs="vfat")])), "lvm volume fs must be xfs, ext4, or swap")
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, fs="swap", size="1G")])), "fs=swap requires mountpoint=swap")
        self.reject(doc(os_set(volumes=[ESP])), "exactly one root volume")
        self.reject(doc(os_set(volumes=[ROOT])), "must declare a /boot/efi vfat partition")
        self.reject(doc(os_set(volumes=[])), "volumes[] must be non-empty")

    def test_mountpoints(self):
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, mountpoint="/data/", size="1G")])),
                    'mountpoint "/data/" is not in canonical form; write it as "/data"')
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, mountpoint="//data", size="1G")])), "canonical")
        for mp in ("/", "/boot", "/boot/efi"):
            self.reject(doc(os_set(), data_set(volumes=[dict(DATA, mountpoint=mp)])), "a data set cannot")
        self.reject(doc(os_set(volumes=[ESP, ROOT, dict(DATA, size="1G")]), data_set()),
                    'mountpoint "/data" is declared twice')
        # Go folds unpaired surrogates to U+FFFD, so these two collide
        self.reject(raw_doc(raw_os(vols=ESP_J + "," + ROOT_J
                                   + ',{"name":"a","mountpoint":"/a\\ud800","fs":"xfs","provider":"lvm","size":"1G"}'
                                   + ',{"name":"b","mountpoint":"/a\\udbff","fs":"xfs","provider":"lvm","size":"1G"}')),
                    "is declared twice")

    def test_flags(self):
        self.reject(doc(os_set(selection="manual", devices=disks(1), persistent=True)),
                    "persistent=true is only valid on a role=data set")
        self.reject(doc({"name": "d", "role": "data", "selection": "discover", "raid": "none",
                         "persistent": True, "volumes": [DATA]}), "persistent=true requires selection=manual")
        self.reject(doc(data_set(save=True)), "save is only valid on a selection=discover set")

    def test_device_paths(self):
        for link in ("by-uuid", "by-label", "by-partuuid", "by-partlabel", "by-diskseq", "by-loop-ref"):
            self.reject(doc(data_set(devices=["/dev/disk/%s/x" % link])), "/dev/disk/")
        self.reject(doc(data_set(devices=["/dev/disk/by-uuid/x"])), "is a by-uuid link")
        self.reject(doc(data_set(devices=["/dev/mapper/mpatha"])), "device-mapper/multipath path")
        self.reject(doc(data_set(devices=["/dev/dm-0"])), "device-mapper/multipath path")
        self.reject(doc(data_set(devices=["sda"])), "device path must start with /dev/: sda")
        self.reject(doc(data_set(raid="1", devices=["/dev/sda", "/dev/disk/by-id/x"])), "all paths must use the same style")
        self.reject(doc(data_set(raid="1", devices=["/dev/sda", "/dev/sda"])), "appears in both set")
        self.reject(doc(os_set(selection="manual", devices=["/dev/sda"]), data_set(devices=["/dev/sda\u00a0"])),
                    'appears in both set "os" and set "d"')


class TestRejected3a26667(Base):
    """The rules luna2-client 3a26667 added."""

    def test_repeated_keys(self):
        self.reject('{"version":2,"version":2,"sets":[%s]}' % raw_os(), 'top-level: key "version" appears twice')
        self.reject('{"version":3,"version":2,"sets":[%s]}' % raw_os(), 'key "version" appears twice')
        self.reject('{"version":2,"sets":5,"sets":[%s]}' % raw_os(), 'key "sets" appears twice')
        self.reject(raw_doc(raw_os(',"bootloader":"first","bootloader":null')), 'sets[0]: key "bootloader" appears twice')
        self.reject(raw_doc(raw_os(',"match":{"min_size":"2T"},"match":{"max_size":"1T"}')), 'key "match" appears twice')
        self.reject(raw_doc(raw_os(',"match":{"min_size":"1T","min_size":"2T"}')), 'sets[0].match: key "min_size"')
        self.reject(raw_doc(raw_os(vols=ESP_J + "," + ROOT_J.replace('"fs"', '"FS":"ext4","fs"'))),
                    'sets[0].volumes[1]: keys "FS" and "fs" are the same field (JSON keys match case-insensitively)')
        self.reject(raw_doc('{"name":"d","role":"data","selection":"manual","raid":"1",'
                            '"devices":["/dev/sda","/dev/sdb"],"devices":["/dev/sdc"],'
                            '"devices":[null,null],"volumes":[%s]}' % DATA_J), 'sets[0]: key "devices" appears twice')
        self.reject(raw_doc('{"name":"os","role":"os","selection":"discover","raid":"none",'
                            '"volumes":[%s,%s],"volumes":[{"name":"uefi"},{"name":"root"}]}' % (ESP_J, ROOT_J)),
                    'key "volumes" appears twice')
        # at any depth, inside values no other check reads, in document order
        self.reject('{"version":2,"sets":[%s],"x":[{"a":1},{"b":{"c":1,"C":2}}]}' % raw_os(),
                    'x[1].b: keys "c" and "C" are the same field')
        self.reject('{"version":2,"comment":{"a":1,"a":2},"sets":[%s]}' % raw_os(), 'comment: key "a" appears twice')
        # strings.ToLower: U+212A (Kelvin) lower-cases to k, U+0130 to i,
        # invalid surrogates are U+FFFD
        self.reject(raw_doc(raw_os(',"\u212aey":1,"key":2')), "are the same field")
        self.reject(raw_doc(raw_os(',"x\u0130":1,"xi":2')), "are the same field")
        self.reject(raw_doc(raw_os(',"\\ud800":1,"\\udbff":2')), "appears twice")

    def test_folded_but_not_repeated_keys(self):
        # U+017F folds to s for encoding/json but not for strings.ToLower: the
        # pair passes jsonstrict and the unknown-key check refuses it
        self.reject(raw_doc(raw_os(vols=ESP_J + "," + ROOT_J.replace('"size"', '"\u017fize":"1G","size"'))),
                    "unknown field '\u017fize'")
        self.reject(raw_doc(raw_os(',"a\u03a3":1,"a\u03c2":2')), "unknown field 'a\u03a3'")

    def test_top_level_comment(self):
        for value in (5, True, [1], {"a": 1}, []):
            self.reject(doc(os_set(), comment=value), "top-level: comment must be a string")
        self.reject('{"version":2,"comment":%s,"sets":[%s]}' % ("9" * 5000, raw_os()), "comment must be a string")

    def test_negative_count(self):
        self.reject(doc(data_set(count=-5)), 'sets[0] (set "d"): count=-5 must not be negative')
        self.reject(doc(os_set(count=-1)), "count=-1 must not be negative")
        self.reject(doc(data_set(count=-9223372036854775808)), "must not be negative")

    def test_device_path_form(self):
        for dev in ("/dev/sda ", "/dev/sd a", "/dev/sda\t", "/dev/sda\n", "/dev/sda\x7f", " /dev/sda", "/dev/sda\x1c"):
            self.reject(doc(data_set(devices=[dev])), "contains a blank or control character")
        for dev, clean in (("/dev//sda", "/dev/sda"), ("/dev/sda/", "/dev/sda"), ("/dev/./sda", "/dev/sda"),
                           ("/dev/../etc/passwd", "/etc/passwd"), ("", "."), ("/dev/", "/dev"),
                           ("/dev/disk/by-id/", "/dev/disk/by-id")):
            self.reject(doc(data_set(devices=[dev])), 'is not a clean path (write it as "%s")' % clean)
        self.reject(doc(data_set(devices=[None])), 'device "" is not a clean path')
        for dev in ("/dev", "/dev/disk"):
            self.reject(doc(data_set(devices=[dev])), "is a directory, not a disk")
        self.reject(doc(data_set(devices=["/dev/disk/by-id"])), "must be /dev/disk/by-id/<link name>")
        self.reject(doc(data_set(devices=["/dev/disk/by-id/a/b"])), "must be /dev/disk/by-id/<link name>")
        self.reject(doc(data_set(devices=["/dev/disk/by-uuid"])), "must be /dev/disk/by-uuid/<link name>")
        # the device-mapper check comes first
        self.reject(doc(data_set(devices=["/dev/mapper/a b"])), "device-mapper/multipath path")

    def test_deep_nesting(self):
        # no layout the node accepts nests deeper than 5 levels. Where Python's
        # parser gives up (near 1000 levels on 3.9-3.11, deeper on 3.12+) the
        # daemon says so; otherwise it gives the node's own first reason.
        for depth, go_reason in ((3000, "comment must be a string"), (60000, "not valid JSON")):
            with self.assertRaises(dl.DisklayoutInvalid) as ctx:
                dl.validate('{"version":2,"comment":%s,"sets":[%s]}' % ("[" * depth + "]" * depth, raw_os()))
            msg = str(ctx.exception)
            self.assertTrue(f"nests {depth + 1} levels deep" in msg or go_reason in msg, msg)


class TestModuleContract(unittest.TestCase):
    def test_never_raises_anything_else(self):
        for text in ('{"version":%s,"sets":[]}' % ("[" * 5000 + "]" * 5000),
                     '{"version":2,"sets":[%s]}' % ("[" * 5000 + "]" * 5000),
                     '{"a":"%s"}' % ("[" * 5000), "[" * 5000,
                     "\ud800", b"\xff\xfe", '{"version":2,"sets":[{"volumes":{"a":1}}]}'):
            try:
                dl.validate(text)
            except dl.DisklayoutInvalid:
                pass

    def test_stdlib_only(self):
        with open(dl.__file__, encoding="utf-8") as fh:
            imports = sorted(line.split()[1] for line in fh if line.startswith(("import ", "from ")))
        self.assertEqual(imports, ["json", "re"])

    def test_public_names(self):
        self.assertTrue(issubclass(dl.DisklayoutInvalid, ValueError))
        self.assertEqual(dl.SCHEMA_VERSION, 2)
        self.assertIsNone(dl.validate(doc(os_set())))


if __name__ == "__main__":
    unittest.main(verbosity=1)
