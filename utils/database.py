#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""
This Class Identify the specified Database Connection from Configuration and return the Cursor of correct Database.
Database have the default methods for CRUD. In case of changing database model dosn't impact the application.

"""

import pyodbc
from utils.log import *

class Database(object):


	"""
    Constructor - Initialize The Coorect Database from the conf file.
    """
	def __init__(self):
		self.logger = Log.get_logger()
		self.connection = pyodbc.connect("DRIVER={};SERVER={};DATABASE={};UID={};PWD={};charset=utf8mb4;PORT={};".format(DRIVER, HOST, DATABASE, DBUSER, DBPASSWORD, PORT))
		self.cursor = self.connection.cursor()


	"""
    Input - None 
    Output - Return Cursor Od Database.
    """
	def get_cursor(self):
		return self.cursor


	"""
    Input - None
    Process - Check If Database is Active, Readable and Writable.
    Output - Result/None.
    """
	def check_db(self):
		try:
			self.cursor.execute("SELECT * FROM user")
			result = self.cursor.fetchone()
		except Exception as e:
			result = None
		return result


	"""
    Input - select fields, tablename, where clause 
    Process - It is SELECT operation on the DB.
    			select can be comma separated column name or None.
				table is the table name where the select operation should be happen.
				where can be None OR complete where condition
    Output - Fetch rows along with column name.
    """
	def get_record(self, select=None, table=None, where=None):
		if select:
		    strcolumn = ','.join(map(str, select))
		else:
		    strcolumn = "*"
		if where:
		    query = "SELECT {} FROM '{}' {}".format(strcolumn, table, where)
		else:
		    query = "SELECT {} FROM '{}'".format(strcolumn, table)
		self.logger.debug("Query Executing => {} .".format(query))
		try:
			self.cursor.execute(query)
		except Exception as e:
			self.logger.error("Error occur While Executing => {}. Error Is {} .".format(query, str(e)))
			return None
		
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


	"""
    Input - tablename and column
    Process - It is Create operation on the DB.
				table is the table name which need to be created.
				column is a list of dict ex: 
				where = [{"column": "id", "datatype": "INTEGER", "length": "10", "key": "PRIMARY Key"}, {"column": "name", "datatype": "VARCHAR", "length": "40"}]
    Output - Creates Table.
    """
	def create(self, table=None, column=None):
		columns = []
		for cols in tablecolumn:
		    column = ""
		    if 'column' in cols.keys():
		        column = column + ' [' + cols['column'] + '] '
		    if 'datatype' in cols.keys():
		        column = column + ' ' +cols['datatype'] + ' '
		    if 'length' in cols.keys():
		        column = column + ' (' +cols['length'] + ') '
		    if 'key'in cols.keys():
		        column = column + ' ' +cols['key'] + ' '
		    columns.append(column)
		    strcolumns = ', '.join(map(str, columns))
		query = "CREATE TABLE IF NOT EXISTS `{}` ({})".format(table, strcolumns)
		# print(query)
		# sys.exit(0)
		try:
		    cursor.execute(query)     
		    connection.commit()
		except Exception as e:
		    print(e)
		    sys.exit(0)
		# cursor.execute(query)     
		# connection.commit()


	"""
    Input - tablename
    Process - Truncate the table.
    Output - Success or Failure.
    """
	def truncate(self, table=None):
		if self.name == "sqlite":
			self.logger.debug("Truncate Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite()
		return result


	"""
    Input - tablename and row
    Process - It is Create operation on the DB.
				table is the table name which need to be created.
				row is a list of dict ex: row = [{"column": "name", "value": "node004"}, {"column": "ip", "value": "10.141.0.1"}]
    Output - Creates Table.
    """
	def insert(self, table=None, row=None):
		keys = []
		values = []
		if data:
		   for x in data:
		       keys.append("'"+str(x)+"'")
		       values.append("'"+str(data[x])+"'")
		query = "INSERT INTO '{}' ({}) VALUES ({})".format(table, ",".join(keys), ",".join(values))
		try:
		   self.cursor.execute(query)     
		   self.connection.commit()
		except Exception as e:
		   print(e)
		   sys.exit(0)
		return True


	"""
    Input - tablename, row, and where clause 
    Process - It is SELECT operation on the DB.
				table is the table name where the update operation should be happen.
				row can be None for all OR a list of dict ex: where = [{"column": "name", "value": "cluster"}, {"column": "network", "value": "ib"}]
				where can be None for all OR a list of dict ex: where = [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
    Output - Update the rows.
    """
	def update(self, table=None, row=None, where=None):
		columns = []
		Where = []
		for cols in update:
		    column = ""
		    if 'column' in cols.keys():
		        column = column+ cols['column']
		    if 'value' in cols.keys():
		        column = column + ' = "' +cols['value'] +'"'
		    columns.append(column)
		    strcolumns = ', '.join(map(str, columns))
		for cols in where:
		    column = ""
		    if 'column' in cols.keys():
		        column = column + cols['column']
		    if 'value' in cols.keys():
		        column = column + ' = "' +cols['value'] +'"'
		    Where.append(column)
		    strWhere = ' AND '.join(map(str, Where))
		query = "UPDATE '{}' SET {} WHERE {}".format(table, strcolumns, strWhere)
		try:
		    self.cursor.execute(query)     
		    self.connection.commit()
		except Exception as e:
		    print(e)
		    sys.exit(0)
		return True


	"""
    Input - tablename and where clause 
    Process - It is SELECT operation on the DB.
				table is the table name where the update operation should be happen.
				where can be None for all OR a list of dict ex: where = [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
    Output - Delete the row.
    """
	def delete_row(self, table=None, row=None, where=None):
		Where = []
		for cols in where:
		    column = ""
		    if 'column' in cols.keys():
		        column = column + cols['column']
		    if 'value' in cols.keys():
		        column = column + ' = ' +cols['value']
		    Where.append(column)
		    strWhere = ' AND '.join(map(str, Where))

		query = "DELETE FROM {} WHERE {}".format(table, strWhere)
		cursor.execute(query)     
		connection.commit()


	def deletetable(self, connection, cursor, table):
		query = "DROP TABLE [IF EXISTS] {}".format(table)
		cursor.execute(query)     
		connection.commit()