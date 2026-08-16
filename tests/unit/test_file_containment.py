#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Containment guard for the file server.

Files().check_file builds a path from IMAGE_FILES and a caller-supplied name and
returns it for the daemon to serve. The name arrives from /files/<filename>, which
is also the path a peer pulls osimages over and the path a booting node fetches its
kernel and ramdisk over - so this function is on the boot and the HA-sync paths, not
a back office.

The route's <string:> converter refuses a slash today, so a traversal cannot arrive
through it - but that is the route's guarantee, not this function's. A future <path:>
route, or any other caller, would walk straight out of IMAGE_FILES with '..'. The
containment therefore belongs here, asserted on the resolved path, and this test pins
it: a resolved path outside the directory is refused, an ordinary file inside is still
served.
"""

import os

import pytest


@pytest.fixture
def image_files(tmp_path):
    """
    Point IMAGE_FILES at a throwaway directory holding one real file, and plant a
    'secret' file in its PARENT - a real target one level up, so an escaping name
    resolves to something that genuinely exists. Without that, '../secret' resolves
    to a non-existent path and the old code returns False for the wrong reason,
    which would let a broken containment pass the test.
    """
    import common.constant as constant
    root = tmp_path / 'files'
    root.mkdir()
    (root / 'osimage-1.tar.bz2').write_bytes(b'image')
    (root / 'vmlinuz').write_bytes(b'kernel')
    (tmp_path / 'secret').write_bytes(b'host secret outside the files dir')
    original = constant.CONSTANT['FILES']['IMAGE_FILES']
    constant.CONSTANT['FILES']['IMAGE_FILES'] = str(root)
    yield root
    constant.CONSTANT['FILES']['IMAGE_FILES'] = original


def test_a_file_inside_the_directory_is_served(image_files):
    from utils.files import Files
    result = Files().check_file('osimage-1.tar.bz2')
    assert result == os.path.realpath(str(image_files / 'osimage-1.tar.bz2'))


def test_an_extensionless_file_inside_the_directory_is_served(image_files):
    """The boot path fetches kernels/ramdisks under plain names - keep serving them."""
    from utils.files import Files
    assert Files().check_file('vmlinuz') == os.path.realpath(str(image_files / 'vmlinuz'))


def test_a_missing_file_returns_false(image_files):
    from utils.files import Files
    assert Files().check_file('not-here.tar') is False


@pytest.mark.parametrize('escape', [
    '../secret',            # a real file one level up - the discriminating case
    '../../../etc/passwd',
    '/etc/passwd',
    'sub/../../secret',
])
def test_a_path_that_escapes_the_directory_is_refused(image_files, escape):
    """
    A name whose resolved path leaves IMAGE_FILES must return False, even when the
    target exists. The old code did os.path.exists on '{IMAGE_FILES}/{name}' with no
    resolution, so '../secret' resolved to the planted file and served it - which is
    why '../secret' is here: it is the case that fails on the unfixed code and passes
    on the fixed one, where a deep '../../../etc/passwd' would resolve to a
    non-existent path and pass either way.
    """
    from utils.files import Files
    assert Files().check_file(escape) is False


def test_a_traversal_that_stays_inside_is_still_served(image_files):
    """Containment is about where the path lands, not whether it contains '..'."""
    from utils.files import Files
    assert Files().check_file('sub/../osimage-1.tar.bz2') == \
        os.path.realpath(str(image_files / 'osimage-1.tar.bz2'))
