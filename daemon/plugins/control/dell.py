#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
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
Plugin Class :: Dell Power Control

Dell iDRAC speaks standards-based Redfish, so everything this plugin does lives in
the vendor-neutral plugin it inherits from - discovery, reset, identify and the
log services, each already falling back to ipmitool.

It stays as a file for two reasons: it is the name the search path resolves for a
Dell node, and it is where Dell-specific behaviour goes the day a board needs it.
A per-model override sits beside it as dell/<model>.py.

Selected by manufacturer: nodeinventory reports 'Dell Inc.', which the search path
normalises to 'dell'.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from plugins.control.redfish import Plugin as RedfishPlugin


class Plugin(RedfishPlugin):
    """Dell-specific control plugin. Standards-based behaviour is inherited."""
