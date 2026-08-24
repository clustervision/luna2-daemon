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
The kernelmodules field, on an ubuntu osimage.

The field has always existed, the CLI has always advertised it as "Kernel Modules to
be included in the Initrd or Ramdisk", and on an ubuntu image it did nothing at all:
the value was accepted, the pack reported success, and the ramdisk came out without
the drivers. Nothing failed, which is what made it expensive -- a node provisioned
over InfiniBand needs ib_ipoib in the ramdisk to have an ib0 to provision over, and
MODULES=most does not include drivers/infiniband.

The two builders take modules by completely different routes, and that is the whole
substance of this:

  dracut       --add-drivers on the argv, exactly as the redhat plugin has always done
  mkinitramfs  has no such flag. The only way in is the `modules` file in its config
               directory, and the only way to point it somewhere else is -d.

The -d route is what keeps this non-destructive. Luna copies the image's config aside
and appends to the COPY, so the image's own /etc/initramfs-tools/modules is never
written to. That matters because customers hand-edit that file today -- it is the only
thing that has ever worked -- and a regeneration in place would eat their entries
silently.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon'))

from plugins.osimage.operations.image.ubuntu import (  # noqa: E402
    initramfs_command,
    split_kernel_modules,
    write_module_confdir,
    DRACUT_PATHS,
    MKINITRAMFS_PATHS,
    LUNA_CONFDIR,
)

KERNEL = '6.8.0-31-generic'
RAMDISK = 'img-1700000000-initramfs-6.8.0-31-generic'
OUTPUT = '/tmp/' + RAMDISK
DRACUT = DRACUT_PATHS[0]
MKINITRAMFS = MKINITRAMFS_PATHS[0]

# What a customer provisioning over InfiniBand actually sets. This is the case the
# whole change exists for, so it is the one the tests are written around.
IB = ['ipmi_devintf', ' ipmi_si', ' ib_core', ' ib_umad', ' mlx5_core', ' mlx5_ib',
      ' ib_ipoib']


def probe(*present):
    """Stand in for os.path.exists over a fixed set of paths inside the image."""
    return lambda path: path in set(present)


# ---------------------------------------------------------------------------
# Reading the field.

def test_the_field_splits_into_add_and_omit():
    add, omit = split_kernel_modules(['ib_ipoib', '-plymouth'])
    assert add == ['ib_ipoib']
    assert omit == ['plymouth']


def test_the_spaces_a_comma_separated_field_arrives_with_are_stripped():
    """luna osimage change -m "a, b, c" reaches the plugin with the spaces attached."""
    add, _ = split_kernel_modules([' ib_ipoib ', 'mlx5_ib'])
    assert add == ['ib_ipoib', 'mlx5_ib']


@pytest.mark.parametrize('empty', [None, [], [''], ['  '], ['', ' ']])
def test_an_empty_field_asks_for_nothing(empty):
    assert split_kernel_modules(empty) == ([], [])


# ---------------------------------------------------------------------------
# dracut: the same mapping the redhat plugin uses, because it is the same field.

def test_dracut_is_asked_for_each_requested_driver():
    command, _ = initramfs_command(KERNEL, RAMDISK, ['ib_ipoib', 'mlx5_ib'],
                                   exists=probe(DRACUT))
    assert command.count('--add-drivers') == 2
    assert command[command.index('--add-drivers') + 1] == 'ib_ipoib'


def test_dracut_is_asked_to_omit_what_the_minus_prefix_names():
    command, _ = initramfs_command(KERNEL, RAMDISK, ['-plymouth'], exists=probe(DRACUT))
    assert '--omit-drivers' in command
    assert command[command.index('--omit-drivers') + 1] == 'plymouth'


def test_the_output_stays_last_for_dracut_however_many_drivers_were_added():
    """dracut takes the output positionally: anything appended after it changes meaning.

    The existing suite pins this for the no-modules case. It is re-asserted here
    because adding drivers is exactly the change that could push it off the end.
    """
    command, _ = initramfs_command(KERNEL, RAMDISK, IB + ['-plymouth'],
                                   exists=probe(DRACUT))
    assert command[-1] == OUTPUT


def test_dracut_still_gets_the_luna_module_when_drivers_are_added():
    """The reason luna is named at all does not stop applying because a field is set."""
    command, _ = initramfs_command(KERNEL, RAMDISK, IB, exists=probe(DRACUT))
    assert command[command.index('--add') + 1] == 'luna'


# ---------------------------------------------------------------------------
# mkinitramfs: the config directory, because there is no flag.

def test_mkinitramfs_is_pointed_at_the_luna_confdir_when_modules_are_asked_for():
    command, builder = initramfs_command(KERNEL, RAMDISK, IB, exists=probe(MKINITRAMFS))
    assert builder == 'mkinitramfs'
    assert command[command.index('-d') + 1] == LUNA_CONFDIR


def test_mkinitramfs_is_left_alone_when_no_modules_are_asked_for():
    """The compatibility floor: every ubuntu image that exists today packs this way.

    An image whose kernelmodules field is empty must produce the identical argv it
    always did, or the change reaches images nobody asked to be touched.
    """
    command, _ = initramfs_command(KERNEL, RAMDISK, None, exists=probe(MKINITRAMFS))
    assert command == [MKINITRAMFS, '-o', OUTPUT, KERNEL]
    assert '-d' not in command


def test_the_dracut_driver_flag_never_reaches_mkinitramfs():
    """It would choke on it -- the same reason --add is kept away from it."""
    command, _ = initramfs_command(KERNEL, RAMDISK, IB, exists=probe(MKINITRAMFS))
    assert '--add-drivers' not in command
    assert 'ib_ipoib' not in command


def test_the_kernel_version_stays_the_last_argument_for_mkinitramfs():
    command, _ = initramfs_command(KERNEL, RAMDISK, IB, exists=probe(MKINITRAMFS))
    assert command[-1] == KERNEL


# ---------------------------------------------------------------------------
# The confdir itself: the copy is what gets written to, never the image.

def test_the_requested_modules_land_in_the_copy(tmp_path):
    image_conf = tmp_path / 'etc-initramfs-tools'
    image_conf.mkdir()
    (image_conf / 'modules').write_text('# stock\n')
    (image_conf / 'initramfs.conf').write_text('MODULES=most\n')
    luna_conf = tmp_path / 'luna-confdir'

    write_module_confdir(['ib_ipoib', 'mlx5_ib'], str(image_conf), str(luna_conf))

    written = (luna_conf / 'modules').read_text()
    assert 'ib_ipoib' in written
    assert 'mlx5_ib' in written


def test_the_images_own_config_is_never_written_to(tmp_path):
    """The customer's file is the source. Today it is the only route that works, so
    it will already have their entries in it, and losing those is the failure this
    design exists to avoid."""
    image_conf = tmp_path / 'etc-initramfs-tools'
    image_conf.mkdir()
    (image_conf / 'modules').write_text('# hand added by the customer\nib_ipoib\n')
    before = (image_conf / 'modules').read_text()

    write_module_confdir(['mlx5_ib'], str(image_conf), str(tmp_path / 'luna-confdir'))

    assert (image_conf / 'modules').read_text() == before


def test_what_the_customer_already_put_in_the_file_survives_into_the_copy(tmp_path):
    image_conf = tmp_path / 'etc-initramfs-tools'
    image_conf.mkdir()
    (image_conf / 'modules').write_text('ib_ipoib\n')
    luna_conf = tmp_path / 'luna-confdir'

    write_module_confdir(['mlx5_ib'], str(image_conf), str(luna_conf))

    written = (luna_conf / 'modules').read_text()
    assert 'ib_ipoib' in written and 'mlx5_ib' in written


def test_the_rest_of_the_configuration_comes_along(tmp_path):
    """mkinitramfs reads more than `modules` out of its confdir -- initramfs.conf
    carries MODULES= and COMPRESS=, and the hooks and scripts trees are where the
    luna installer itself comes from. A confdir holding only `modules` would build a
    ramdisk that cannot install a node."""
    image_conf = tmp_path / 'etc-initramfs-tools'
    (image_conf / 'hooks').mkdir(parents=True)
    (image_conf / 'modules').write_text('')
    (image_conf / 'initramfs.conf').write_text('MODULES=most\nCOMPRESS=zstd\n')
    (image_conf / 'hooks' / 'local-hook').write_text('#!/bin/sh\n')
    luna_conf = tmp_path / 'luna-confdir'

    write_module_confdir(['mlx5_ib'], str(image_conf), str(luna_conf))

    assert (luna_conf / 'initramfs.conf').read_text() == 'MODULES=most\nCOMPRESS=zstd\n'
    assert (luna_conf / 'hooks' / 'local-hook').exists()


def test_a_leftover_confdir_from_a_previous_pack_does_not_accumulate(tmp_path):
    """Two packs of the same image must not stack the same modules twice."""
    image_conf = tmp_path / 'etc-initramfs-tools'
    image_conf.mkdir()
    (image_conf / 'modules').write_text('')
    luna_conf = tmp_path / 'luna-confdir'

    write_module_confdir(['mlx5_ib'], str(image_conf), str(luna_conf))
    write_module_confdir(['mlx5_ib'], str(image_conf), str(luna_conf))

    assert (luna_conf / 'modules').read_text().count('mlx5_ib') == 1


# ---------------------------------------------------------------------------
# The same field on the redhat plugin.
#
# It has always worked there -- kernelmodules becomes dracut --add-drivers, and a
# packed ramdisk carries the requested driver. The one thing it did not survive is a
# trailing comma, which is a plausible typo in a comma-separated field: the empty
# entry it leaves behind was indexed unguarded, and the pack reported the generic
# "Problem building initrd" with nothing pointing at the real cause.

def test_the_redhat_plugin_survives_a_trailing_comma():
    """luna osimage change -m "ib_ipoib," is a typo, not a reason to fail a pack."""
    source = open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'daemon', 'plugins', 'osimage', 'operations', 'image', 'default.py'),
        encoding='utf-8').read()

    # Replay the plugin's own parsing over a field with an empty entry in it.
    drivers_add, drivers_remove = [], []
    for i in 'ib_ipoib, , mlx5_ib,'.split(','):
        s = i.replace(" ", "")
        if not s:
            continue
        if s[0] != '-':
            drivers_add.extend(['--add-drivers', s])
        else:
            drivers_remove.extend(['--omit-drivers', s[1:]])

    assert drivers_add == ['--add-drivers', 'ib_ipoib', '--add-drivers', 'mlx5_ib']
    assert 'if not s:' in source, (
        "default.py indexes s[0] without guarding the empty entry a trailing comma "
        "leaves behind - a typo in kernelmodules then fails the pack with a message "
        "that points nowhere near it")


def test_the_ubuntu_plugin_survives_the_same_trailing_comma():
    """Same field, same typo, so the two plugins must agree about it."""
    assert split_kernel_modules('ib_ipoib, , mlx5_ib,'.split(',')) == (
        ['ib_ipoib', 'mlx5_ib'], [])
