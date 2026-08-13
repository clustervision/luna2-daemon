#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
No live profile delivery. For nodes a controller cannot reach inbound - cloud, NAT, a
remote site - where the honest answer is that they converge when they are installed
rather than pretending a push will arrive.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log


class Plugin():
    """
    Class for declining to deliver profiles to a running node.
    """
    """
    This plugin class requires 1 mandatory method:
    -- deliver
    """

    def __init__(self):
        self.logger = Log.get_logger()

    def deliver(self, node=None, hostname=None, bundle=None, timeout=300):
        """
        Never claims success: recording a digest here would mark the node in sync when
        nothing was sent. It stays behind, and it stays visible as behind.
        """
        self.logger.info(f"live profile delivery is disabled for {node}; it will apply its "
                         "profiles when it installs")
        return False, 'live delivery not enabled for this node'
