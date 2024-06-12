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
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
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

    def get_me(self):
        """
        This method will return the primary controller name of the cluster
        """
        controller = Database().get_record(None, 'controller', "WHERE controller.beacon=1")
        if controller:
            self.logger.debug("Returning {controller[0]['hostname']}")
            return controller[0]['hostname']
        self.logger.error('No controller available, returning defaults')
        return 'controller'

