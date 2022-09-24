#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""
This Class Identify the specified Database Connection from Configuration and return the Instance of correct Database.
Database have the default methods for CRUD. In case of changing database model dosn't impact the application.

"""

from common.constants import *
import sqlite3
from sqlite3 import Error
import mysql.connector
import psycopg2
from utils.database.sqlite import sqlite as SQLite
from utils.database.mysql import *
from utils.database.postgresql import *
from utils.log import *

class Database(object):


	"""
    Constructor - Initialize The Coorect Database from the conf file.
    """
	def __init__(self):
		self.logger = Log.get_logger()
		if DEFAULTDB == "SQLDB":
			self.DB = self.sqlite()
			self.logger.debug("Select Database To Perform Actions Is => {}.".format(SQLDB))
		elif DEFAULTDB == "MYSQLDB":
			self.DB = self.mysql()
			self.logger.debug("Select Database To Perform Actions Is => {}.".format(MYSQLDB))
		elif DEFAULTDB == "PGSQLDB":
			self.DB = self.postgresql()
			self.logger.debug("Select Database To Perform Actions Is => {}.".format(PGSQLDB))
		else:
			self.name = ""
			self.logger.error("DB NOT Configured.")


	"""
	Input - None
	Process - Connec the SQLite Database as per conf file.
	Output - Cursor.
	"""
	def sqlite(self):
		self.connection = sqlite3.connect(SQLDB)
		self.cursor = self.connection.cursor()
		self.name = "sqlite"
		self.logger.debug("Database {} cursor returned.".format(SQLDB))
		return self.cursor


	"""
	Input - None
	Process - Connec the MySQL Database as per conf file.
	Output - Cursor.
	"""
	def mysql(self):
		self.connection = mysql.connector.connect(user=MYSQLUSERNAME, password=MYSQLPASSWORD, host=MYSQLHOST, port=MYSQLPORT, database=MYSQLDB)
		self.cursor = self.connection.cursor()
		self.name = "mysql"
		self.logger.debug("Database {} cursor returned.".format(MYSQLDB))
		return self.cursor


	"""
	Input - None
	Process - Connec the PostgreSQL Database as per conf file.
	Output - Cursor.
	"""
	def postgresql(self):
		self.connection = psycopg2.connect(user=PGSQLUSERNAME, password=PGSQLPASSWORD, host=PGSQLHOST, database=PGSQLDB)
		self.cursor = self.connection.cursor()
		self.name = "postgresql"
		self.logger.debug("Database {} cursor returned.".format(PGSQLDB))
		return self.cursor


	"""
    Input - select fields, tablename, where clause 
    Process - It is SELECT operation on the DB.
    			select can be comma separated column name or None.
				table is the table name where the select operation should be happen.
				where can be None for all OR a list of dict ex: where = [{"column": "name", "value": "cluster"}, {"column": "network", "value": "ib"}]
    Output - Fetch rows along with column name.
    """
	def get_record(self, select=None, table=None, where=None):
		if self.name == "sqlite":
			self.logger.debug("Select Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite(self.cursor).get_record(select, table, where)
		return result


	"""
    Input - tablename and column
    Process - It is Create operation on the DB.
				table is the table name which need to be created.
				column is a list of dict ex: 
				where = [{"column": "id", "datatype": "INTEGER", "length": "10", "key": "PRIMARY Key"}, {"column": "name", "datatype": "VARCHAR", "length": "40"}]
    Output - Creates Table.
    """
	def create(self, table=None, column=None):
		if self.name == "sqlite":
			self.logger.debug("Create Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite()
		return result


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
		if self.name == "sqlite":
			self.logger.debug("Insert Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite()
		return result


	"""
    Input - tablename, row, and where clause 
    Process - It is SELECT operation on the DB.
				table is the table name where the update operation should be happen.
				row can be None for all OR a list of dict ex: where = [{"column": "name", "value": "cluster"}, {"column": "network", "value": "ib"}]
				where can be None for all OR a list of dict ex: where = [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
    Output - Update the rows.
    """
	def update(self, table=None, row=None, where=None):
		if self.name == "sqlite":
			self.logger.debug("Update Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite()
		return result


	"""
    Input - tablename and where clause 
    Process - It is SELECT operation on the DB.
				table is the table name where the update operation should be happen.
				where can be None for all OR a list of dict ex: where = [{"column": "active", "value": "1"}, {"column": "network", "value": "ib"}]
    Output - Delete the row.
    """
	def delete_row(self, table=None, row=None, where=None):
		if self.name == "sqlite":
			self.logger.debug("Delete Row Operation Performed on {}.".format(SQLDB))
			result = SQLite.SQLite()
		return result