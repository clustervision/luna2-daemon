#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
Which initramfs builder an ubuntu osimage gets packed with.

Debian and Ubuntu ship two, and an image may carry either -- so unlike the redhat
plugin, which always has dracut, this one has to choose. It chooses on one thing
only: which builder the image has. dracut wins when it has both.

What ends up INSIDE the ramdisk is not this code's business, with one exception.
The client package ships a dracut module, an initramfs-tools hook, or both, and each
pulls in its own toolset -- including the lpart binaries, which are an add-on the
packer must never see. A probe for any of it would encode today's packaging into the
daemon and go stale the moment the packaging moves, so the tests below assert that no
such path changes the outcome.

The exception is the name 'luna', passed to dracut as a constant. It is not a probe
and nothing about the image is inspected to decide it, so the property above still
holds: the argv is identical whatever the client did or did not install. It is there
because a dracut that cannot install 95luna omits it and still exits 0, which is the
one failure this code can turn from silent into loud.

The defect this replaced did exactly that: it gated the builder on the luna dracut
module, so a dracut image without it packed with mkinitramfs -- the wrong tool, and
absent entirely on 25.10+, where the pack then failed.

Every combination is enumerated rather than the one case that prompted the change,
because the next image to arrive is the one nobody wrote an example for.
"""

import os
import sys

DAEMON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'daemon'))
sys.path.insert(0, DAEMON)

import pytest

from plugins.osimage.operations.image.ubuntu import (
    DRACUT_PATHS,
    MKINITRAMFS_PATHS,
    initramfs_command,
)

KERNEL = '6.8.0-31-generic'
RAMDISK = 'img-1700000000-initramfs-6.8.0-31-generic'
OUTPUT = '/tmp/' + RAMDISK
DRACUT = DRACUT_PATHS[0]
MKINITRAMFS = MKINITRAMFS_PATHS[0]

DRACUT_ARGV = [DRACUT, '--force', '--add', 'luna', '--kver', KERNEL, OUTPUT]
MKINITRAMFS_ARGV = [MKINITRAMFS, '-o', OUTPUT, KERNEL]

# Everything the client package may or may not have put in the image. None of it may
# reach this decision -- naming one path would only prove that one was ignored.
CLIENT_PAYLOAD = [
    '/usr/lib/dracut/modules.d/95luna',
    '/usr/share/initramfs-tools/hooks/luna',
    '/usr/bin/lpart-node-installer', '/usr/bin/lpart-storage-prepare',
    '/usr/bin/lpart-storage-check', '/usr/bin/lpart-osimage-install',
    '/usr/bin/lpart-bootloader-finalise', '/usr/bin/lpart-emit',
    '/usr/bin/lpart-tui', '/usr/bin/lpart-phase',
]


def probe(*present):
    """Stand in for os.path.exists over a fixed set of paths inside the image."""
    return lambda path: path in set(present)


def test_an_image_with_only_initramfs_tools_is_unchanged():
    """The 22.04/24.04 case, and the compatibility floor.

    Every ubuntu osimage that exists today is this one. It must pack exactly as it
    did before the builder became a choice, or the change reaches images nobody
    asked to be touched.
    """
    assert initramfs_command(KERNEL, RAMDISK, exists=probe(MKINITRAMFS)) == (
        MKINITRAMFS_ARGV, 'mkinitramfs')


def test_an_image_with_only_dracut_uses_dracut():
    """25.10+, where mkinitramfs is not installed at all.

    Previously this picked mkinitramfs and the pack failed on a missing binary.
    """
    assert initramfs_command(KERNEL, RAMDISK, exists=probe(DRACUT)) == (
        DRACUT_ARGV, 'dracut')


def test_dracut_wins_when_the_image_has_both():
    assert initramfs_command(KERNEL, RAMDISK, exists=probe(DRACUT, MKINITRAMFS)) == (
        DRACUT_ARGV, 'dracut')


def test_an_image_with_neither_builder_reports_it():
    """No builder is a fact to report, not a default to fall back to.

    Returning a command for a binary that is not there turns a diagnosable failure
    into a confusing one, which is what the old message did.
    """
    assert initramfs_command(KERNEL, RAMDISK, exists=probe()) == (None, None)


@pytest.mark.parametrize('dracut_path', DRACUT_PATHS)
@pytest.mark.parametrize('mkinitramfs_path', MKINITRAMFS_PATHS)
def test_either_spelling_of_either_builder_is_found(dracut_path, mkinitramfs_path):
    """Packaging has moved these between sbin and bin; both must be probed."""
    _, builder = initramfs_command(KERNEL, RAMDISK, exists=probe(dracut_path))
    assert builder == 'dracut', f'{dracut_path} not recognised as dracut'
    _, builder = initramfs_command(KERNEL, RAMDISK, exists=probe(mkinitramfs_path))
    assert builder == 'mkinitramfs', f'{mkinitramfs_path} not recognised'


def test_nothing_the_client_package_ships_reaches_this_decision():
    """The whole client payload thrown at every image shape; not one output may move.

    This is the property that keeps the packer abstract. The dracut module, the
    initramfs-tools hook and every lpart binary are the client's to ship and the
    client's to pull in -- dracut includes an installed module by itself, so there
    is not even a name to pass. If any of it starts to matter here, the daemon has
    grown an opinion about packaging that packaging is free to invalidate.
    """
    for image in ((DRACUT,), (MKINITRAMFS,), (DRACUT, MKINITRAMFS), ()):
        bare = initramfs_command(KERNEL, RAMDISK, exists=probe(*image))
        loaded = initramfs_command(KERNEL, RAMDISK,
                                   exists=probe(*image, *CLIENT_PAYLOAD))
        assert bare == loaded, (
            f'something the client package ships changed the outcome for an image '
            f'holding {image}'
        )


def test_luna_is_named_so_a_ramdisk_without_it_cannot_be_built():
    """The one module dracut may not silently omit, because omitting it is invisible.

    This reverses an earlier decision here, and the reason it reversed is worth
    keeping. Leaving the name off rested on dracut including an installed 95luna by
    itself. It does -- but only while every module 95luna depends on can also be
    installed. When one cannot, dracut drops 95luna, prints an [E], and exits 0. The
    ramdisk builds, packs and serves with no installer inside it, and the failure
    only ever surfaces on a node's console. Ubuntu 26 does exactly this: dracut's
    network modules are a separate package, and 95luna depends on them.

    --add turns that into rc 1 and no artifact. The known cost is accepted: a dracut
    image with no client installed now fails to pack rather than producing a
    client-less ramdisk, which could never have installed a node anyway.
    """
    command, _ = initramfs_command(KERNEL, RAMDISK, exists=probe(DRACUT))
    assert '--add' in command
    assert command[command.index('--add') + 1] == 'luna'


def test_the_module_name_never_reaches_mkinitramfs():
    """It is a dracut flag; mkinitramfs has no such concept and would choke on it."""
    command, _ = initramfs_command(KERNEL, RAMDISK, exists=probe(MKINITRAMFS))
    assert '--add' not in command and 'luna' not in command


def test_the_output_is_the_last_argument_for_dracut():
    """dracut takes it positionally, so anything appended after it changes meaning."""
    command, _ = initramfs_command(KERNEL, RAMDISK, exists=probe(DRACUT))
    assert command[-1] == OUTPUT


# ---------------------------------------------------------------------------
# Where the installer unpacks to.
#
# The other consequence of ubuntu having two initramfs frameworks. They do not
# share a name for the target root -- initramfs-tools exports rootmnt=/root,
# dracut exports NEWROOT=/sysroot and has no notion of rootmnt -- so a plugin that
# names only one of them is correct for exactly one builder.
#
# The value is shell, evaluated on the node, so these tests do what the node does:
# render it into the two lines of templ_install.cfg that consume it and run them
# under each framework. Asserting on the string would only prove it is the string
# somebody wrote.
# ---------------------------------------------------------------------------

from plugins.osimage.operations.image.ubuntu import Plugin as UbuntuPlugin

# verbatim from templ_install.cfg -- the unconditional export, then the guard
SYSTEMROOT_PREAMBLE = (
    'export _SYSTEMROOT="{systemroot}"\n'
    'if [[ -z ${{rootmnt:-}} ]]; then\n'
    '    export rootmnt="{systemroot}"\n'
    'fi\n'
    'printf "%s\\n%s\\n" "$_SYSTEMROOT" "$rootmnt"\n'
)


def _resolve(systemroot, environment):
    """Evaluate the rendered preamble the way a booting node would."""
    import subprocess
    script = SYSTEMROOT_PREAMBLE.format(systemroot=systemroot)
    result = subprocess.run(['bash', '-c', script], capture_output=True,
                            text=True, env=environment, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.split()


@pytest.mark.parametrize('environment,expected', [
    ({'rootmnt': '/root'},        '/root'),     # initramfs-tools
    ({'NEWROOT': '/sysroot'},     '/sysroot'),  # dracut
    ({},                          '/sysroot'),  # neither: the literal, never empty
])
def test_the_target_root_resolves_under_either_initramfs(environment, expected):
    systemroot, rootmnt = _resolve(UbuntuPlugin.systemroot, environment)
    assert rootmnt == expected
    # _SYSTEMROOT is exported before the guard and is published to the operator's
    # pre/part/post scripts, so it has to agree rather than merely be set.
    assert systemroot == expected


@pytest.mark.parametrize('environment', [{'rootmnt': '/root'}, {'NEWROOT': '/sysroot'}, {}])
def test_the_target_root_is_never_empty_or_relative(environment):
    """An empty resolution is the failure that matters: every "/${rootmnt}/..." in
    the installer would then address the initramfs' own root, and the image would
    unpack into a tmpfs that disappears at pivot."""
    for value in _resolve(UbuntuPlugin.systemroot, environment):
        assert value, 'the target root resolved to nothing'
        assert value.startswith('/'), f'the target root is relative: {value}'
