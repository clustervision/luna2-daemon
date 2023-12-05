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
Plugin Class ::  Default group plugin. is being called during group create/update
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

#import os
#import pwd
#import sys
import subprocess
from utils.log import Log
#from utils.helper import Helper


class Plugin():
    """
    Class for running custom scripts during group create/update actions
    """
    SCRIPTS_PATH = "/trinity/local/sbin"

    def __init__(self):
        """
        two defined methods are mandatory:
        - postcreate
        - postupdate
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def postcreate(self, name=None, nodes=[]):
        processes = []
        return_code = 0
        if not nodes: return
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "group", "create", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "group", "create", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "create", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None, nodes=[]):
        processes = []
        return_code = 0
        if not nodes: return
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "group", "update", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "group", "update", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "group", "update", name, ','.join(nodes)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"


    # ---------------------------------------------------------------------------

    def rename(self, name=None, newname=None):
        processes = []
        return_code = 0
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "group", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "group", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "group", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"


    # ---------------------------------------------------------------------------

    def delete(self, name=None):
        processes = []
        return_code = 0
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "group", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "group", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "group", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"


    # ---------------------------------------------------------------------------
