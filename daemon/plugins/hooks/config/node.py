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
        five defined methods are mandatory:
        - postcreate
        - postupdate
        - rename
        - delete
        - bulk
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def postcreate(self, name=None, group=None):
        processes = []
        return_code = 0
        if not group:
            return False, "No group given"
        if not use_new_config_method:
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "node", "create", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "node", "create", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "node", "create", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}: {process.stderr.decode()}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None, group=None):
        processes = []
        return_code = 0
        if not group:
            return False, "No group given"
        if not use_new_config_method:
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "node", "update", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "node", "update", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "node", "update", name, group], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}: {process.stderr.decode()}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"

    # ---------------------------------------------------------------------------

    def rename(self, name=None, newname=None):
        processes = []
        return_code = 0
        processes.append(subprocess.run(["/usr/bin/rename ." + name + ". ." + newname + ". /trinity/local/etc/prometheus_server/rules/*"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True))
        if not use_new_config_method:
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "node", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "node", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "node", "rename", name, newname], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}: {process.stderr.decode()}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"

    # ---------------------------------------------------------------------------

    def delete(self, name=None):
        processes = []
        return_code = 0
        processes.append(subprocess.run(["/bin/rm -f /trinity/local/etc/prometheus_server/rules/trix.hw." + name + ".*"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True))
        if not use_new_config_method:
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "pdsh-genders", "node", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-nodes", "node", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            processes.append(subprocess.run([self.SCRIPTS_PATH + "/trix-config-manager", "slurm-partitions", "node", "delete", name], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

        for process in processes:
            process_return_code = process.returncode
            if process_return_code == 0:
                self.logger.info(f"Script {process.args} executed successfully")
            else:
                self.logger.error(f"Script {process.args} failed with return code {process_return_code}: {process.stderr.decode()}")
                return_code = max(return_code, process_return_code)
        if return_code == 0:
            return True, "Config files written"
        else:
            return False, "Error writing config files"

    # ---------------------------------------------------------------------------

    def bulk(self, fullset=[]):
        """
        Bulk takes care of bulky operations, e.g. when writing a config file for all nodes in one go.
        This function is called through queue and will typically be called only after a massive
        node operation like cloning a big number of nodes.
        """
        if use_new_config_method:
            returns = []
            returns.append(Slurm().all_configs(fullset))
            returns.append(Generate().Genders(fullset))
            if (min(returns)):
                return True, "Config files written"
            else:
                return False, "Error writing config files"
        else:
            return True, "No config change required"

    # ---------------------------------------------------------------------------
