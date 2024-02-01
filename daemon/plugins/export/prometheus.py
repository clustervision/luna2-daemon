
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Prometheus export class to export targets for dynamic/auto host/service detection
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from base.node import Node


class Plugin():
    """
    Class for exporting prometheus config
    """

    def __init__(self):
        """
        one defined method is mandatory:
        - export
        """
        self.port = 9100

    # ---------------------------------------------------------------------------

    def export(self):
        status, all_nodes = Node().get_all_nodes()
        if status:
            if 'config' in all_nodes and 'node' in all_nodes['config']:
                structured, response = {}, []
                data = all_nodes['config']['node']
                for node in data.keys():
                    labels = { "exporter": "node" }
                    if 'group' in data[node]:
                        labels['luna_group'] = data[node]['group']
                    #if 'roles' in data[node] and data[node]['roles']:
                    #    labels['luna_role'] = data[node]['roles'].replace(' ','').split(',')[0]
                    response.append({"targets": [f"{data[node]['hostname']}:{self.port}"], "labels": labels})
                return True, response
        return False, "Failed to generate export data"

