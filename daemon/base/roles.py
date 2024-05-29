#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#This code is part of the TrinityX software suite
#Copyright (C) 2024  ClusterVision Solutions b.v.
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
Roles class. handles role related activities.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2024, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import re
from base64 import b64decode, b64encode
from common.constant import CONSTANT
from utils.database import Database
from utils.helper import Helper
from utils.log import Log


class Roles():
    """
    This class is responsible to provide all role(s) data.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.roles_plugins = Helper().plugin_finder(f'{plugins_path}/boot/roles')

    def get_role(self, name=None):
        """
        load the role plugin based on the name, extract the data and prepare to return
        """
        status = False
        if not name:
            return status, "Role not supplied"
        try:
            status = True
            self.logger.info(f"Loading role plugin {name}")
            role_plugin = Helper().plugin_load(self.roles_plugins, f'boot/roles', name)
            target = str(role_plugin().target)
            script = str(role_plugin().script)
            self.logger.debug(f"data for role {name}: {target}, {script}")

            regex=re.compile(r"^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$")
            try:
                if not regex.match(script):
                    data = b64encode(script.encode())
                    script = data.decode("ascii")
            except Exception as exp:
                self.logger.error(f"{exp}. Maybe it's already base64?")

            response = {'role': {name: {'target': target, 'script': script} } }
            return status, response

        except Exception as exp:
            self.logger.error(f"while working on role {name}: {exp}")

        return status, f"Role {name} could not be loaded"

