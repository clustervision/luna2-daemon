
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
                structured['default'] = []
                data = all_nodes['config']['node']
                for node in data.keys():
                    if 'group' in data[node]:
                        if data[node]['group'] not in structured.keys():
                            structured[data[node]['group']] = []
                        structured[data[node]['group']].append(f"{data[node]['name']}:{self.port}")
                    else:
                        structured['default'].append(f"{data[node]['name']}:{self.port}")
                if len(structured['default']) < 1:
                    del structured['default']

                for group in structured.keys():
                    if group == 'default':
                        response.append({"targets": structured[group]})
                    else:
                        response.append({"targets": structured[group], "labels": { "__meta_group": group }})
                return True, response
        return False, "Failed to generate export data"

