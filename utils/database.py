#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This Class Identify the specified Database Connection from Configuration
and return the Cursor of correct Database.
Database have the default methods for CRUD. In case of changing database
model dosn't impact the application.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


import pyodbc
from utils.log import Log
from common.constant import CONSTANT
import re

class Database(object):

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
        self.pswd = f'PWD={CONSTANT["DATABASE"]["DBPASSWORD"]};'
        self.encoding = 'charset=utf8mb4;'
        self.port = f'PORT={CONSTANT["DATABASE"]["PORT"]};'
        self.connection_string = f'{self.driver}{self.server}{self.database}{self.uid}{self.pswd}'
        self.connection_string = f'{self.connection_string}{self.encoding}{self.port}'
        self.connection = pyodbc.connect(self.connection_string)
        self.cursor = self.connection.cursor()

    def get_cursor(self):
        """
        Input - None
        Output - Return Cursor Od Database.
        """
        return self.cursor


    def check_db(self):
        """
        Input - None
        Process - Check If Database is Active, Readable and Writable.
        Output - Result/None.
        """
        try:
            self.cursor.execute('SELECT * FROM user')
            result = self.cursor.fetchone()
        except pyodbc.Error as exp:
            self.logger.error(f'Error while checking database => {exp}.')
            result = None
        return result


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
            strcolumn = ','.join(map(str, select))
        else:
            strcolumn = "*"
        if where:
            query = f'SELECT {strcolumn} FROM "{table}" {where};'
        else:
            query = f'SELECT {strcolumn} FROM "{table}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            self.cursor.execute(query)
            names = list(map(lambda x: x[0], self.cursor.description)) # Fetching the Column Names
            data = self.cursor.fetchall()
            self.logger.debug(f'Dataset retrived => {data}.')
            rowdict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    rowdict[key] = value
                response.append(rowdict)
                rowdict = {}
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response

    def convert_string_to_list(self,myitem):
        if type(myitem) == type('string'):
            mylist=[]
            mylist.append(str(myitem))
        else:
            mylist=myitem
        return mylist

    def get_record_join(self, select=None, joinon=None, where=None):
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
        ## but optimizing will most probably obscure what's happening. i therefor left it as is for now.
        ## Antoine
        ## ------------------------------------------------------------------------

        if select:
            #strcolumn = ','.join(map(str, select))
            cols=[]
            select=self.convert_string_to_list(select)
            for eachselect in select:
                table,col=eachselect.split('.',1)
                #str_output = re.sub(regex_search_term, regex_replacement, str_input)
                col = re.sub('(as|AS) (.+)', r"AS `\2`", col)
                if col:
                    cols.append(f"`{table}`.{col}")
                else:
                    cols.append(f"`{table}`")
            strcolumn = ','.join(cols)
        else:
            strcolumn = "*"
        if joinon:
            """
            in here we do two things. we disect the joins, polish them (`) and we gather the involved tables
            """
            joinon=self.convert_string_to_list(joinon)
            joins=[]
            tables=[]
            for eachjoin in joinon:
                left,right=eachjoin.split('=')
                lefttable,leftcol=left.split('.')
                righttable,rightcol=right.split('.')
                joins.append(f"`{lefttable}`.{leftcol}=`{righttable}`.{rightcol}")
                if lefttable not in tables:
                    tables.append(lefttable)
                if righttable not in tables:
                    tables.append(righttable)
            #print(tables)
            #tablestr = ','.join(joinon.map(lambda x:x.split('.',1)[0])) #    map(lambda x:x.split('.', 1)[0])
            tablestr = '`,`'.join(tables)
            strjoin = ' AND '.join(joins)
        else: # no join? we give up. this function is called _join so you better specify one
            response = None
            return response
        if where:
            where=self.convert_string_to_list(where)
            strwhere = ' AND '.join(map(str, where))
        if where and joinon:
            query = f'SELECT {strcolumn} FROM `{tablestr}` WHERE {strjoin} AND {strwhere};'
        elif joinon:
            query = f'SELECT {strcolumn} FROM `{tablestr}` WHERE {strjoin};'
        else:       
            response = None
            return response
#        self.logger.debug(f'Query executing => {query}.')
        print(f'Query executing => {query}.')
        try:
            self.cursor.execute(query)
            names = list(map(lambda x: x[0], self.cursor.description)) # Fetching the Column Names
            data = self.cursor.fetchall()
            self.logger.debug(f'Dataset retrived => {data}.')
            rowdict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    rowdict[key] = value
                response.append(rowdict)
                rowdict = {}
        except pyodbc.Error as exp:
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
            self.cursor.execute(query)
            names = list(map(lambda x: x[0], self.cursor.description)) # Fetching the Column Names
            data = self.cursor.fetchall()
            self.logger.debug(f'Dataset retrived => {data}.')
            rowdict = {}
            response = []
            for row in data:
                for key, value in zip(names,row):
                    rowdict[key] = value
                response.append(rowdict)
                rowdict = {}
        except pyodbc.Error as exp:
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
                        {"column": "id", "datatype": "INTEGER", "length": "10", "key": "PRIMARY", "keyadd": "autoincrement"},
                        {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE"},
                        {"column": "id", "datatype": "INTEGER", "length": "20", "key": "UNIQUE", "with": "name"},
                        {"column": "name", "datatype": "VARCHAR", "length": "40"}]
        Output - Creates Table.
        """
        driver=f'{CONSTANT["DATABASE"]["DRIVER"]}' # either MySQL, SQLite, or...
        columns = []
        indici  = []
        for cols in column:
            strcolumn = ''
            if 'column' in cols.keys():
                strcolumn = strcolumn + ' `' + cols['column'] + '` '
            if 'datatype' in cols.keys():
                strcolumn = strcolumn + ' ' +cols['datatype'].upper() + ' '
            if 'length' in cols.keys():
                if driver != "SQLite" and 'keyadd' in cols.keys() and cols['keyadd'].upper() == "AUTOINCREMENT":
                    #YES! sqlite does not allow e.g. INTEGER(10) to be an auto increment... _has_ to be INTEGER
                    strcolumn = strcolumn + ' (' +cols['length'] + ') '
            if 'key' in cols.keys() and 'column' in cols.keys():
                if cols['key'] == "PRIMARY":
                    if 'keyadd' in cols.keys():
                        if cols['keyadd'].upper() == "AUTOINCREMENT": # then it must a an INT or FLOAT
                            strcolumn = strcolumn + " NOT NULL "
                            if driver != "SQLite": # e.g. Mysql
                                strcolumn = strcolumn + "AUTO_INCREMENT "
                        if driver == "SQLite":
                            indici.append(f"PRIMARY KEY (`{cols['column']}` {cols['keyadd'].upper()})")
                        else:
                            indici.append(f"PRIMARY KEY (`{cols['column']}`)")
                    else:
                        indici.append(f"PRIMARY KEY (`{cols['column']}`)")
                else:
                    if 'with' not in cols:
                        indici.append(f"{cols['key'].upper()} (`{cols['column']}`)")
            if 'with' in cols.keys() and 'column' in cols.keys():
                indici.append(f"UNIQUE (`{cols['column']}`,`{cols['with']}`)")
            columns.append(strcolumn)
        strkeys = ', '.join(map(str, indici))
        columns.append(strkeys)
        strcolumns = ', '.join(map(str, columns))
        query = f'CREATE TABLE IF NOT EXISTS `{table}` ({strcolumns})'
        try:
            self.cursor.execute(query)
            self.connection.commit()
            response = True
        except pyodbc.Error as exp:
            self.logger.error(f'Error while creating table {table}. Error: {exp}')
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
            self.cursor.execute(query)
            self.cursor.commit()
            query = f'DELETE FROM sqlite_sequence WHERE name ="{table}";'
            self.cursor.execute(query)
            self.cursor.commit()
            response = True
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = False
        return response


    def insert(self, table=None, row=None):
        """
        Input - tablename and row
        Process - It is Create operation on the DB.
                    table is the table name which need to be created.
                    row is a list of dict ex: row =
        [{"column": "name", "value": "node004"}, {"column": "ip", "value": "10.141.0.1"}]
        Output - Creates Table.
        """
        keys, values, wherelist = [], [], []
        where = ' WHERE '
        response = False
        if row:
            for nrow in row:
                keys.append('"'+str(nrow["column"])+'"')
                values.append('"'+str(nrow["value"])+'"')
            wherekeys = keys
            wherevalues = values
            keys = ','.join(keys)
            values = ','.join(values)
        query = f'INSERT INTO "{table}" ({keys}) VALUES ({values});'
        try:
            self.cursor.execute(query)
            self.cursor.commit()
            for key,value in zip(wherekeys, wherevalues):
                wherelist.append(f'{key} = {value}')
            where = where + ' AND '.join(wherelist)
            result = self.get_record(None, table, where)
            if result:
                response = result[0]['id']
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
        return response


    def update(self, table=None, row=None, where=None):
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
        columns, wherelist = [], []
        for cols in row:
            column = ''
            if 'column' in cols.keys():
                column = column+ cols['column']
            if 'value' in cols.keys():
                column = column + ' = "' +str(cols['value']) +'"'
            columns.append(column)
            strcolumns = ', '.join(map(str, columns))
        for cols in where:
            column = ''
            if 'column' in cols.keys():
                column = column + cols['column']
            if 'value' in cols.keys():
                column = column + ' = "' +str(cols['value']) +'"'
            wherelist.append(column)
            strwhere = ' AND '.join(map(str, wherelist))
        query = f'UPDATE "{table}" SET {strcolumns} WHERE {strwhere};'
        try:
            self.cursor.execute(query)
            self.connection.commit()
            if self.cursor.rowcount < 1:
                response = False
            else:
                response = True
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = False
        return response


    def delete_row(self, table=None, where=None):
        """
        Input - tablename and where clause
        Process - It is SELECT operation on the DB.
                    table is the table name where the update operation should be happen.
                    where can be None for all OR a list of dict ex: where =
        [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
        Output - Delete the row.
        """
        wherelist = []
        for cols in where:
            column = ''
            if 'column' in cols.keys():
                column = column + cols['column']
            if 'value' in cols.keys():
                column = column + ' = "' +str(cols['value']) +'"'
            wherelist.append(column)
            strwhere = ' AND '.join(map(str, wherelist))
        try:
            query = f'DELETE FROM "{table}" WHERE {strwhere};'
            self.cursor.execute(query)
            self.cursor.commit()
            response = True
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = False
        return response


    def deletetable(self, connection, cursor, table):
        """
        Input - tablename
        Process - Delete The Table
        Output - Success/Failure.
        """
        try:
            query = f'DROP TABLE [IF EXISTS] {table}'
            cursor.execute(query)
            connection.commit()
            response = True
        except pyodbc.Error as exp:
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
            self.cursor.execute(query)
            # Fetching the Column Names
            response = list(map(lambda x: x[0], self.cursor.description))
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def getid_byname(self, table=None, name=None):
        """
        Input - tablename, name
        Output - id.
        """
        query = f'SELECT id FROM "{table}" WHERE `name` == "{name}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            self.cursor.execute(query)
            response = self.cursor.fetchone()
            self.logger.debug(f'Dataeet retrived => {response}.')
            if response:
                response = response[0]
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response


    def getname_byid(self, table=None, tableid=None):
        """
        Input - tablename, id
        Output - name.
        """
        query = f'SELECT name FROM "{table}" WHERE `id` == "{tableid}";'
        self.logger.debug(f'Query executing => {query}.')
        try:
            self.cursor.execute(query)
            response = self.cursor.fetchone()
            self.logger.debug(f'Dataset retrived => {response}.')
            if response:
                response = response[0]
        except pyodbc.Error as exp:
            self.logger.error(f'Error occur while executing => {query}. error is {exp}.')
            response = None
        return response
