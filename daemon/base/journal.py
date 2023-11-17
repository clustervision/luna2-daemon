#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#This code is part of the TrinityX software suite
#Copyright (C) 2023  ClusterVision Solutions b.v.
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>


"""
Journal class. handles internal journal calls
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


class Journal():
    """
    This class is responsible for journal data mangling.
    """

    def __init__(self):
        self.logger = Log.get_logger()


    def update_journal(self, request_data=None):
        """
        This method will return update requested node.
        """
        status = True
        response = "success"
        if request_data:
            data = request_data['journal']
            journal_columns = Database().get_columns('journal')
            for entry in data:
                if 'function' in entry and 'object' in entry:
                    self.logger.info(f"received: {data}")
                    columns_check = Helper().compare_list(entry, journal_columns)
                    if columns_check:
                        row = Helper().make_rows(entry)
                        request_id = Database().insert('journal', row)
                        if request_id:
                            self.logger.error(f"added {entry['function']}({entry['object']}) to the journal")
                        else:
                            response = f"failed adding {entry['function']}({entry['object']}) to the journal"
                            self.logger.error(f"failed adding {entry['function']}(entry['object']) to the journal")
                            return False, response
                    else:
                        response = 'Invalid request: Columns are incorrect'
                        return False, response
        else:
            response = 'Invalid request: Did not receive data'
            status = False
        return status, response

