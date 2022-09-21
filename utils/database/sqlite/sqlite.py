#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""
This is SQLite Class. It will perform all operations with SQLite Database.
This is the Default Database for Luna 2.

"""
from common.constants import *


class SQLite(object):

	def __init__(self, cursor):
		self.cursor = cursor


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
		self.cursor.execute(query)
		names = list(map(lambda x: x[0], self.cursor.description))
		data = self.cursor.fetchall()
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