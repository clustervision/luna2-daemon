#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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

This Class Identify the specified Database Connection from Configuration
and return the Cursor of correct Database.
Database have the default methods for CRUD. In case of changing database
model doesn't impact the application.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


import re
import threading
from time import sleep
import sqlite3
import pyodbc
from utils.log import Log
from common.constant import CONSTANT

local_thread = threading.local()


class Database():

    """
    Database Connector Class with all basic functions.
    """

    def __init__(self):
        """
        Constructor - Initialize The Correct Database from the conf file.
        """
        self.logger = Log.get_logger()
        self.driver = f'DRIVER={CONSTANT["DATABASE"]["DRIVER"]};'
        self.server = f'SERVER={CONSTANT["DATABASE"]["HOST"]};'
        self.database = f'DATABASE={CONSTANT["DATABASE"]["DATABASE"]};'
        self.uid = f'UID={CONSTANT["DATABASE"]["DBUSER"]};'
        self.password = f'PWD={CONSTANT["DATABASE"]["DBPASSWORD"]};'
        self.encoding = 'charset=utf8mb4;'
        self.port = f'PORT={CONSTANT["DATABASE"]["PORT"]};'
        self.connection_string = f'{self.driver}{self.server}{self.database}{self.uid}'
        self.connection_string += f'{self.password}{self.encoding}{self.port};'
        self.connection_string += 'MultipleActiveResultSets=True;MARS_Connection=yes;Pooling=True'
        # self.connection = pyodbc.connect(self.connection_string)
        # self.cursor = local.connection.cursor()
        # the below 5 lines ensure that each thread gets it's own connection.
        # it's a MUST for pyodbc - Antoine
        connection = getattr(local_thread, 'connection', None)
        if connection is None:
            if "DATABASE" in CONSTANT and "DRIVER" in CONSTANT["DATABASE"] and CONSTANT["DATABASE"]["DRIVER"] == "SQLite3":
                message = f"====> Trying SQLite3 driver {threading.current_thread().name} <===="
                self.logger.debug(message)
                if "DATABASE" in CONSTANT["DATABASE"]:
                    attempt = 1
                    while attempt < 100:
                        try:
                            local_thread.connection = sqlite3.connect(CONSTANT["DATABASE"]["DATABASE"])
                            local_thread.connection.execute('pragma journal_mode=wal')
                            local_thread.connection.execute('pragma busy_timeout=5000')
                            local_thread.connection.execute('pragma synchronous=1')
                            local_thread.connection.isolation_level = None
                            local_thread.cursor = local_thread.connection.cursor()
                            break
                        except Exception as exp:
                            message = f"Problem '{exp}' while connecting to Database on attempt "
                            message += f"{attempt}... i try again in a few seconds..."
                            self.logger.info(message)
                            sleep(10)
                            attempt += 1
            else:
                message = f"====> Trying pyodbc driver {threading.current_thread().name} <===="
                self.logger.debug(message)
                local_thread.connection = pyodbc.connect(self.connection_string)
                ## local_thread.connection.autocommit = True
                local_thread.cursor = local_thread.connection.cursor()
            message = f"===> Established DB connection for {threading.current_thread().name} <==="
            self.logger.debug(message)


    def commit(self):
        """
        This method will commit the local thread.
        """
        if "DATABASE" in CONSTANT and "DRIVER" in CONSTANT["DATABASE"] and CONSTANT["DATABASE"]["DRIVER"] == "SQLite3":
            local_thread.connection.commit()
        else:
            local_thread.cursor.commit()


    def check_db(self):
        """
        Input - None
        Process - Check If Database is Active, Readable and Writable.
        Output - Result/None.
        """
        try:
            local_thread.cursor.execute('SELECT * FROM user')
            result = local_thread.cursor.fetchone()
        except Exception as exp:
            self.logger.error(f'Error while checking database => {exp}.')
            result = None
        return result


    def get_sequence(self, name=None):
        """
        Input - table name fixed: SQLITE_SEQUENCE. name of column optional
        Output - returns sequence numbers of next autoincrement
        """
        where = None
        if name:
            where = f" WHERE `name`='{name}';"
        data=self.get_record(None,'SQLITE_SEQUENCE', where)
        if data:
            if name:
                return data[0]['seq']
            else:
                return data
        return None


    def update_sequence(self, name=None, seq=None):

        """
        Input -  name and seq(uence)
        Output - Update the rows.
        """
        if not name or not seq:
            return None
        row=[{"column": "seq", "value": seq}]
        where=[{"column": "name", "value": name}]
        return self.update('SQLITE_SEQUENCE', row, where)


    def get_record(self, select=None, table=None, where=None):
        """
        Input - select fields, tablename, where clause
        Process - It is SELECT operation on the DB.
                    select can be comma separated column name or None.
                    table is the table name where the select operation should be happen.
                    where can be None OR complete where condition
        Output - Fetch rows along with column name.
        """
        if select:
            column_string = ','.join(map(str, select))
        else:
            column_string = "*"
        if where:
            where = re.sub(';$', '', where)
            query = f'SELECT {column_string} FROM "{table}" {where};'
        else:
            query = f'SELECT {column_string} FROM "{table}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            local_thread.cursor.execute(query)
            names = list(map(lambda x: x[0], local_thread.cursor.description))
            # Fetching the Column Names
            data = local_thread.cursor.fetchall()
            self.logger.debug(f'Dataset retrieved => {data}.')
            row_dict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    row_dict[key] = value
                response.append(row_dict)
                row_dict = {}
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def convert_string_to_list(self, text=None):
        """
        This method convert string to list.
        """
        response = []
        if isinstance(text, str):
            response.append(str(text))
        else:
            response = text
        return response


    def get_record_join(self, select=None, join_on=None, where=None):
        """
        Input - Complete SQL query with Joins
        Process - It is SELECT operation on the DB.
                    select can be comma separated column name or None.
                    table is the table name where the select operation should be happen.
                    where can be None OR complete where condition
        Output - Fetch rows along with column name.
        """

        ## ------------------------- NOTE NOTE NOTE -------------------------------
        ## The code below is actively used and works as intended. it looks a bit messy
        ## but optimizing will most probably obscure what's happening.
        # i therefor left it as is for now.
        ## Antoine
        ## ------------------------------------------------------------------------

        if select:
            # column_string = ','.join(map(str, select))
            cols = []
            select=  self.convert_string_to_list(select)
            for each in select:
                table, col = each.split('.', 1)
                # str_output = re.sub(regex_search_term, regex_replacement, str_input)
                col = re.sub('(as|AS) (.+)', r"AS `\2`", col)
                if col:
                    cols.append(f"`{table}`.{col}")
                else:
                    cols.append(f"`{table}`")
            column_string = ','.join(cols)
        else:
            column_string = "*"
        if join_on:
            # in here we do two things. we dissect the joins,
            # polish them (`) and we gather the involved tables
            join_on = self.convert_string_to_list(join_on)
            joins = []
            tables = []
            for each in join_on:
                left, right = each.split('=')
                left_table, left_column = left.split('.')
                right_table, right_column = right.split('.')
                joins.append(f"`{left_table}`.{left_column}=`{right_table}`.{right_column}")
                if left_table not in tables:
                    tables.append(left_table)
                if right_table not in tables:
                    tables.append(right_table)
            # table_string = ','.join(join_on.map(lambda x:x.split('.',1)[0]))
            # map(lambda x:x.split('.', 1)[0])
            table_string = '`,`'.join(tables)
            join_string = ' AND '.join(joins)
        else:
            # no join? we give up. this function is called _join so you better specify one
            response = None
            return response
        if where:
            where=self.convert_string_to_list(where)
            join_where = ' AND '.join(map(str, where))
        if where and join_on:
            query = f'SELECT {column_string} FROM `{table_string}` WHERE {join_string}'
            query += f' AND {join_where};'
        elif join_on:
            query = f'SELECT {column_string} FROM `{table_string}` WHERE {join_string};'
        else:
            response = None
            return response
        self.logger.debug(f'Query executing => {query}.')
        try:
            local_thread.cursor.execute(query)
            names = list(map(lambda x: x[0], local_thread.cursor.description))
            # Fetching the Column Names
            data = local_thread.cursor.fetchall()
            self.logger.debug(f'Dataset retrieved => {data}.')
            row_dict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    row_dict[key] = value
                response.append(row_dict)
                row_dict = {}
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def get_record_query(self, query=None):
        """
        Input - Complete SQL query with Joins
        Process - It is SELECT operation on the DB.
                    select can be comma separated column name or None.
                    table is the table name where the select operation should be happen.
                    where can be None OR complete where condition
        Output - Fetch rows along with column name.
        """
        self.logger.debug(f'Query executing => {query}.')
        try:
            local_thread.cursor.execute(query)
            names = list(map(lambda x: x[0], local_thread.cursor.description))
            # Fetching the Column Names
            data = local_thread.cursor.fetchall()
            self.logger.debug(f'Dataset retrieved => {data}.')
            row_dict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    row_dict[key] = value
                response.append(row_dict)
                row_dict = {}
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def create(self, table=None, column=None):
        """
        Input - tablename and column
        Process - It is Create operation on the DB.
            table is the table name which need to be created.
            column is a list of dict ex:
            where = [
                {"column": "id", "datatype": "INTEGER", "length": "10", "key": "PRIMARY", 
                "keyadd": "autoincrement"},
                {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE"},
                {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE", 
                "with": "name"},
                {"column": "name", "datatype": "VARCHAR", "length": "40"}]
        Output - Creates Table.
        """
        driver = f'{CONSTANT["DATABASE"]["DRIVER"]}'
        # either MySQL, SQLite, or...
        if driver == "SQLite3":
            driver = "SQLite"
        columns = []
        key_list  = []
        for cols in column:
            column_string = ''
            if 'column' in cols.keys():
                column_string = column_string + ' `' + cols['column'] + '` '
            if 'datatype' in cols.keys():
                column_string = column_string + ' ' +cols['datatype'].upper() + ' '
            if 'length' in cols.keys():
                if driver != "SQLite" and 'keyadd' in cols.keys() and cols['keyadd'].upper() == "AUTOINCREMENT":
                    # YES! sqlite does not allow e.g. INTEGER(10) to be
                    # an auto increment... _has_ to be INTEGER
                    column_string = column_string + ' (' +cols['length'] + ') '
            if 'key' in cols.keys() and 'column' in cols.keys():
                if cols['key'] == "PRIMARY":
                    if 'keyadd' in cols.keys():
                        if cols['keyadd'].upper() == "AUTOINCREMENT":
                            # then it must a an INT or FLOAT
                            column_string = column_string + " NOT NULL "
                            if driver != "SQLite":
                                # e.g. Mysql
                                column_string = column_string + "AUTO_INCREMENT "
                        if driver == "SQLite":
                            a_key = f"PRIMARY KEY (`{cols['column']}` {cols['keyadd'].upper()})"
                            key_list.append(a_key)
                            a_key = ''
                        else:
                            key_list.append(f"PRIMARY KEY (`{cols['column']}`)")
                    else:
                        key_list.append(f"PRIMARY KEY (`{cols['column']}`)")
                else:
                    if 'with' not in cols:
                        key_list.append(f"{cols['key'].upper()} (`{cols['column']}`)")
            if 'with' in cols.keys() and 'column' in cols.keys():
                key_list.append(f"UNIQUE (`{cols['column']}`,`{cols['with']}`)")
            if len(column_string)>0:
                columns.append(column_string)
        if key_list:
            join_keys = ', '.join(map(str, key_list))
            columns.append(join_keys)
        column_strings = ', '.join(map(str, columns))
        query = f'CREATE TABLE IF NOT EXISTS `{table}` ({column_strings})'
        self.logger.debug(f"Query executing => {query}")
        try:
            local_thread.cursor.execute(query)
            self.commit()
            response = True
        except Exception as exp:
            self.logger.error(f'Error while creating table {table}. Error: {exp}')
            response = False
        return response


    def add_column(self, table=None, column=None):
        """
        Input - tablename and column
        Process - It is Create operation on the DB.
            table is the table name which need to be created.
            column is a list of dict ex:
            where = [
                {"column": "id", "datatype": "INTEGER", "length": "10", "key": "PRIMARY", 
                "keyadd": "autoincrement"},
                {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE"},
                {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE", 
                    "with": "name"},
                {"column": "name", "datatype": "VARCHAR", "length": "40"}]
        Output - adds column to table.
        """
        column_string, key_query = '', []
        if 'column' in column.keys():
            column_string = column_string + ' `' + column['column'] + '` '
        if 'datatype' in column.keys():
            column_string = column_string + ' ' +column['datatype'].upper() + ' '
        if 'length' in column.keys():
            column_string = column_string + ' (' +column['length'] + ') '
        if 'key' in column.keys() and 'column' in column.keys():
            if column['key'] == "UNIQUE":
                if 'with' in column:
                    key_query.append(f"CREATE UNIQUE INDEX {column['column']}_{column['with']} ON `{table}`(`{column['column']}`,`{column['with']}`)")
                else:
                    key_query.append(f"CREATEUNIQUE INDEX {column['column']}_index ON `{table}`(`{column['column']}`)")

        query = f'ALTER TABLE `{table}` ADD {column_string}'
        self.logger.debug(f"Query executing => {query}")
        try:
            local_thread.cursor.execute(query)
            self.commit()
            response = True
        except Exception as exp:
            self.logger.error(f'Error while adding column to {table}. Error: {exp}')
            response = False
        if len(key_query) > 0:
            try:
                for query in key_query:
                    local_thread.cursor.execute(query)
                self.commit()
                response = True
            except Exception as exp:
                self.logger.error(f'Error while creating indexes on {table}. Error: {exp}')
                response = False
        return response


    def truncate(self, table=None):
        """
        Input - tablename
        Process - Truncate the table.
        Output - Success or Failure.
        """
        try:
            query = f'DELETE FROM "{table}";'
            local_thread.cursor.execute(query)
            self.commit()
            query = f'DELETE FROM sqlite_sequence WHERE name ="{table}";'
            local_thread.cursor.execute(query)
            self.commit()
            response = True
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = False
        return response


    def insert(self, table=None, row=None, replace=False):
        """
        Input - tablename and row
        Process - It is Create operation on the DB.
                    table is the table name which need to be created.
                    row is a list of dict ex: row =
        [{"column": "name", "value": "node004"}, {"column": "ip", "value": "10.141.0.1"}]
        Output - Creates Table.
        """
        keys, values = [], []
        where_keys, where_values = [], []
        where = ' WHERE '
        insert='INSERT'
        if replace is True:
            insert='REPLACE'
        response = False
        if row:
            for each in row:
                keys.append('"'+str(each["column"])+'"')
                if str(each["column"]) == "created" or str(each["column"]) == "updated":
                    # wee ugly but fast.
                    if str(each["value"]) == "NOW":
                        values.append("datetime('now')")
                    else:
                        result = re.search(
                            r"^NOW\s*(\+|\-)\s*([0-9]+)\s*(hour|minute|second)$",
                            str(each["value"])
                        )
                        if result:
                            symbol = result.group(1)
                            time_value = result.group(2)
                            time_denom = result.group(3)
                            if symbol and time_value and time_denom:
                                values.append(f"datetime('now','{symbol}{time_value} {time_denom}')")
                                # only sqlite complaint! pending
                            else:
                                values.append('datetime('+str(each["value"])+',"unixepoch")')
                        else:
                            values.append('datetime('+str(each["value"])+',"unixepoch")')
                else:
                    if each["value"] is not None:
                        values.append('"'+str(each["value"])+'"')
                    else:
                        values.append('NULL')
            where_keys = keys
            where_values = values
            keys = ','.join(keys)
            values = ','.join(values)
        query = f'{insert} INTO "{table}" ({keys}) VALUES ({values});'
        self.logger.debug(f"Insert Query ---> {query}")
        attempt = 1
        while (not response) and attempt < 10:
            try:
                local_thread.cursor.execute(query)
                self.commit()
                new_where = where
                where_list = []
                for key,value in zip(where_keys, where_values):
                    if value == "NULL":
                        continue
                    where_list.append(f'{key} = {value}')
                if len(where_list) > 0:
                    new_where = new_where + ' AND '.join(where_list)
                result = self.get_record(None, table, new_where)
                if result:
                    response = True
                    if 'id' in result[0]:
                        response = result[0]['id']
            except Exception as exp:
                message = f'Error occur while executing => {query}. error is "{exp}" '
                message += f'on attempt {attempt}.'
                self.logger.error(message)
                if f"{exp}" == "database is locked":
                    attempt += 1
                    sleep(3)
                else:
                    break
        return response


    def update(self, table=None, row=[], where=[]):
        """
        Input - tablename, row, and where clause
        Process - It is SELECT operation on the DB.
                    table is the table name where the update operation should be happen.
                    row can be None for all OR a list of dict ex: where =
                    [{"column": "name", "value": "cluster"}, {"column": "network", "value": "ib"}]
                    where can be None for all OR a list of dict ex: where =
                    [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
        Output - Update the rows.
        """
        column_strings, columns, where_list, join_where = None, [], [], None
        for cols in row:
            column = ''
            cur_col = None
            if 'column' in cols.keys():
                column = column + "`" + cols['column'] + "`"
                cur_col = cols['column']
            if 'value' in cols.keys():
                if str(cur_col) == "created" or str(cur_col) == "updated":
                    # wee ugly but fast.
                    if str(cols["value"]) == "NOW":
                        column = column + " = datetime('now')"
                    else:
                        result = re.search(
                            r"^NOW\s*(\+|\-)\s*([0-9]+)\s*(hour|minute|second)$",
                            str(cols["value"])
                        )
                        if result:
                            symbol = result.group(1)
                            time_value = result.group(2)
                            time_denom = result.group(3)
                            if symbol and time_value and time_denom:
                                column = column + f" = datetime('now','{symbol}{time_value} {time_denom}')"
                                # only sqlite compliant! pending
                            else:
                                column = column + f" = datetime({cols['value']}, 'unixepoch')"
                        else:
                            column = column + f" = datetime({cols['value']}, 'unixepoch')"
                else:
                    if cols['value'] is not None:
                        column = column + ' = "' +str(cols['value']) +'"'
                    else:
                        column = column + ' = NULL'
            columns.append(column)
            column_strings = ', '.join(map(str, columns))
        if not column_strings:
            self.logger.error("column_strings is empty. no cols in row?")
            return False
        for cols in where:
            column = ''
            if 'column' in cols.keys():
                column = column + cols['column']
            if 'value' in cols.keys():
                if cols['value'] is not None:
                    column = column + ' = "' +str(cols['value']) +'"'
                else:
                    column = column + ' = NULL'
            where_list.append(column)
            join_where = ' AND '.join(map(str, where_list))
        if join_where:
            query = f'UPDATE "{table}" SET {column_strings} WHERE {join_where};'
        else:
            query = f'UPDATE "{table}" SET {column_strings};'
        self.logger.debug(f"Update Query ---> {query}")
        attempt = 1
        while attempt < 10:
            try:
                local_thread.cursor.execute(query)
                self.commit()
                if local_thread.cursor.rowcount < 1:
                    return False
                else:
                    return True
            except Exception as exp:
                message = f'Error occur while executing => {query}. error is "{exp}"'
                message += f' on attempt {attempt}.'
                self.logger.error(message)
                if f"{exp}" == "database is locked":
                    attempt += 1
                    sleep(3)
                else:
                    break
        return False


    def delete_row(self, table=None, where=None):
        """
        Input - tablename and where clause
        Process - It is SELECT operation on the DB.
                    table is the table name where the update operation should be happen.
                    where can be None for all OR a list of dict ex: where =
        [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
        Output - Delete the row.
        """
        where_list = []
        for cols in where:
            column = ''
            if 'column' in cols.keys():
                column = column + cols['column']
            if 'value' in cols.keys():
                column = column + ' = "' +str(cols['value']) +'"'
            where_list.append(column)
            join_where = ' AND '.join(map(str, where_list))
        attempt=1
        while attempt<10:
            try:
                query = f'DELETE FROM "{table}" WHERE {join_where};'
                local_thread.cursor.execute(query)
                self.commit()
                return True
            except Exception as exp:
                message = f'Error occur while executing => {query}. error is "{exp}" '
                message += f'on attempt {attempt}.'
                self.logger.error(message)
                if f"{exp}" == "database is locked":
                    attempt += 1
                    sleep(3)
                else:
                    break
        return False


    def clear(self, table, excluding=None):
        """
        This method will do truncate the table.
        """
        try:
            query = f'DELETE FROM "{table}";'
            if excluding:
                query = f'DELETE FROM "{table}" WHERE {excluding};'
            local_thread.cursor.execute(query)
            self.commit()
            response = True
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = False
        return response


    def get_columns(self, table=None):
        """
        Input - select fields, tablename, where clause
        Process - It is SELECT operation on the DB.
                    select can be comma separated column name or None.
                    table is the table name where the select operation should be happen.
                    where can be None OR complete where condition
        Output - Fetch rows along with column name.
        """
        query = f'SELECT * FROM "{table}" LIMIT 1;'
        self.logger.debug(f'Query Executing => {query} .')
        try:
            local_thread.cursor.execute(query)
            # Fetching the Column Names
            response = list(map(lambda x: x[0], local_thread.cursor.description))
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def id_by_name(self, table=None, name=None):
        """
        Input - tablename, name
        Output - id.
        """
        query = f'SELECT id FROM "{table}" WHERE `name` == "{name}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            local_thread.cursor.execute(query)
            response = local_thread.cursor.fetchone()
            self.logger.debug(f'Dataset retrieved => {response}.')
            if response:
                response = response[0]
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def name_by_id(self, table=None, tableid=None):
        """
        Input - tablename, id
        Output - name.
        """
        query = f'SELECT name FROM "{table}" WHERE `id` == "{tableid}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            local_thread.cursor.execute(query)
            response = local_thread.cursor.fetchone()
            self.logger.debug(f'Dataset retrieved => {response}.')
            if response:
                response = response[0]
        except Exception as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response
