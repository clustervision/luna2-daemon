#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.

"""
The installer's profile block, executed.

Both installers write profile files during an install, out of a shell block that no
Python test reaches. Reading it is not enough: the block was correct line by line and
still produced empty files on every install, because a cleanup glob deleted the file the
next loop reads --

    get_json_segment ... 'content' 'nodash' > /lunatmp/node.profile.contents.dat
    rm -f /lunatmp/node.profile.content*.dat        # matches contents.dat too
    ... done < /lunatmp/node.profile.contents.dat   # gone

So these tests lift the block out of the template, give it the payload the daemon really
serves, and run it under bash against a temporary root. What is asserted is what ends up
on disk.
"""

import base64
import json
import os
import re
import shutil
import subprocess

import pytest

TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'daemon', 'templates')
INSTALLERS = ['templ_install.cfg', 'templ_install_lpart.cfg']


def _function(source, name):
    """One shell function, from the first line of its definition to its closing brace."""
    match = re.search(rf'^function {name} \{{$.*?^\}}$', source, re.M | re.S)
    assert match, f'{name} is not in the template any more'
    return match.group(0)


def _harness(template, payload, root, tmp_path):
    """The template's own profile block, run over a real payload against a fake root."""
    with open(os.path.join(TEMPLATES, template), 'r', encoding='utf-8') as handle:
        source = handle.read()

    lunatmp = tmp_path / 'lunatmp'
    lunatmp.mkdir(exist_ok=True)
    (lunatmp / 'node.profile.json').write_text(json.dumps(payload))

    block = _function(source, 'node_profiles')
    # the fetch is the one line we cannot run here: no daemon, no token. Everything after
    # it - the extraction, the split, the writing, the manifest - is the code under test
    block = re.sub(r'^\s*curl .*$', '        true', block, flags=re.M)
    block = block.replace("$(echo {{ LUNA_PROFILES }} | tr ',' ' ')", "'demo'")
    block = block.replace('update_status "install.profiles"', 'true')

    script = '\n'.join([
        '#!/bin/bash',
        f'rootmnt={root}',
        'DECODE=1',
        _function(source, 'get_json_segment'),
        _function(source, 'get_encapsulated_content'),
        _function(source, 'get_json_exact'),
        block.replace('/lunatmp/', f'{lunatmp}/'),
        'node_profiles',
    ])
    path = tmp_path / 'block.sh'
    path.write_text(script)
    return subprocess.run(['bash', str(path)], capture_output=True, text=True, timeout=60)


def _payload(files):
    return {'profile': {'demo': {
        'scope': 'static', 'service': 'cron', 'action': 'none', 'enabled': True,
        'files': files}}}


def _file(path, content, **extra):
    entry = {'name': os.path.basename(path), 'path': path,
             'content': base64.b64encode(content.encode()).decode(),
             'owner': 'root:root', 'mode': '644', 'resolved_owner': '0:0'}
    entry.update(extra)
    return entry


@pytest.mark.skipif(not shutil.which('bash'), reason='needs bash')
@pytest.mark.parametrize('template', INSTALLERS)
def test_the_installer_writes_the_content_not_an_empty_file(template, tmp_path):
    """The whole point of applying a profile at install time."""
    root = tmp_path / 'root'
    (root / 'etc').mkdir(parents=True)
    result = _harness(template, _payload([_file('/etc/one.conf', 'FIRST-CONTENT')]),
                      root, tmp_path)
    assert result.returncode == 0, result.stderr
    written = root / 'etc' / 'one.conf'
    assert written.exists(), f'{template} wrote no file at all\n{result.stdout}{result.stderr}'
    assert written.read_text().strip() == 'FIRST-CONTENT', \
        f'{template} wrote an empty or wrong file: {written.read_text()!r}\n{result.stderr}'


@pytest.mark.skipif(not shutil.which('bash'), reason='needs bash')
@pytest.mark.parametrize('template', INSTALLERS)
def test_every_file_of_a_profile_gets_its_own_content(template, tmp_path):
    """The contents arrive as one stream split on separators, so the second file is where
    an off-by-one shows up - and a profile with several files is the ordinary case."""
    root = tmp_path / 'root'
    (root / 'etc').mkdir(parents=True)
    result = _harness(template, _payload([
        _file('/etc/one.conf', 'FIRST-CONTENT'),
        _file('/etc/two.conf', 'SECOND-CONTENT'),
        _file('/etc/three.conf', 'THIRD-CONTENT'),
    ]), root, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (root / 'etc' / 'one.conf').read_text().strip() == 'FIRST-CONTENT'
    assert (root / 'etc' / 'two.conf').read_text().strip() == 'SECOND-CONTENT'
    assert (root / 'etc' / 'three.conf').read_text().strip() == 'THIRD-CONTENT'


@pytest.mark.skipif(not shutil.which('bash'), reason='needs bash')
@pytest.mark.parametrize('template', INSTALLERS)
def test_a_path_whose_directory_does_not_exist_yet(template, tmp_path):
    """An image has no /srv/something until a profile puts a file there. The live applier
    creates the parents; the installer did not, and the file was simply lost."""
    root = tmp_path / 'root'
    (root / 'etc').mkdir(parents=True)
    result = _harness(template, _payload([_file('/srv/deep/nested/thing.conf', 'DEEP')]),
                      root, tmp_path)
    assert result.returncode == 0, result.stderr
    written = root / 'srv' / 'deep' / 'nested' / 'thing.conf'
    assert written.exists(), f'{template} did not create the parent directory\n{result.stderr}'
    assert written.read_text().strip() == 'DEEP'


@pytest.mark.skipif(not shutil.which('bash'), reason='needs bash')
@pytest.mark.parametrize('template', INSTALLERS)
def test_the_manifest_records_what_was_there_before(template, tmp_path):
    """The live applier reads this to decide what to put back. A file the image already
    had must be marked as pre-existing and copied to the backup, or unassigning the
    profile later would delete something Luna did not put there."""
    root = tmp_path / 'root'
    (root / 'etc').mkdir(parents=True)
    (root / 'etc' / 'existing.conf').write_text('THE-ORIGINAL\n')
    result = _harness(template, _payload([
        _file('/etc/existing.conf', 'MANAGED'),
        _file('/etc/fresh.conf', 'ALSO-MANAGED'),
    ]), root, tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((root / 'var/lib/luna/profiles/manifest.json').read_text())
    assert manifest['/etc/existing.conf']['existed_before'] is True
    assert manifest['/etc/fresh.conf']['existed_before'] is False
    backup = root / 'var/lib/luna/profiles/backup/etc/existing.conf'
    assert backup.read_text().strip() == 'THE-ORIGINAL', 'the original was not kept'
