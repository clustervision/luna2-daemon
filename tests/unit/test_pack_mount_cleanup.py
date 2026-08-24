#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
Packing an osimage binds the host's /dev, /proc and /sys into the image tree and
chroots in to build the ramdisk. Those mounts are live doors onto the host: leave one
mounted and a later delete of the image walks into the host's filesystems and takes
out its device nodes. The unmount therefore has to run on every path, and it has to
actually succeed.

Two distinct failures are guarded here, because the first one alone let the second
ship. Structurally, the try which performs the mount+chroot must have a finally, and
that finally must be what calls cleanup_mounts -- otherwise a raised chroot or a
builder error skips the unmount entirely. Behaviourally, the unmount must be waited on
and must clear nested mounts: a plugin whose cleanup_mounts *runs* and silently fails
leaks exactly as badly as one that never runs it, and passes the structural check
while doing so. That was the real defect -- umount fired through Popen, never waited
on, its status never read, refused by the efivarfs the ramdisk build mounts inside the
image's own /sys.

Every plugin in the image operations directory is checked, not one named file. The
plugins are a fan-out: a fix applied to the one someone happened to open leaves the
next distro's plugin carrying the bug.
"""

import ast
import os

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')
PLUGIN_DIR = os.path.join(DAEMON, 'plugins', 'osimage', 'operations', 'image')


def image_plugins():
    """Every image operation plugin, so a new distro's plugin is covered on arrival."""
    found = []
    for name in sorted(os.listdir(PLUGIN_DIR)):
        if not name.endswith('.py') or name == '__init__.py':
            continue
        path = os.path.join(PLUGIN_DIR, name)
        source = open(path, encoding='utf-8').read()
        if 'prepare_mounts' not in source:
            continue
        found.append((name, source, ast.parse(source, filename=path)))
    assert found, f"no image plugin in {PLUGIN_DIR} mounts anything - has pack been restructured?"
    return found


def _calls(node):
    return {n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_every_image_plugin_unmounts_in_a_finally():
    for name, _source, tree in image_plugins():
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

        assert guarded, (
            f"{name}: no try block performs prepare_mounts - the mount+chroot is not "
            "exception-safe, so a failed pack leaks bind mounts inside the image tree")
        for has_cleanup, final_calls in guarded:
            assert has_cleanup, (
                f"{name}: the mount+chroot try has no cleanup_mounts in its finally - a "
                f"failed pack leaks bind mounts inside the image tree. "
                f"finally calls: {final_calls or 'none'}")


def test_every_image_plugin_waits_on_its_umount():
    """A fire-and-forget umount cannot fail visibly, so it leaks in silence.

    subprocess.Popen returns before the umount has run and its status is never read.
    The unmount has to be a call we wait on and whose return code we inspect.
    """
    for name, source, tree in image_plugins():
        umount = _function(tree, 'umount')
        assert umount is not None, f"{name}: no umount helper found"
        body = ast.get_source_segment(source, umount)

        popen = [n for n in ast.walk(umount)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == 'Popen']
        assert not popen, (
            f"{name}: umount is fired through subprocess.Popen and never waited on. "
            "Nothing reads its status, so a refused unmount is invisible and the "
            "host's filesystem stays mounted inside the image tree.")

        assert 'returncode' in body, (
            f"{name}: umount never inspects the return code of the unmount, so a "
            "failure cannot be reported and the mount is left behind silently.")


def test_every_image_plugin_clears_nested_mounts():
    """The ramdisk build mounts efivarfs inside the image's own /sys.

    A non-recursive umount of the parent is refused while a nested mount is live, so
    the unmount has to take the whole subtree, not just the mountpoint we created.
    """
    for name, source, tree in image_plugins():
        umount = _function(tree, 'umount')
        body = ast.get_source_segment(source, umount)
        assert '--recursive' in body or "'-R'" in body, (
            f"{name}: umount is not recursive. The initramfs build mounts efivarfs "
            "under the image's /sys, and the parent then refuses to unmount while it "
            "is there - which is exactly how the host's sysfs got left behind.")


def test_cleanup_mounts_covers_everything_prepare_mounts_mounts():
    """Derived from prepare_mounts, so a fourth mount cannot be added and forgotten."""
    for name, source, tree in image_plugins():
        prepare = _function(tree, 'prepare_mounts')
        cleanup = _function(tree, 'cleanup_mounts')
        assert prepare is not None and cleanup is not None, \
            f"{name}: prepare_mounts/cleanup_mounts pair not found"

        # mount targets look like f"{path}/dev" -- take the literal tail of each
        mounted = set()
        for call in ast.walk(prepare):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == 'mount'):
                continue
            target = call.args[1]
            if isinstance(target, ast.JoinedStr):
                for piece in target.values:
                    if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                        mounted.add(piece.value.strip('/'))

        assert mounted, f"{name}: could not read the mount targets out of prepare_mounts"

        cleanup_body = ast.get_source_segment(source, cleanup)
        for leaf in sorted(mounted):
            assert leaf in cleanup_body, (
                f"{name}: prepare_mounts mounts '{leaf}' but cleanup_mounts never "
                f"unmounts it - it is left inside the image tree after every pack.")
