#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""
This Class deal all CRUD operations on Database SQLite, which is default for luna.

"""
from common.constants import *
from utils.log import *


class SQLite(object):


	"""
    Constructor - Initialize The Cursor to perform the operations.
    """
	def __init__(self, cursor):
		self.cursor = cursor
		self.logger = Log.get_logger()


	"""
    Input - select fields, tablename, where clause 
    Process - It is SELECT operation on the DB.
    			select can be comma separated column name or None.
				table is the table name where the select operation should be happen.
				where can be None for all OR a list of dict ex: where = [{"column": "name", "value": "cluster"}, {"column": "network", "value": "ib"}]
    Output - Fetch rows along with column name.
    """
	def get_record(self, select=None, table=None, where=None):
		if where:
		    Where = []
		    for cols in where:
		        column = ""
		        if 'column' in cols.keys():
		            column = column + cols['column']
		        if 'value' in cols.keys():
		            column = column + " = '" +cols['value']+"'"
		        Where.append(column)
		        strWhere = ' AND '.join(map(str, Where))
		if select:
		    strcolumn = ','.join(map(str, select))
		else:
		    strcolumn = "*"
		if where:
		    query = "SELECT {} FROM '{}' WHERE {}".format(strcolumn, table, strWhere)
		else:
		    query = "SELECT {} FROM '{}'".format(strcolumn, table)
		self.logger.debug("Query Executing => {} .".format(query))
		self.cursor.execute(query)
		names = list(map(lambda x: x[0], self.cursor.description)) # Fetching the Column Names
		data = self.cursor.fetchall()
		self.logger.debug("Data Set Retrived => {}.".format(str(data)))
		rowdict = {}
		response = []
		for row in data:
		    for key, value in zip(names,row):
		        rowdict[key] = value
		    response.append(rowdict)
		    rowdict = {}
		return response
	

	# def createtable(self, connection, cursor, table, tablecolumn):
 #        columns = []
 #        for cols in tablecolumn:
 #            column = ""
 #            if 'column' in cols.keys():
 #                column = column + ' [' + cols['column'] + '] '
 #            if 'datatype' in cols.keys():
 #                column = column + ' ' +cols['datatype'] + ' '
 #            if 'length' in cols.keys():
 #                column = column + ' (' +cols['length'] + ') '
 #            if 'key'in cols.keys():
 #                column = column + ' ' +cols['key'] + ' '
 #            columns.append(column)
 #            strcolumns = ', '.join(map(str, columns))
 #        query = "CREATE TABLE IF NOT EXISTS `{}` ({})".format(table, strcolumns)
 #        # print(query)
 #        # sys.exit(0)
 #        try:
 #            cursor.execute(query)     
 #            connection.commit()
 #        except Exception as e:
 #            print(e)
 #            sys.exit(0)
 #        # cursor.execute(query)     
 #        # connection.commit()


 #    def insertrow(self, table, data):
 #        keys = []
 #        values = []
 #        if data:
 #            for x in data:
 #                keys.append("'"+str(x)+"'")
 #                values.append("'"+str(data[x])+"'")
 #        query = "INSERT INTO '{}' ({}) VALUES ({})".format(table, ",".join(keys), ",".join(values))
 #        try:
 #            self.cursor.execute(query)     
 #            self.connection.commit()
 #        except Exception as e:
 #            print(e)
 #            sys.exit(0)
 #        return True

 #    def updaterow(self, table, update, where):
 #        columns = []
 #        Where = []
 #        for cols in update:
 #            column = ""
 #            if 'column' in cols.keys():
 #                column = column+ cols['column']
 #            if 'value' in cols.keys():
 #                column = column + ' = "' +cols['value'] +'"'
 #            columns.append(column)
 #            strcolumns = ', '.join(map(str, columns))
 #        for cols in where:
 #            column = ""
 #            if 'column' in cols.keys():
 #                column = column + cols['column']
 #            if 'value' in cols.keys():
 #                column = column + ' = "' +cols['value'] +'"'
 #            Where.append(column)
 #            strWhere = ' AND '.join(map(str, Where))
 #        query = "UPDATE '{}' SET {} WHERE {}".format(table, strcolumns, strWhere)
 #        try:
 #            self.cursor.execute(query)     
 #            self.connection.commit()
 #        except Exception as e:
 #            print(e)
 #            sys.exit(0)
 #        return True


 #    def deleterow(self, connection, cursor, table, where):
 #        Where = []
 #        for cols in where:
 #            column = ""
 #            if 'column' in cols.keys():
 #                column = column + cols['column']
 #            if 'value' in cols.keys():
 #                column = column + ' = ' +cols['value']
 #            Where.append(column)
 #            strWhere = ' AND '.join(map(str, Where))

 #        query = "DELETE FROM {} WHERE {}".format(table, strWhere)
 #        cursor.execute(query)     
 #        connection.commit()


	# def deletetable(self, connection, cursor, table):
 #        query = "DROP TABLE [IF EXISTS] {}".format(table)
 #        cursor.execute(query)     
 #        connection.commit()