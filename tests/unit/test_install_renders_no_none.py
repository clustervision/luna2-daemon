"""
Nothing the installer renders is the literal string None.

boot.py copies interface columns into the dictionary the install template
reads. Bash sees a Python None as the four-letter word None, and a plugin's
`if [ "$MTU" ]` is true for it: an interface without an MTU wrote mtu=None
into its NetworkManager keyfile. Every nullable column that is copied straight
across must carry a fallback; the template guards the address family fields
itself, so those are exempt.
"""

import os
import re

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'daemon')

# rendered only inside the template's own `if ipaddress` / dhcp branches, or never null
GUARDED_BY_TEMPLATE = {'interface', 'macaddress', 'ipaddress', 'ipaddress_ipv6', 'subnet',
                       'subnet_ipv6', 'networkid', 'network'}


def _copied_without_fallback():
    with open(os.path.join(DAEMON, 'base', 'boot.py'), encoding='utf-8') as handle:
        body = handle.read()
    found = []
    for match in re.finditer(r"^\s*'(\w+)':\s*interface\['(\w+)'\]\s*,?\s*$", body, re.M):
        key, column = match.groups()
        if column not in GUARDED_BY_TEMPLATE:
            found.append((key, column))
    return found


def test_every_nullable_interface_column_copied_into_the_installer_has_a_fallback():
    from utils.dbstructure import DBStructure
    nullable = set()
    for table in ('nodeinterface', 'ipaddress', 'network'):
        for column in DBStructure().get_database_table_structure(table):
            if 'key' not in column and column.get('default') is None:
                nullable.add(column['column'])
    offenders = [f"{key} <- interface['{column}']" for key, column in _copied_without_fallback()
                 if column in nullable]
    assert offenders == [], 'None would render as the word None for: ' + ', '.join(offenders)
