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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.database import Database
from utils.helper import Helper
from utils.log import Log
from utils.ha import HA


class Journal():
    """
    This class is responsible for journal data mangling.
    """

    def __init__(self):
        self.logger = Log.get_logger()


    def get_journal(self, host=None):
        where=""
        data=[]
        del_ids=[]
        if host:
            controller=None
            all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
            if all_controllers:
                dict_controllers_byname = Helper().convert_list_to_dict(all_controllers, 'hostname')
                dict_controllers_byipaddress = Helper().convert_list_to_dict(all_controllers, 'ipaddress')
                if host in dict_controllers_byname:
                    controller=host
                elif host in dict_controllers_byipaddress:
                    controller=dict_controllers_byipaddress[host]['hostname']
                if controller:
                    where=f"sendfor='{controller}'"
                    self.logger.debug(f"where: {where}")
        entries=Database().get_record(select=["*","strftime('%s',created) AS created"],
                                      table='journal', where=where, orderby='created,id')
        if entries:
            for entry in entries:
                del_ids.append(entry['id'])
                del entry['id']
                data.append(entry)
        if del_ids:
            for id in del_ids:
                Database().delete_row('journal', [{"column": "id", "value": id}])
        response={'journal': data}
        self.logger.debug(f"sending: {data}")
        return True, response


    def update_journal(self, request_data=None):
        """
        This method will add received journal entries to the journal
        """
        status = True
        response = "success"
        if request_data:
            data = request_data['journal']
            journal_columns = Database().get_columns('journal')
            for entry in data:
                if 'function' in entry and 'object' in entry:
                    self.logger.debug(f"received: {data}")
                    columns_check = Helper().compare_list(entry, journal_columns)
                    if columns_check:
                        row = Helper().make_rows(entry)
                        request_id = Database().insert('journal', row)
                        if request_id:
                            self.logger.info(f"added {entry['function']}({entry['object']}) to the journal")
                            HA().set_insync(False)
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


    def delete_journal(self, host=None):
        status=False
        response="Invalid request: no host specified"
        if host:
            status=True
            response="journal entries deleted"
            controller=None
            all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as domain'],
                                                          ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                                                          ["ipaddress.tableref='controller'"])
            if all_controllers:
                dict_controllers_byname = Helper().convert_list_to_dict(all_controllers, 'hostname')
                dict_controllers_byipaddress = Helper().convert_list_to_dict(all_controllers, 'ipaddress')
                if host in dict_controllers_byname:
                    controller=host
                elif host in dict_controllers_byipaddress:
                    controller=dict_controllers_byipaddress[host]['hostname']
                if controller:
                    where=f"sendfor='{controller}'"
                    self.logger.debug(f"where: {where}")
                    entries=Database().get_record(select=["id"],table='journal',where=where)
                    if entries:
                        for entry in entries:
                            self.logger.debug(f"journal entry deleting {entry['id']}, {where}")
                            Database().delete_row('journal', [{"column": "id", "value": entry['id']}])

        return status, response

