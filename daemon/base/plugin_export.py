#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#This code is part of the TrinityX software suite
#Copyright (C) 2023  ClusterVision Solutions b.v.
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>


"""
Journal class. handles internal journal calls
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from common.constant import CONSTANT
from utils.helper import Helper
from utils.log import Log


class Export():
    """
    This class is responsible for export plugin handling.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.export_plugins = Helper().plugin_finder(f'{plugins_path}/export')

    def plugin(self,name,args=None):
        allowed_exporters = None
        if 'ALLOWED_EXPORTERS' in CONSTANT["PLUGINS"]:
            allowed_exporters = CONSTANT["PLUGINS"]["ALLOWED_EXPORTERS"].replace(' ','').split(',')
        if allowed_exporters: 
            if name in allowed_exporters:
                export_plugin=Helper().plugin_load(self.export_plugins,'export',name)
                if export_plugin:
                    if args:
                        status, response = export_plugin().Export(args)
                    else:
                        status, response = export_plugin().Export()
                    return status, response
                return False, f"plugin {name} could not be loaded"
        return False, f"allowed_exporters is undefined or using plugin {name} not permitted"

