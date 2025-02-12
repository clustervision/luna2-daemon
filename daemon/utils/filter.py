#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Security class which provides functions and method to verify,
check and secure input and other related things
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import re
import itertools
import sys
# from jsonschema import validate
# import unicodedata
from utils.log import Log

all_chars = (chr(i) for i in range(sys.maxunicode))
categories = {'Cc'}
# control_chars = ''.join(c for c in all_chars if unicodedata.category(c) in categories)
# or equivalently and much more efficiently
control_chars = ''.join(map(chr, itertools.chain(range(0x00,0x20), range(0x7f,0xa0))))
control_char_re = re.compile('[%s]' % re.escape(control_chars))

class Filter(object):

    def __init__(self):
        self.logger = Log.get_logger()
        self.regexps={'name':'^[a-z0-9\-]+$','ipaddress':'^[0-9a-f:\.]+$','macaddress':'^[a-fA-F0-9:\-]+$'}
        self.mymatch={'name':'name','newnodename':'name','hostname':'name','newhostname':'name','newswitchname':'name','newotherdevicename':'name','newotherdevname':'name',
                     'ipaddress':'ipaddress','macaddress':'macaddress'}
        self.maxlength={'request_id':'256'}
        self.convert={'macaddress':{'-':':'}}
        self.error=None
        self.skip=[]

    def validate_input(self,data,checks=None,skip=None):
        self.error=None
        if skip:
            if type(skip) == type('string'):
                self.skip.append(str(skip))
            else:
                self.skip=skip

        self.logger.debug(f"---- START ---- {data}")
        if self.check_structure(data,checks):
            data=self.parse_item(data)
            self.logger.debug(f"----- END ----- {data}")
            if self.error:
                return self.error,False
            return data,True
        return "data structure incomplete or incorrect",False

    def parse_dict(self,data):
        for item in data.keys():
            data[item]=self.parse_item(data[item],item)
        return data

    def parse_list(self,data):
        ndata=[]
        for item in data:
            what=type(item)
            if what is list:
                item=self.parse_list(item)
            else:
                item=self.parse_item(item)
            ndata.append(item)
        return ndata

    def parse_item(self,data,name=None):
        what=type(data)
        if what is dict:
            data.update(self.parse_dict(data))
        elif what is list:
            data=self.parse_list(data)
        elif what is str:
            data=self.filter(data,name)
        return data

    def filter(self,data,name=None):
        if name in self.skip:
            self.logger.debug(f"Skipping filter on {name}")
            return data
        data=control_char_re.sub('', data)
        data=data.replace("'","")
        data=data.replace('"',"")
        if name in self.maxlength.keys():
            if len(data) > int(self.maxlength[name]):
                self.logger.debug(f"length of {name} exceeds {self.maxlength[name]}")
                self.error=f"length of {name} exceeds {self.maxlength[name]}"
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

    def check_structure(self,data,checks=None):
        if not checks:
            return True
        mychecks=[]
        if type(checks) == type('string'):
            mychecks.append(str(checks))
        else:
            mychecks=checks

        try:
            for check in mychecks:
                arr=check.split(':')
                sliced_data=data
                for element in arr:
                    if not element in sliced_data:
                        self.logger.debug(f"{element} not found in data {sliced_data}")
                        return False
                    self.logger.debug(f"OK: {element} found in data {sliced_data}")
                    sliced_data=sliced_data[element]
            return True
        except Exception as exp:
            self.logger.debug(f"filter encountered issue due to incorrect data/json/dict?: {exp}")
            return False
