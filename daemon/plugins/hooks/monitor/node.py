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
Plugin Class ::  Default node plugin. is being called during node create/update
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

#import os
#import pwd
#import sys
from utils.log import Log
import subprocess
#from utils.helper import Helper

logger = Log.get_logger()

class Plugin():
    """
    Class for running custom scripts during node create/update actions
    """

    def __init__(self):
        """
        none of the methods are really mandatory.
        the existence of the function will be tested prior to calling,
	however the following status are there by default:
        - install_prescript
        - install_partscript
        - install_postscript
        - install_secrets
        - install_roles
        - install_scripts
        - install_download
        - install_unpack
        - install_setupbmc
        - install_setnet
        - install_success

        BEWARE that __init__ is not being called for this plugin
        """

    # ---------------------------------------------------------------------------

    def install_discovered(self,name=None):
        return True, "success"

    def install_prescript(self,name=None):
        return True, "success"

    def install_partscript(self,name=None):
        return True, "success"

    def install_postscript(self,name=None):
        return True, "success"

    def install_secrets(self,name=None):
        return True, "success"

    def install_roles(self,name=None):
        return True, "success"

    def install_scripts(self,name=None):
        return True, "success"

    def install_download(self,name=None):
        return True, "success"

    def install_unpack(self,name=None):
        return True, "success"

    def install_setupbmc(self,name=None):
        return True, "success"

    def install_setnet(self,name=None):
        return True, "success"

    def install_success(self,name=None):
        return True, "success"
    

    # ---------------------------------------------------------------------------
