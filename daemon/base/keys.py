#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
The keys a change of an object type accepts, in the names the API answers them under.

Read from this controller's own table, so a client learns what this daemon takes rather
than what the newest one would.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.access import COLUMNS as ACCESS_COLUMNS

# Columns no change of any type carries, each with its reason.
EXCLUDED = {'id': 'the primary key, never sent',
            **{column: 'who may, changed through _chmod, _chgrp and _chown' for column in ACCESS_COLUMNS}}

# Per path segment: the table, the columns a change names otherwise, the columns it does
# not carry with the reason, and the keys it takes that are no column.
KEYS = {
    'node': {
        'table': 'node',
        'renamed': {'groupid': 'group', 'osimageid': 'osimage', 'osimagetagid': 'osimagetag',
                    'switchid': 'switch', 'cloudid': 'cloud', 'bmcsetupid': 'bmcsetup',
                    'redfishsetupid': 'redfishsetup', 'biosconfigid': 'biosconfig'},
        'excluded': {'status': 'answered from the install monitor, the column is not read',
                     'profiles_digest': 'written by the daemon once a node applied its profiles'},
        'body': ['newnodename', 'interfaces', 'routes'],
    },
    'group': {
        'table': 'group',
        'renamed': {'osimageid': 'osimage', 'osimagetagid': 'osimagetag', 'bmcsetupid': 'bmcsetupname',
                    'redfishsetupid': 'redfishsetupname', 'biosconfigid': 'biosconfig'},
        'excluded': {},
        'body': ['newgroupname', 'interfaces', 'routes'],
    },
    'osimage': {
        'table': 'osimage',
        'renamed': {'tagid': 'tag'},
        'excluded': {'changed': 'set by the rename itself'},
        'body': ['newosimage'],
    },
    'network': {
        'table': 'network',
        'renamed': {},
        'excluded': {'subnet': 'carried by network, in CIDR notation',
                     'subnet_ipv6': 'carried by network, in CIDR notation',
                     'network_ipv6': 'an IPv6 network is sent as network',
                     'gateway_ipv6': 'an IPv6 gateway is sent as gateway',
                     'dhcp_range_begin_ipv6': 'an IPv6 range is sent as dhcp_range_begin',
                     'dhcp_range_end_ipv6': 'an IPv6 range is sent as dhcp_range_end',
                     'nameserver_ip_ipv6': 'IPv6 name servers are sent in nameserver_ip'},
        'body': ['newnetname', 'clear', 'routes'],
    },
    'switch': {
        'table': 'switch',
        'renamed': {},
        'excluded': {},
        'body': ['newswitchname', 'ipaddress', 'network', 'nonetwork'],
    },
    'otherdev': {
        'table': 'otherdevices',
        'renamed': {},
        'excluded': {},
        'body': ['newotherdevname', 'ipaddress', 'network', 'nonetwork'],
    },
    'bmcsetup': {
        'table': 'bmcsetup',
        'renamed': {},
        'excluded': {},
        'body': ['newbmcname'],
    },
    'cluster': {
        'table': 'cluster',
        'renamed': {},
        'excluded': {},
        # controller is the beacon's address; the other controllers go by their hostnames
        'body': ['controller', 'controller_network'],
    },
}


class Keys():
    """
    This class answers which keys a change of an object type accepts.
    """

    def get_keys(self, segment=None):
        """
        Input - the path segment of an object type
        Output - the keys a change of that type accepts, sorted, in the API's names
        """
        found = KEYS[segment]
        excluded = set(EXCLUDED) | set(found['excluded'])
        keys = {found['renamed'].get(column, column)
                for column in Database().get_columns(found['table']) if column not in excluded}
        return {'keys': sorted(keys | set(found['body']))}
