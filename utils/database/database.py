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
ORM Taking Extra time, need to research for best ORM.

"""

from common.constants import *
import sqlite3
from sqlite3 import Error
from utils.database.sqlite import sqlite as SQLite
from utils.database.mysql import *
from utils.database.postgresql import *


class Database(object):

	def __init__(self):
		if SQLDB:
			self.DB = self.sqlite()
		elif MYSQLBD:
			
			self.DB = self.mysql()
		elif POSTGREDB:
			self.DB = self.postgresql()
		else:
			self.name = ""
			print("DB not Configured.")
			

	def sqlite(self):
		self.connection = sqlite3.connect(SQLDB)
		self.cursor = self.connection.cursor()
		self.name = "sqlite"
		return self.cursor


	def mysql(self):
		self.name = "mysql"


	def postgresql(self):
		self.name = "postgresql"


	def get_record(self, select=None, table=None, where=None):
		if self.name == "sqlite":
			result = SQLite.SQLite(self.cursor).get_record(select, table, where)
		return result

	def create(self):
		if self.name == "sqlite":
			result = SQLite.SQLite()
		return result

	def truncate(self):
		if self.name == "sqlite":
			result = SQLite.SQLite()
		return result

	def insert(self):
		if self.name == "sqlite":
			result = SQLite.SQLite()
		return result

	def update(self):
		if self.name == "sqlite":
			result = SQLite.SQLite()
		return result

	def delete(self):
		if self.name == "sqlite":
			result = SQLite.SQLite()
		return result