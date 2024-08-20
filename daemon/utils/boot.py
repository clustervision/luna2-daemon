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
This Is a class to assist in Status related items. e.g. the cleanup thread lives here.

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue

class Boot(object):

    def __init__(self):
        self.logger = Log.get_logger()

    def verify_bootpause(self, osimage=None):
        """
        returns True when the daemon is busy with a osimage related and the node should wait
        """
        if osimage:
            cluster = Database().get_record(None, 'cluster')
            if cluster and cluster[0]['packing_bootpause']:
                packing_bootpause = Helper().make_bool(cluster[0]['packing_bootpause'])
                if packing_bootpause:
                    busy=Queue().tasks_in_queue(subsystem='osimage',task='pack_n_build_osimage',subitem=osimage)
                    if busy:
                        return True
        return False

    def we_are_sinking(self):
        """
        placeholder function for future syncing state check, e.g. daemon to daemon
        """
        return None 
