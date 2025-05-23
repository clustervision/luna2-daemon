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
Journal class tracks incoming requests that requires replication to other controllers.
It also receives requests that need to be dealt with by the controller itself.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from utils.database import Database
from utils.log import Log

class Controller():
    """
    This class is responsible for simple controller related help functions
    """

    def __init__(self):
        """
        room for comments/help
        """
        self.logger = Log.get_logger()

    def get_beacon(self):
        """
        This method will return the primary controller name of the cluster
        """
        controller = Database().get_record(None, 'controller', "WHERE controller.beacon=1")
        if controller:
            self.logger.debug(f"Returning {controller[0]['hostname']}")
            return controller[0]['hostname']
        self.logger.error('No controller available, going to return first found entry')
        controller = Database().get_record(None, 'controller', "ORDER BY id LIMIT 1")
        if controller:
            self.logger.warning(f"Returning {controller[0]['hostname']}")
            return controller[0]['hostname']
        self.logger.error('No controller available, returning last resort defaults')
        return 'controller'

    def get_beaconip(self):
        """
        This method will return the primary controller ip of the cluster
        """
        controller = Database().get_record_join(
            ['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
            ['ipaddress.tablerefid=controller.id'],
            ['tableref="controller"','controller.beacon=1']
        )
        if controller:
            if controller[0]['ipaddress_ipv6']:
                self.logger.debug("Returning {controller[0]['ipaddress_ipv6]}")
                return controller[0]['ipaddress_ipv6']
            self.logger.debug(f"Returning {controller[0]['ipaddress']}")
            return controller[0]['ipaddress']
        self.logger.error('No controller IP available, going to return first found entry')
        controller = Database().get_record(None, 'ipaddress', "WHERE tableref='controller' ORDER BY id LIMIT 1")
        if controller:
            if controller[0]['ipaddress_ipv6']:
                self.logger.warning("Returning {controller[0]['ipaddress_ipv6]}")
                return controller[0]['ipaddress_ipv6']
            self.logger.warning(f"Returning {controller[0]['ipaddress']}")
            return controller[0]['ipaddress']
        self.logger.error('No controller available, returning defaults')
        return '10.141.255.254'

    def get_controllers(self):
        """
        This method will return all controller details of the cluster
        """
        controllers = Database().get_record_join(
            ['controller.*', 'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'network.name as network'],
            ['ipaddress.tablerefid=controller.id', 'network.id=ipaddress.networkid'],
            ['tableref="controller"']
        )
        if not controllers:
            controllers = Database().get_record_join(
                ['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
                ['ipaddress.tablerefid=controller.id'],
                ['tableref="controller"']
            )
        all_controllers={}
        if controllers:
            for controller in controllers:
                all_controllers[controller['hostname']]={
                    'ipaddress': controller['ipaddress'],
                    'ipaddress_ipv6': controller['ipaddress_ipv6'],
                    'serverport': controller['serverport'],
                    'network': None,
                    'clusterid': controller['clusterid'],
                    'beacon': controller['beacon'],
                    'shadow': controller['shadow']
                }
                if 'network' in controller:
                    all_controllers[controller['hostname']]['network'] = controller['network'],
            return all_controllers
        self.logger.error('No controller available, returning defaults')
        all_controllers['controller']={
            'ipaddress': '10.141.255.254',
            'ipaddress_ipv6': None,
            'serverport': 7050,
            'network': 'cluster',
            'clusterid': 1,
            'beacon': True,
            'shadow': False
        }
        return all_controllers

