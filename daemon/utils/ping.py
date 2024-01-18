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
simple ping class to register received ping times
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.helper import Helper
from utils.log import Log

class Ping():
    """
    This class is responsible for Ping related matter. used in conjunction with HA.
    """

    def __init__(self,me=None):
        self.logger = Log.get_logger()

    def update(self):
        ping={'updated': 'NOW'}
        row = Helper().make_rows(ping)
        result=Database().update('ping', row, [])
        if result:
            return True
        return False

    def received(self,last=False):
        ping=None
        if last:
            ping = Database().get_record(["strftime('%s', updated) AS updated"],'ping')
        else:
            ping = Database().get_record(["strftime('%s', updated) AS updated"],'ping',f"WHERE updated>datetime('now','-120 second')")
        self.logger.debug(f"last ping: {ping}")
        if ping:
            if last:
                return ping[0]['updated']
            return True
        return False

