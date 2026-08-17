#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Packing an osimage binds the host's /dev, /proc and /sys into the image tree and
chroots in to run dracut. Those bind mounts are live doors onto the host: leave one
mounted and a later delete of the image walks into the host's filesystems and takes
out its device nodes. The unmount therefore has to run on every path.

The failure this guards is the mount lifecycle NOT being exception-safe: the unmount
sitting after the work rather than in a finally, so a raised chroot or a dracut error
skips it and leaks the mounts. This asserts, structurally, that the try which performs
the mount+chroot has a finally, and that the finally is what calls cleanup_mounts.
"""

import ast
import os

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')
SRC = os.path.join(DAEMON, 'plugins', 'osimage', 'operations', 'image', 'default.py')


def _calls(node):
    return {n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def test_the_mount_and_chroot_run_under_a_try_finally_that_unmounts():
    tree = ast.parse(open(SRC, encoding='utf-8').read(), filename=SRC)
    guarded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        body_calls = set()
        for stmt in node.body:
            body_calls |= _calls(stmt)
        # the try that performs the mount + chroot
        if 'prepare_mounts' in body_calls:
            final_calls = set()
            for stmt in node.finalbody:
                final_calls |= _calls(stmt)
            guarded.append(('cleanup_mounts' in final_calls, final_calls))

    assert guarded, "no try block performs prepare_mounts - has the pack been restructured?"
    for has_cleanup, final_calls in guarded:
        assert has_cleanup, (
            "the mount+chroot try has no cleanup_mounts in its finally - a failed pack "
            f"leaks bind mounts inside the image tree. finally calls: {final_calls or 'none'}")
