#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is responsible to Check The Status for Database.

"""

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
    if os.path.isfile(DATABASE):
        sqlite = True
        if os.access(DATABASE, os.R_OK): 
            read = True
            code = 500
            try:
                file = open(DATABASE, "a")
                if file.writable():
                    write = True
                    code = 200
                    file.close()
            except Exception as e:
                logger.error("DATABASE {} is Not Writable.".format(DATABASE))
            
            with open(DATABASE,'r', encoding = "ISO-8859-1") as f:
                header = f.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                else:
                    read, write = False, False
                    code = 503
                    logger.error("DATABASE {} is Not a SQLite3 Database.".format(DATABASE))
        else:
            logger.error("DATABASE {} is Not Readable.".format(DATABASE))
    else:
        logger.info("DATABASE {} is Not a SQLite Database.".format(DATABASE))
    if not sqlite:
        try:
            Database().get_cursor()
            read, write = True, True
            code = 200
        except pyodbc.Error as error:
            logger.error("Error While connecting to Database {} is: {}.".format(DATABASE, str(error)))
    response = {"database": DRIVER, "read": read, "write": write}
    return response, code


if __name__ == "__main__":
    response, code = checkdbstatus()