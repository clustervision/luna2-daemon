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
        self.regexps={'name':'^[a-z0-9\-]+$','ipaddress':'^[0-9a-f:\.]+$','macaddress':'^[a-fA-F0-9:\-]+$'}
        self.mymatch={'name':'name','newnodename':'name','hostname':'name','newhostname':'name','newswitchname':'name','newotherdevicename':'name','newotherdevname':'name',
                     'ipaddress':'ipaddress','macaddress':'macaddress'}
        self.convert={'macaddress':{'-':':'}}
        self.error=None

    def validate_input(self,data,mytype=None):
        self.error=None
        self.logger.debug(f"---- START ---- {data}")
        if mytype:
            what=type(data)
            if what is not mytype:
                return "data type mismatch",False
        data=self.parse_item(data)
        self.logger.debug(f"----- END ----- {data}")
        if self.error:
            return self.error,False
        return data,True

    def parse_dict(self,data):
        for item in data.keys():
            data[item]=self.parse_item(data[item],item)
        return data
        
    def parse_list(self,data):
        for item in data:
            what=type(item)
            if what is list:
                item=self.parse_list(item)
            else:
                item=self.parse_item(item)
        return data

    def parse_item(self,data,name=None):
        what=type(data)
        if what is dict:
            data.update(self.parse_dict(data))
        elif what is list:
            data=(self.parse_list(data))
        elif what is str:
            data=self.filter(data,name)
        return data

    def filter(self,data,name=None):
        data=control_char_re.sub('', data)
        data=data.replace("'","")
        data=data.replace('"',"")
        if name in self.mymatch.keys():
            regex=re.compile(r""+self.regexps[self.mymatch[name]])
            if not regex.match(data):
                self.logger.debug(f"MATCH name = {name} with data = {data} mismatch with self.regexps['{self.mymatch[name]}'] = {self.regexps[self.mymatch[name]]}")
                self.error=f"field {name} with content {data} does match criteria {self.regexps[self.mymatch[name]]}"
        if name in self.convert.keys():
            self.logger.debug(f"CONVERT IN {name} = {data}")
            for rep in self.convert[name].keys():
                data=data.replace(rep,self.convert[name][rep])
            self.logger.debug(f"CONVERT OUT {name} = {data}")
        return data


