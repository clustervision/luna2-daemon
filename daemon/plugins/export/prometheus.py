
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
        self.services = {
            "node":  9100,
            "ipmi":  9102,
            "nvidia":  9103
        }

    # ---------------------------------------------------------------------------

    def export(self):
        status, all_nodes = Node().get_all_nodes()
        if status:
            if 'config' in all_nodes and 'node' in all_nodes['config']:
                targets = []
                data = all_nodes['config']['node']

                for service_name, service_port in self.services.items():
                    service_targets = [{
                            "targets": [f"{node['hostname']}:{service_port}" ],
                            "labels": {
                                "exporter": f"{service_name}",

                            },
                        }
                        for  node in data.values()
                    ]   
                    
                    for target, node in zip(service_targets, data.values()):
                        if 'group' in node and node['group']:
                            target['labels']['luna_group'] = node['group']

                        # if 'roles' in data[node] and data[node]['roles']:
                        #     target['labels']['luna_roles'] = data[node]['roles'][0]
                    targets.extend(service_targets)
                return True, targets
        return False, "Failed to generate export data"

