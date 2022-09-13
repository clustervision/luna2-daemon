#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "1.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""

"""

import os
import sys
import json
# import sqlite3
# from sqlite3 import Error
import pandas as pd
import datetime
import subprocess

from termcolor import cprint, colored
from colorama import Fore, Back, Style
from prettytable.colortable import ColorTable, Themes
from rich import print_json

connection = None

# sqldb  = DB()
# connection = sqldb.initdb(database)
# cursor = sqldb.getcursor(connection)

class Helper(object):

    def __init__(self):
        self.connection = None
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(BASE_DIR, "luna.db")
        db = db_path
        # print(db)
        # sys.exit(0)
        # self.connection = sqlite3.connect(db)
        # self.cursor = self.connection.cursor()


    def runcommand(self, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output = process.communicate()
        process.wait()
        return output
        # output = process.stdout.readline().decode()
        # outputerror = process.stderr.readline().decode()
        # return output, outputerror

    def changepassword(self, username, password):
        process = subprocess.Popen(['/usr/bin/sudo', '/usr/bin/passwd', username, '--stdin'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        process.communicate(password)
        output = process.stdout.readline().decode()
        outputerror = process.stderr.readline().decode()
        return output, outputerror


    def printhorizontaltable(self, lists=None, table=None):
        ctable = ColorTable(theme=Themes.OCEAN)
        ctable.preserve_internal_border  = False
        ctable.padding_width = 5
        field = [colored("S.No.", 'cyan'), colored("Entity", 'cyan'), colored("Value", 'cyan')]
        ctable.field_names = field
        num = 1
        for xtable in table:
            for i in xtable:
                ctable.add_row([Fore.YELLOW +str(num), Fore.YELLOW +str(i), Fore.YELLOW +str(xtable[i])])
                num = num + 1
        return ctable

    def printlist(self, table=None):
        ctable = ColorTable(theme=Themes.OCEAN)
        ctable.preserve_internal_border  = False
        ctable.padding_width = 5
        field = [colored("S.No.", 'cyan'), colored("Services", 'cyan')]
        ctable.field_names = field
        num = 1
        for xtable in table:
            ctable.add_row([Fore.YELLOW +str(num), Fore.YELLOW +str(xtable)])
            num = num + 1
        return ctable


    def printjson(self, data):
        pretty = json.dumps(data, indent=4)
        print_json(pretty)
        return True
