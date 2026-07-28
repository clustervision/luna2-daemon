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
plugin, which always has dracut, this one has to choose. Two questions are kept
apart on purpose and both are pinned here:

  * WHICH BUILDER  -- decided by what the image has installed, nothing else
  * WHICH ADD-ONS  -- the luna dracut module is requested if present, and its absence
                      must never change the builder

Conflating them is the defect this replaced: the luna module was used as the gate on
the builder, so a dracut image without the module packed with mkinitramfs -- the wrong
tool, and absent entirely on 25.10+, where the pack then failed.

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
    LUNA_DRACUT_MODULE,
    MKINITRAMFS_PATHS,
    initramfs_command,
)

KERNEL = '6.8.0-31-generic'
RAMDISK = 'img-1700000000-initramfs-6.8.0-31-generic'
OUTPUT = '/tmp/' + RAMDISK


def probe(*present):
    """Stand in for os.path.exists over a fixed set of paths inside the image."""
    return lambda path: path in set(present)


def test_an_image_with_only_initramfs_tools_is_unchanged():
    """The 22.04/24.04 case, and the compatibility floor.

    Every ubuntu osimage that exists today is this one. It must pack exactly as it
    did before the builder became a choice, or the change reaches images nobody
    asked to be touched.
    """
    command, builder = initramfs_command(KERNEL, RAMDISK,
                                         exists=probe(MKINITRAMFS_PATHS[0]))
    assert builder == 'mkinitramfs'
    assert command == [MKINITRAMFS_PATHS[0], '-o', OUTPUT, KERNEL]


def test_an_image_with_only_dracut_uses_dracut():
    """25.10+, where mkinitramfs is not installed at all.

    Previously this picked mkinitramfs and the pack failed on a missing binary.
    """
    command, builder = initramfs_command(KERNEL, RAMDISK,
                                         exists=probe(DRACUT_PATHS[0]))
    assert builder == 'dracut'
    assert command == [DRACUT_PATHS[0], '--force', '--kver', KERNEL, OUTPUT]


def test_dracut_wins_when_the_image_has_both():
    command, builder = initramfs_command(
        KERNEL, RAMDISK, exists=probe(DRACUT_PATHS[0], MKINITRAMFS_PATHS[0]))
    assert builder == 'dracut'
    assert MKINITRAMFS_PATHS[0] not in command


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


def test_the_luna_module_is_added_when_the_image_carries_it():
    command, _ = initramfs_command(
        KERNEL, RAMDISK, exists=probe(DRACUT_PATHS[0], LUNA_DRACUT_MODULE))
    assert command == [DRACUT_PATHS[0], '--force', '--kver', KERNEL,
                       '--add', 'luna', OUTPUT]


def test_the_luna_module_is_not_requested_when_absent():
    """`--add` on a module that is not there makes dracut fail.

    So this cannot be unconditional the way the redhat plugin affords to be -- that
    one runs against images whose client rpm always ships the module.
    """
    command, _ = initramfs_command(KERNEL, RAMDISK, exists=probe(DRACUT_PATHS[0]))
    assert '--add' not in command and 'luna' not in command


def test_the_luna_module_never_decides_the_builder():
    """The defect this replaced, pinned so it cannot come back.

    The module is an add-on. Its presence or absence changes what is passed to the
    builder and must never change which builder runs -- in either direction.
    """
    for extra in ((), (LUNA_DRACUT_MODULE,)):
        _, builder = initramfs_command(KERNEL, RAMDISK,
                                       exists=probe(DRACUT_PATHS[0], *extra))
        assert builder == 'dracut', 'the luna module changed the builder choice'
        _, builder = initramfs_command(KERNEL, RAMDISK,
                                       exists=probe(MKINITRAMFS_PATHS[0], *extra))
        assert builder == 'mkinitramfs', 'the luna module changed the builder choice'


def test_initramfs_tools_gets_no_lpart_specific_flags():
    """Nothing to pass: its hooks are picked up on their own.

    This is what lets a future client package ship either half of the toolset without
    the packer learning anything about it.
    """
    command, _ = initramfs_command(
        KERNEL, RAMDISK, exists=probe(MKINITRAMFS_PATHS[0], LUNA_DRACUT_MODULE))
    assert command == [MKINITRAMFS_PATHS[0], '-o', OUTPUT, KERNEL]


def test_the_output_is_the_last_argument_for_both_builders():
    """dracut takes it positionally, so anything appended after it changes meaning."""
    for present in (DRACUT_PATHS[0], MKINITRAMFS_PATHS[0]):
        command, _ = initramfs_command(KERNEL, RAMDISK, exists=probe(present))
        assert OUTPUT in command
        if command[0] in DRACUT_PATHS:
            assert command[-1] == OUTPUT
