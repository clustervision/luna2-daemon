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
Cloud Class will handle all cloud operations.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.1"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"

from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.config import Config
from utils.service import Service
from utils.model import Model

class Cloud():
    """
    This class is responsible for all operations for cloud.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'cloud'
        self.table_cap = self.table.capitalize()


    def get_all_clouds(self):
        """
        This method will return all the clouds in detailed format.
        """
        status, response = Model().get_record(
            table = self.table,
            table_cap = self.table_cap,
            ip_check = False
        )
        return status, response


    def get_cloud(self, name=None):
        """
        This method will return requested cloud in detailed format.
        """
        status, response = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = False
        )
        return status, response


    def update_cloud(self, name=None, request_data=None):
        """
        This method will create or update a cloud.
        """
        status=False
        response="Internal error"
        network = False
        data, response = {}, {}
        create, update = False, False

        if request_data:
            data = request_data['config'][self.table][name]
            data['name'] = name
            where = f' WHERE `name` = "{name}"'
            check_cloud = Database().get_record(table=self.table, where=where)
            if check_cloud:
                cloudid = check_cloud[0]['id']
                if 'newcloudname' in request_data['config'][self.table][name]:
                    data['name'] = data['newcloudname']
                    del data['newcloudname']
                update = True
            else:
                create = True

            cloud_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, cloud_columns)
            row = Helper().make_rows(data)
            if column_check:
                if create:
                    cloudid = Database().insert(self.table, row)
                    response = f'Cloud {name} created successfully'
                    status=True
                if update:
                    where = [{"column": "id", "value": cloudid}]
                    Database().update(self.table, row, where)
                    response = f'Cloud {name} updated successfully'
                    status=True
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
            return status, response
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_cloud(self, name=None):
        """
        This method will delete a cloud.
        """
        status, response = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = False
        )
        return status, response

