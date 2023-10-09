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
This Is a Helper Class, which help the project to provide the common Methods.

"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

#from json import dumps
from utils.log import Log
from utils.helper import Helper
from utils.database import Database


class Model():
    """
    All kind of helper methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()


    def get_record(self, name=None, table=None, table_cap=None, ip_check=None, new_table=None):
        """
        This method will return the requested record from the table
        or all records if the name is not available.
        """
        status=False
        if name:
            all_records = Database().get_record(table=table, where=f' WHERE name = "{name}"')
        else:
            all_records = Database().get_record(table=table)
        if all_records:
            if new_table:
                config_table = new_table
            else:
                config_table = table
            response = {'config': {config_table: {} }}
            for record in all_records:
                record_id = record['id']
                del record['id']
                response['config'][config_table][record['name']] = record
                if ip_check:
                    ipaddress, network = Helper().get_ip_network(table=table, record_id=record_id)
                    if ipaddress:
                        response['config'][config_table][record['name']]['ipaddress'] = ipaddress
                        response['config'][config_table][record['name']]['network'] = network
            self.logger.info(f'Available {table_cap} are {all_records}.')
            status=True
        else:
            self.logger.error(f'No {table_cap} is available.')
            response = f'No {table_cap} is available'
            status=False
        return status, response


    def get_member(self, name=None, table=None, table_cap=None):
        """
        This method will return all the nodes which are member of a requested table.
        """
        status=False
        all_records = Database().get_record(table=table, where=f' WHERE name = "{name}"')
        if all_records:
            nodes = []
            record = all_records[0]
            record_id = record['id']
            response = {'config': {table: {name: {'members': []}} }}
            get_group_node = Database().get_record_join(
                ['node.name'],
                ['group.id=node.groupid'],
                [f"`group`.{table}id='{record_id}'"]
            )
            where = f' WHERE {table}id ="{record_id}"'
            get_record_node = Database().get_record(select=['name'], table='node', where=where)
            list_nodes = get_group_node + get_record_node
            if list_nodes:
                for node in list_nodes:
                    nodes.append(node['name'])
            if nodes:
                response['config'][table][name]['members'] = nodes
                self.logger.info(f'Provided all {table_cap} members for nodes {nodes}.')
                status=True
            else:
                self.logger.error(f'{table_cap} {name} is not have any member node.')
                response = f'{table_cap} {name} is not have any member node'
                status=False
        else:
            self.logger.error(f'{table_cap} {name} is not available.')
            response = f'{table_cap} {name} is not available'
            status=False
        return status, response


    def delete_record(self, name=None, table=None, table_cap=None, ip_check=None):
        """
        This method will delete the requested.
        """
        status=False
        record = Database().get_record(table=table, where=f' WHERE `name` = "{name}"')
        if record:
            if ip_check:
                ip_clause = [
                    {"column": "tablerefid", "value": record[0]['id']},
                    {"column": "tableref", "value": table}
                ]
                Database().delete_row('ipaddress', ip_clause)
                self.logger.info(f'{table_cap} linked IP Address is deleted.')
            Database().delete_row(table, [{"column": "name", "value": name}])
            self.logger.info(f'{table_cap} removed from database.')
            response = f'{table_cap} removed from database.'
            status=True
        else:
            self.logger.info(f'{name} is not present in the database.')
            response = f'{name} is not present in the database.'
            status=False
        return status, response


    def delete_record_by_id(self, id=None, table=None, table_cap=None, ip_check=None):
        """
        This method will delete the requested.
        """
        status=False
        record = Database().get_record(table=table, where=f' WHERE `id` = "{id}"')
        if record:
            if ip_check:
                ip_clause = [
                    {"column": "tablerefid", "value": record[0]['id']},
                    {"column": "tableref", "value": table}
                ]
                Database().delete_row('ipaddress', ip_clause)
                self.logger.info(f'{table_cap} linked IP Address is deleted.')
            Database().delete_row(table, [{"column": "id", "value": id}])
            self.logger.info(f'{table_cap} removed from database.')
            response = f'{table_cap} removed from database.'
            status=True
        else:
            self.logger.info(f'{name} is not present in the database.')
            response = f'{name} is not present in the database.'
            status=False
        return status, response


    def change_record(
            self,
            name=None,
            new_name=None,
            table=None,
            table_cap=None,
            request_data=None
        ):
        """
        This method will decide to create or update a record.
        """
        record = Database().get_record(table=table, where=f' WHERE `name` = "{name}"')
        if record or (new_name in request_data['config'][table][name]):
            status, response = self.update_record(
                record,
                name,
                new_name,
                table,
                table_cap,
                request_data
            )
        else:
            status, response = self.create_record(record ,name, table, table_cap, request_data)
        return status, response


    def create_record(self, record=None, name=None, table=None, table_cap=None, request_data=None):
        """
        This method will create a new record for requested table.
        """
        response = {}
        status=False
        data = request_data['config'][table][name]
        data['name'] = name
        if record:
            self.logger.info(f'{table_cap} already has {name}')
            response = f'{table_cap} already has {name}'
            status=False
        else:
            columns = Database().get_columns(table)
            column_check = Helper().compare_list(data, columns)
            if column_check:
                row = Helper().make_rows(data)
                Database().insert(table, row)
                self.logger.info(f'{name} successfully added in {table}')
                response = f'{name} successfully added in {table}'
                status=True
            else:
                self.logger.info('Incorrect column(s) provided.')
                response = 'Invalid request: Incorrect column(s) provided.'
                status=False
        return status, response


    def update_record(
            self,
            record=None,
            name=None,
            new_name=None,
            table=None,
            table_cap=None,
            request_data=None
        ):
        """
        This method will update a record for requested table.
        """
        response = {}
        status=False
        data = request_data['config'][table][name]
        if new_name in request_data['config'][table][name]:
            data['name'] = data[new_name]
            del data[new_name]
        else:
            data['name'] = name
        if record:
            columns = Database().get_columns(table)
            column_check = Helper().compare_list(data, columns)
            row = Helper().make_rows(data)
            if column_check:
                where = [{"column": "id", "value": record[0]['id']}]
                Database().update(table, row, where)
                response = f'{name} updated successfully'
                status=True
            else:
                self.logger.info('Incorrect column(s) provided.')
                response = 'Invalid request: Incorrect column(s) provided.'
                status=False
        else:
            self.logger.info(f'{name} is not present in {table_cap}.')
            response = f'{name} is not present in {table_cap}.'
            status=False
        return status, response


    def clone_record(self, name=None, new_name=None, table=None, table_cap=None, request_data=None):
        """
        This method will clone a record for requested table.
        """
        response = {}
        status=False
        data = request_data['config'][table][name]
        if new_name in request_data['config'][table][name]:
            data['name'] = data[new_name]
            new_record = data[new_name]
            del data[new_name]
        else:
            data['name'] = name
        record = Database().get_record(table=table, where=f' WHERE `name` = "{name}"')
        if record:
            where = f' WHERE `name` = "{new_record}"'
            check_new_record = Database().get_record(table=table, where=where)
            if check_new_record:
                response = f'{new_record} Already present in database'
                status=False
                return status, response
            del record[0]['id']
            for item in record[0]:
                if not item in data:
                    data[item] = record[0][item]

            columns = Database().get_columns(table)
            column_check = Helper().compare_list(data, columns)
            row = Helper().make_rows(data)
            if column_check:
                Database().insert(table, row)
                response = f'{name} cloned as {new_record} successfully'
                status=True
            else:
                self.logger.info('Incorrect column(s) provided.')
                response = 'Invalid request: Incorrect column(s) provided.'
                status=False
        else:
            self.logger.info(f'{name} is not present in {table_cap}.')
            response = f'{name} is not present in {table_cap}.'
            status=False
        return status, response
