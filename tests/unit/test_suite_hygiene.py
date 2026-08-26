#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
Two rules about what may end up in the tree, held by a test rather than by care.

Both were broken by the same line, and it survived review and shipped: a
regression test wrote its rendered output to a fixed path in somebody's home
directory. It was a debugging convenience nobody removed. It named a tool in a
path, and it meant that test could only pass on one machine - anywhere else it
raises before reaching the assertions that matter.

Neither rule is new. What is new is that they now fail the suite instead of
depending on somebody noticing in a diff.
"""

import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEARCHED = ('daemon', 'tests')
SUFFIXES = ('.py', '.cfg', '.ini', '.templ', '.sh', '.j2')

# This file necessarily contains the words it looks for.
EXEMPT = {os.path.abspath(__file__)}


def tree_files():
    for top in SEARCHED:
        for where, dirs, files in os.walk(os.path.join(REPO, top)):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            for name in files:
                path = os.path.join(where, name)
                if name.endswith(SUFFIXES) and path not in EXEMPT:
                    yield path


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        return handle.read()


# --- a test must not write outside the directory pytest gave it -------------

ABSOLUTE_WRITE = re.compile(r"""open\(\s*f?['"]/(home|root|Users)/""")


def test_nothing_writes_into_somebody_s_home_directory():
    """
    A path under /home only exists on the machine it was written on. A test that
    writes there passes for its author and raises for everyone else, before it
    reaches the assertions it exists for - so the failure names a file, not the
    behaviour under test.

    pytest hands out tmp_path for exactly this. If a rendered artefact is worth
    keeping to look at, keep it in tmp_path and read it from the failure output.
    """
    offenders = []
    for path in tree_files():
        for number, line in enumerate(read(path).splitlines(), 1):
            if ABSOLUTE_WRITE.search(line):
                offenders.append(f'{os.path.relpath(path, REPO)}:{number}')
    assert not offenders, (
        f'these write to a fixed path in a home directory: {offenders}. '
        f'Use the tmp_path fixture; a path under /home exists on one machine.'
    )


# --- nothing in the tree credits or names a tool ----------------------------

# Built from fragments so this file does not match its own rule when the check
# above is pointed at the tree.
FORBIDDEN = [
    'cl' + 'aude', 'anthro' + 'pic', 'chat' + 'gpt', 'open' + 'ai',
    'co-auth' + 'ored-by', 'gene' + 'rated by ai', 'ai-ass' + 'isted',
    'cop' + 'ilot',
]


def test_nothing_in_the_tree_names_a_tool():
    """
    The code is ours and how it was written is not part of the record. This is an
    absolute rule in a product repo - not softened by the mention being small,
    honest or true, and it covers a path in a debug line as much as a comment.

    It gets broken by accident rather than intent: a scratch path, a default
    trailer some tooling adds, a filename nobody looked at twice. A default is not
    permission, which is why this is a test.
    """
    offenders = []
    for path in tree_files():
        lowered = read(path).lower()
        for number, line in enumerate(lowered.splitlines(), 1):
            for word in FORBIDDEN:
                if word in line:
                    offenders.append(f'{os.path.relpath(path, REPO)}:{number} ({word})')
    assert not offenders, f'these name a tool: {offenders}'


def test_the_check_can_actually_fail(tmp_path):
    """
    A scan whose regex matched nothing would make both tests above pass forever
    while checking nothing. This proves each pattern still catches what it names.
    """
    assert ABSOLUTE_WRITE.search('    open("/home/someone/out.conf", "w").write(x)')
    assert ABSOLUTE_WRITE.search("open(f'/root/{name}.cfg', 'w')")
    assert not ABSOLUTE_WRITE.search('open(tmp_path / "out.conf", "w")')
    assert any(word in ('cl' + 'aude') for word in FORBIDDEN)
