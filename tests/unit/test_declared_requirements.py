"""
Everything the daemon imports is in requirements.txt.

This list goes wrong one way only: a package arrives through another package's
dependencies, gets imported directly, and nobody declares it. It works for as
long as whatever was pulling it in keeps doing so. jinja2 sat like that for
years - imported by the boot routes to render the iPXE templates, declared
nowhere, present only because Flask wanted it.

Scoped to daemon/ - what ships - so a test or a tool needing something extra is
not a packaging error.
"""

import ast
import os
import re
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DAEMON = os.path.join(ROOT, 'daemon')

# A distribution is named one thing and imported as another often enough to matter.
IMPORTED_AS = {
    'pyjwt': 'jwt',
    'pyyaml': 'yaml',
    'python-pam': 'pam',
    'python-hostlist': 'hostlist',
}

# Imported inside a try because a controller may not have them. The installer puts
# them there per cluster - config-slurm only where Slurm is the workload manager -
# and the daemon runs without them. Declaring them would make them required.
OPTIONAL = {
    'trinityx_config_slurm',
    'trinityx_config_genders',
}


def _declared():
    """
    The import names requirements.txt accounts for.
    """
    names = set()
    with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name = re.split(r'[=<>!~\[]', line)[0].strip().lower()
            names.add(IMPORTED_AS.get(name, name.replace('-', '_')))
    return names


def _local():
    """
    The daemon's own top-level modules and packages, which are not dependencies.
    """
    names = set()
    for entry in os.listdir(DAEMON):
        if entry.endswith('.py'):
            names.add(entry[:-3])
        elif os.path.isdir(os.path.join(DAEMON, entry)):
            names.add(entry)
    return names


def test_every_package_the_daemon_imports_is_declared():
    declared, local = _declared(), _local()
    missing = {}
    for folder, _, files in os.walk(DAEMON):
        if '__pycache__' in folder:
            continue
        for name in files:
            if not name.endswith('.py'):
                continue
            source = os.path.join(folder, name)
            with open(source, encoding='utf-8') as handle:
                with warnings.catch_warnings():
                    # Parsing every file surfaces each one's own syntax warnings, which
                    # are nothing to do with what this test is checking.
                    warnings.simplefilter('ignore')
                    tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    heads = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                    heads = [node.module.split('.')[0]]
                else:
                    continue
                for head in heads:
                    if (head in sys.stdlib_module_names or head in local
                            or head.lower() in declared or head in OPTIONAL):
                        continue
                    missing[head] = os.path.relpath(source, ROOT)

    assert missing == {}, ('imported but not in requirements.txt: ' + repr(missing) +
                          '. Declare it, or import it inside a try and list it in '
                          'OPTIONAL here.')
