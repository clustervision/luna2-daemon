"""
Every name used in the daemon is defined on the path that uses it.

A NameError only fires when its line runs, and three of them sat for two years
on paths nobody exercised: an ospush of an image without a stored path, a
bmcsetup field with a boolean default, and the CLI's exit after a failed
service action. pyflakes finds the whole class in a second; this pins it.
"""

import os

import pytest

pyflakes_api = pytest.importorskip('pyflakes.api')
from pyflakes.reporter import Reporter  # noqa: E402

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'daemon')


class _Collect:
    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)

    def flush(self):
        pass


def test_no_undefined_name_anywhere_in_the_daemon():
    out = _Collect()
    pyflakes_api.checkRecursive([DAEMON], Reporter(out, out))
    undefined = [line.strip() for line in ''.join(out.lines).splitlines()
                 if 'undefined name' in line and 'may be undefined' not in line and 'unable to detect' not in line]
    assert undefined == [], 'names used but never defined on their path:\n' + '\n'.join(undefined)
