#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
An IPv6 controller address has to be bracketed in every URL the installer builds.
The bracket decision is made in bash from the rendered address, so the check runs
the rendered bash rather than reading it.
"""

import os
import subprocess

import pytest
from jinja2 import Template

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON = os.path.join(HERE, '..', '..', 'daemon')

RENDER = {
    'WEBSERVER_PROTOCOL': 'http', 'WEBSERVER_PORT': '7051', 'LUNA_API_PROTOCOL': 'http',
    'LUNA_API_PORT': '7050', 'LUNA_IMAGEFILE': 'compute.tar.bz2', 'LUNA_SYSTEMROOT': 'sysroot',
}

CONTROLLERS = [('fd00:141::254', '[fd00:141::254]'), ('10.141.255.254', '10.141.255.254')]


def _url_block(path):
    """The LUNA_URL block at the top of an installer template, as bash."""
    with open(path) as fh:
        lines = fh.read().split('\n')
    start = next(i for i, l in enumerate(lines) if l.startswith('if [ "$(echo'))
    return '\n'.join(lines[start:start + 5])


def _bash(script):
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize('template', ['templ_install.cfg', 'templ_install_lpart.cfg'])
@pytest.mark.parametrize('controller,expected', CONTROLLERS)
def test_the_installer_api_url_brackets_an_ipv6_controller(template, controller, expected):
    block = Template(_url_block(os.path.join(DAEMON, 'templates', template))).render(
        LUNA_CONTROLLER=controller, **RENDER)
    assert _bash(block + '\necho "$LUNA_URL"') == f'http://{expected}:7050'


@pytest.mark.parametrize('plugin', ['http', 'torrent'])
@pytest.mark.parametrize('controller,expected', CONTROLLERS)
def test_the_provision_plugin_downloads_from_a_bracketed_ipv6_controller(plugin, controller, expected, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        plugin, os.path.join(DAEMON, 'plugins', 'boot', 'provision', f'{plugin}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fetch = Template(module.Plugin.fetch).render(LUNA_CONTROLLER=controller, LUNA_TOKEN='t', **RENDER)
    # only the download decision is run: curl is a stub that records its URL (the
    # segment redirects curl's stdout, so it records to a file), cd does nothing, and
    # the segment is cut after the if/else that picks the URL form
    log = tmp_path / 'curl.log'
    decision = fetch.split('\n    fi\n')[0] + '\n    fi\n'
    script = f'curl() {{ for a in "$@"; do case "$a" in http*) echo "$a" >> {log};; esac; done; }}\n' \
             'cd() { :; }\nINTERFACE=""; LUNA_TOKEN=t\n' \
             + decision.replace('> /sysroot/', '> /dev/null #').replace('> compute.tar.bz2.torrent', '> /dev/null #')
    _bash(script)
    urls = log.read_text().split() if log.exists() else []
    assert urls, 'no curl call was made'
    assert all(f'http://{expected}:7051/files/' in u for u in urls), urls
