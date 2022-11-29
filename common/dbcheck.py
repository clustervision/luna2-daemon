#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is responsible to Check The Status for Database.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'



import os
from utils.database import *
logger = Log.get_logger()
"""
Input - None
Process - Check the Current Database condition.
Output - Status of Read & Write.
"""
def checkdbstatus():
    sqlite, read, write = False, False, False
    code = 503
    if os.path.isfile(CONSTANT['DATABASE']['DATABASE']):
        sqlite = True
        if os.access(CONSTANT['DATABASE']['DATABASE'], os.R_OK):
            read = True
            code = 500
            try:
                file = open(CONSTANT['DATABASE']['DATABASE'], "a")
                if file.writable():
                    write = True
                    code = 200
                    file.close()
            except Exception as e:
                logger.error("DATABASE {} is Not Writable.".format(CONSTANT['DATABASE']['DATABASE']))

            with open(CONSTANT['DATABASE']['DATABASE'],'r', encoding = "ISO-8859-1") as f:
                header = f.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                else:
                    read, write = False, False
                    code = 503
                    logger.error("DATABASE {} is Not a SQLite3 Database.".format(CONSTANT['DATABASE']['DATABASE']))
        else:
            logger.error("DATABASE {} is Not Readable.".format(CONSTANT['DATABASE']['DATABASE']))
    else:
        logger.info("DATABASE {} is Not a SQLite Database.".format(CONSTANT['DATABASE']['DATABASE']))
    if not sqlite:
        try:
            Database().get_cursor()
            read, write = True, True
            code = 200
        except pyodbc.Error as error:
            logger.error("Error While connecting to Database {} is: {}.".format(CONSTANT['DATABASE']['DATABASE'], str(error)))
    response = {"database": CONSTANT['DATABASE']['DRIVER'], "read": read, "write": write}
    return response, code


if __name__ == "__main__":
    response, code = checkdbstatus()

