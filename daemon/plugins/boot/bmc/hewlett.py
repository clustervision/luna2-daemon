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
Plugin Class :: HPE BMC - the same plugin as hpe.py

The search path resolves a plugin by what the hardware reports, normalised to a
filename. a board reporting 'Hewlett Packard Enterprise' normalises to its first word, 'hewlett',
so it arrives here rather than at hpe.py.

This exists as a file rather than as an entry in a lookup table on purpose: what
is supported is then visible in a directory listing, and a site whose hardware
reports something else adds one of these rather than waiting for us to extend a
table it cannot see.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from plugins.boot.bmc.hpe import Plugin as VendorPlugin


class Plugin(VendorPlugin):
    """HPE hardware, handled by hpe.py."""
