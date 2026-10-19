#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
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
Packing an osimage through lchroot instead of mounting the host into the image tree.

When a Python lchroot that takes --path is installed, the pack hands it the in-image
builder commands: lchroot brings its own /dev, /proc and /sys and holds the image lock,
so the daemon mounts nothing and never chroots. Which route a pack takes is decided
once, by detection, before anything runs in the image; after that a failure is a
failed pack, never a quiet switch to the chroot route -- an image another session is
editing must not be entered beside it.

The chroot route is exercised here only to prove it was or was not entered. Every
call it would make on this machine -- mount, chroot, the builder -- is intercepted.
"""

import io
import json
import logging
import os
import subprocess
import sys

import pytest

import plugins.osimage.operations.image.default as default_module
import plugins.osimage.operations.image.ubuntu as ubuntu_module

KERNEL = '5.14.0-test'
LOGGER = 'luna2-daemon'

LOCKED_LINE = ("ERROR: image 'compute' is held by a live session (PID 3793739 on /dev/pts/14); "
               "refusing to break it non-interactively. Re-run on a terminal, inspect with "
               "`lchroot --status compute`, or pass --force to break the lock and run anyway.")
HELP_WITH_PATH = 'usage: lchroot [--path DIR] [--force] [--ro] [IMAGE] [-- COMMAND ...]'
HELP_WITHOUT_PATH = 'usage: lchroot [--force] IMAGE'

# A stand-in for the modern lchroot: it answers --help, appends every other argv to a
# record file, and plays the builder it is asked to run by creating the output file
# inside the image. In 'locked' mode it refuses the way lchroot does; in 'fail' mode
# the builder fails.
FAKE_LCHROOT = '''#!%(python)s
import json, os, sys
argv = sys.argv[1:]
if argv == ['--help']:
    print(%(help)r)
    sys.exit(%(help_rc)d)
with open(%(record)r, 'a') as handle:
    handle.write(json.dumps(argv) + '\\n')
if %(mode)r == 'locked':
    sys.stderr.write(%(locked)r + '\\n')
    sys.exit(9)
if %(mode)r == 'fail':
    sys.stderr.write('dracut: Failed to install module luna\\ndracut: cannot continue\\n')
    sys.exit(1)
image = argv[argv.index('--path') + 1]
command = argv[argv.index('--') + 1:]
if '--list-modules' in command:
    sys.stdout.write(%(listing)r)
    sys.exit(0)
if '-d' in command:
    with open(image + command[command.index('-d') + 1] + '/modules') as modules:
        with open(%(record)r + '.modules', 'w') as seen:
            seen.write(modules.read())
output = command[command.index('-o') + 1] if '-o' in command else command[-1]
open(image + output, 'w').close()
'''


def install_lchroot(tmp_path, monkeypatch, mode='ok', help_text=HELP_WITH_PATH, help_rc=0,
                    listing='luna\nbase\n', script=None):
    """Put an lchroot first on PATH and return (its path, the argv record file)."""
    bindir = tmp_path / 'bin'
    bindir.mkdir(exist_ok=True)
    record = tmp_path / 'lchroot.argv'
    lchroot = bindir / 'lchroot'
    lchroot.write_text(script or FAKE_LCHROOT % {
        'python': sys.executable, 'help': help_text, 'help_rc': help_rc,
        'record': str(record), 'mode': mode, 'locked': LOCKED_LINE, 'listing': listing})
    lchroot.chmod(0o755)
    monkeypatch.setenv('PATH', f"{bindir}:{os.environ.get('PATH', '')}")
    return str(lchroot), record


def recorded(record):
    return [json.loads(line) for line in record.read_text().splitlines()]


def make_image(tmp_path):
    """An image tree with a kernel, mkinitramfs, and an initramfs-tools config to copy."""
    image = tmp_path / 'images' / 'compute'
    for sub in ('boot', 'tmp', 'dev', 'proc', 'sys', 'usr/sbin', 'etc/initramfs-tools'):
        (image / sub).mkdir(parents=True)
    (image / 'boot' / f'vmlinuz-{KERNEL}').write_text('kernel')
    (image / 'usr/sbin/mkinitramfs').write_text('#!/bin/sh\n')
    (image / 'etc/initramfs-tools/modules').write_text('nvme\n')
    return image


def detector():
    found = getattr(default_module, 'bwrap_lchroot', None)
    assert found is not None, 'default.py has no lchroot detector'
    return lambda: found(logging.getLogger(LOGGER), 'compute')


BUILDERS = ('/usr/bin/dracut', '/usr/sbin/dracut', '/usr/sbin/mkinitramfs', '/usr/bin/mkinitramfs')


class RefusedBuilder:
    """What the chroot route gets instead of a real builder on this host: a failed run."""
    returncode = 1

    def __init__(self):
        self.stdout = io.BytesIO(b'')
        self.stderr = io.BytesIO(b'builder refused by the test\n')

    def poll(self):
        return self.returncode


@pytest.fixture
def host(monkeypatch):
    """Keep the chroot route off this machine, and record whether it was entered."""
    calls = {'chroot': [], 'mount': [], 'builder': []}
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if argv[0] in ('/usr/bin/mount', '/usr/bin/umount'):
            calls['mount'].append(argv)
            return subprocess.CompletedProcess(argv, 0, '', '')
        return real_run(argv, *args, **kwargs)

    # subprocess.run is built on Popen, so only the builders are intercepted here;
    # everything else, the fake lchroot included, runs for real.
    def popen(argv, *args, **kwargs):
        if argv[0] in BUILDERS:
            calls['builder'].append(argv)
            return RefusedBuilder()
        return real_popen(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr(subprocess, 'Popen', popen)
    monkeypatch.setattr(os, 'chroot', lambda path: calls['chroot'].append(path))
    monkeypatch.setattr(os, 'fchdir', lambda fd: None)
    monkeypatch.setattr(os, 'chown', lambda *args, **kwargs: None)
    for module in (default_module, ubuntu_module):
        monkeypatch.setattr(module.Plugin, 'verify_space', lambda self, *args: (True, 'ok'))
    return calls


def pack(module, tmp_path, image, kernel_modules=()):
    return module.Plugin().pack(osimage='compute', image_path=str(image),
                                files_path=str(tmp_path / 'files'), kernel_version=KERNEL,
                                kernel_modules=list(kernel_modules))


# ---------------------------------------------------------------------------
# Detection: what counts as a usable lchroot.

def test_no_lchroot_on_the_path_means_chroot(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', str(tmp_path))
    assert detector()() is None


def test_a_shell_script_lchroot_is_rejected_without_being_run(tmp_path, monkeypatch):
    """The old lchroot is a bash script that calls back into this daemon's API for any
    argument. Reading its first line is allowed; executing it, even for --help, is not."""
    marker = tmp_path / 'executed'
    install_lchroot(tmp_path, monkeypatch, script=(
        f"#!/bin/bash\ntouch {marker}\necho '{HELP_WITH_PATH}'\n"))
    assert detector()() is None
    assert not marker.exists(), 'the shell-script lchroot was executed'


def test_a_python_lchroot_without_path_is_rejected_with_a_warning(tmp_path, monkeypatch, caplog):
    lchroot, _ = install_lchroot(tmp_path, monkeypatch, help_text=HELP_WITHOUT_PATH)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert detector()() is None
    assert lchroot in caplog.text and 'not usable' in caplog.text


def test_a_python_lchroot_offering_path_is_used(tmp_path, monkeypatch):
    lchroot, _ = install_lchroot(tmp_path, monkeypatch)
    assert detector()() == lchroot


# ---------------------------------------------------------------------------
# The redhat plugin's pack, end to end against the fake lchroot.

def test_pack_builds_through_lchroot_with_no_mount_and_no_chroot(tmp_path, monkeypatch, host):
    lchroot, record = install_lchroot(tmp_path, monkeypatch)
    image = make_image(tmp_path)

    result = pack(default_module, tmp_path, image)

    assert result[0] is True, result[1]
    assert host['chroot'] == [] and host['mount'] == []
    kernel_file, ramdisk_file = result[2], result[3]
    assert (tmp_path / 'files' / kernel_file).is_file()
    assert (tmp_path / 'files' / ramdisk_file).is_file()

    calls = recorded(record)
    assert len(calls) == 2
    for argv in calls:
        assert argv[:3] == ['--path', str(image), '--']
        assert '--force' not in argv[:3]
    listing, build = (argv[3:] for argv in calls)
    assert listing == ['/usr/bin/dracut', '--kver', KERNEL, '--list-modules']
    assert build == ['/usr/bin/dracut', '--force', '--kver', KERNEL, '--add', 'luna',
                     '--omit', 'i18n', '--omit', 'plymouth', '/tmp/' + ramdisk_file]


def test_a_missing_luna_module_is_added_as_on_the_chroot_route(tmp_path, monkeypatch, host):
    _, record = install_lchroot(tmp_path, monkeypatch, listing='base\nnetwork\n')
    result = pack(default_module, tmp_path, make_image(tmp_path))
    assert result[0] is True, result[1]
    build = recorded(record)[1]
    assert build[build.index('--') + 1:].count('luna') == 2


@pytest.mark.parametrize('module', [default_module, ubuntu_module], ids=['default', 'ubuntu'])
def test_an_image_held_by_another_session_fails_the_pack_verbatim(tmp_path, monkeypatch, host, module):
    """Exit 9 is lchroot refusing to break a live session. Entering the image anyway
    through the chroot route would be the race the lock exists to prevent."""
    install_lchroot(tmp_path, monkeypatch, mode='locked')
    result = pack(module, tmp_path, make_image(tmp_path))
    assert result[0] is False
    assert result[1] == LOCKED_LINE
    assert host['chroot'] == [], 'the chroot route was entered on a held image'


@pytest.mark.parametrize('module', [default_module, ubuntu_module], ids=['default', 'ubuntu'])
def test_a_failed_build_under_lchroot_fails_the_pack(tmp_path, monkeypatch, host, module):
    """Once the modern route is chosen there is no second attempt: the builder's
    first stderr lines come back the way the chroot route reports them."""
    install_lchroot(tmp_path, monkeypatch, mode='fail')
    result = pack(module, tmp_path, make_image(tmp_path))
    assert result[0] is False
    assert result[1] == 'dracut: Failed to install module luna.dracut: cannot continue.'
    assert host['chroot'] == [], 'the chroot route was entered after a failed lchroot build'


def test_an_unusable_python_lchroot_is_warned_about_and_the_pack_chroots(tmp_path, monkeypatch, host, caplog):
    """A Python lchroot whose --help fails (a missing library, say) is set aside at
    detection time, loudly, and the pack takes the chroot route it always had."""
    lchroot, record = install_lchroot(tmp_path, monkeypatch, help_rc=2)
    image = make_image(tmp_path)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        pack(default_module, tmp_path, image)
    assert str(image) in host['chroot'], 'the chroot route was not entered'
    assert not record.exists(), 'the unusable lchroot was asked to run a command'
    assert lchroot in caplog.text and 'not usable' in caplog.text


# ---------------------------------------------------------------------------
# The ubuntu plugin: the image is asked by path, and the confdir lives in the image.

def test_ubuntu_probes_the_builder_inside_the_image_and_writes_its_confdir_there(tmp_path, monkeypatch, host):
    """The image carries mkinitramfs only; whatever this controller has must not
    decide the builder. The requested modules reach mkinitramfs through a copy of
    the image's own initramfs-tools config, made under the image's /tmp and gone
    again after the pack."""
    _, record = install_lchroot(tmp_path, monkeypatch)
    image = make_image(tmp_path)

    result = pack(ubuntu_module, tmp_path, image, kernel_modules=['ib_ipoib', ' mlx5_ib'])

    assert result[0] is True, result[1]
    assert host['chroot'] == [] and host['mount'] == []
    ramdisk_file = result[3]
    (build,) = recorded(record)
    assert build[:3] == ['--path', str(image), '--']
    assert build[3:] == ['/usr/sbin/mkinitramfs', '-d', '/tmp/luna-initramfs-tools',
                         '-o', '/tmp/' + ramdisk_file, KERNEL]
    seen = (tmp_path / 'lchroot.argv.modules').read_text()
    assert 'nvme' in seen, 'the image\'s own modules file was not the source of the copy'
    assert 'ib_ipoib' in seen and 'mlx5_ib' in seen
    assert not (image / 'tmp' / 'luna-initramfs-tools').exists(), 'the confdir was left in the image'


def test_ubuntu_still_refuses_an_omit_on_an_mkinitramfs_image(tmp_path, monkeypatch, host):
    _, record = install_lchroot(tmp_path, monkeypatch)
    result = pack(ubuntu_module, tmp_path, make_image(tmp_path), kernel_modules=['-plymouth'])
    assert result[0] is False
    assert 'cannot exclude a module' in result[1]
    assert not record.exists(), 'the builder was run despite the refusal'
