#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security class which provides functions and method to verify, check and secure input and other related things
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import json
import string
from utils.log import Log
#from jsonschema import validate
import unicodedata, re, itertools, sys

all_chars = (chr(i) for i in range(sys.maxunicode))
categories = {'Cc'}
#control_chars = ''.join(c for c in all_chars if unicodedata.category(c) in categories)
# or equivalently and much more efficiently
control_chars = ''.join(map(chr, itertools.chain(range(0x00,0x20), range(0x7f,0xa0))))
control_char_re = re.compile('[%s]' % re.escape(control_chars))

class Filter(object):

    def __init__(self):
        self.logger = Log.get_logger()
#        base64="[0-9A-Za-z\/\-\+\=]"

    def validate_input(self,data,required=None,filter=None):
        self.logger.debug(f"---- START ---- {data}")
        what=type(data)
#        self.logger.debug(f"VALIDATE_INPUT: what = [{what}] {data}")
        data=self.parse_item(data)
        self.logger.debug(f"----- END ----- {data}")
        return data

    def parse_dict(self,data):
        for item in data.keys():
            what=type(item)
#            self.logger.debug(f"PARSE_DICT: what = [{what}] {data}")
            if what is dict:
               item.update(self.parse_dict(item))
            elif what is list:
               item=self.parse_list(item)
            elif what is str: # or what is bool:
               data[item]=self.parse_item(data[item])
#        self.logger.debug(f"PARSE_DICT RETURN {data}")
        return data
        
    def parse_list(self,data):
        for item in data:
            what=type(item)
#            self.logger.debug(f"PARSE_LIST: what = [{what}] {data}")
            if what is dict:
               item.update(self.parse_dict(item))
            elif what is list:
               item=self.parse_list(item)
            elif what is str: # or what is bool:
               data[item]=self.parse_item(data[item])
#        self.logger.debug(f"PARSE_LIST RETURN {data}")
        return data

    def parse_item(self,data):
#        self.logger.debug(f"PARSE_ITEM inside what is str: [{data}]")
        what=type(data)
        if what is dict:
            data.update(self.parse_dict(data))
        elif what is list:
            data=(self.parse_list(data))
        else:
            data=self.filter(data)
        return data

    def filter(self,data):
#        filter(lambda x: x in string.printable, '\x01string')
#        data=filter(lambda x: x in string.printable, data)
        data=self.printable(data)
        data=data.replace("'","")
        data=data.replace('"',"")
#        self.logger.debug(f"FILTER: [{data}]")
        return data

    def printable(self,line):
        #return line+'blaat'
        return control_char_re.sub('', line)


