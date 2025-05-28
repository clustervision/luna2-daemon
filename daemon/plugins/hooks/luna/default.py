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

from utils.log import Log
#from utils.helper import Helper

try:
    from trinityx_config_slurm import Generate as Slurm
    from trinityx_config_genders import Generate
    use_new_config_method = True
except Exception as exp:
    use_new_config_method = False

class Plugin():
    """
    Class for running custom scripts during node create/update actions
    """
    SCRIPTS_PATH = "/trinity/local/sbin"

    def __init__(self):
        """
        two defined methods are mandatory:
        - startup
        - shutdown
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def startup(self, fullset=[]):
        """
        This method will be called when luna starts up
        fullset contains node/group key/value pairs in a list
        """
        returns = []
        if use_new_config_method:
            returns.append(Slurm().all_configs(fullset))
            returns.append(Generate().Genders(fullset))
            if (min(returns)):
                return True, "Config files written"
            else:
                return False, "Error writing config files"
        return True, "no config change needed"

    # ---------------------------------------------------------------------------

    def shutdown(self, fullset=[]):
        """
        This method will be called when luna shutsdown
        """
        return True, "no config change needed"
    
    # ---------------------------------------------------------------------------
