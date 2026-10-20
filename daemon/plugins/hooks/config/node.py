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
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
import subprocess

# Two try blocks: a shared one would lose genders where config-slurm is absent.
try:
    from trinityx_config_slurm import Generate as Slurm
except Exception:
    Slurm = None

try:
    from trinityx_config_genders import Generate
except Exception:
    Generate = None

# The trix-daemon beside this controller, where there is one; absent is normal.
try:
    from plugins.addons.trixd import notify as trixd_notify
except Exception:
    trixd_notify = None

class Plugin():
    """
    Class for running custom scripts during node create/update actions
    """

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

    def tell_trixd(self, event=None, payload=None):
        """
        Hand a change to the trix-daemon, which decides for itself what to do with it.
        """
        if trixd_notify is None:
            return False
        return trixd_notify(event, payload)

    # ---------------------------------------------------------------------------

    def postcreate(self, name=None, group=None):
        told = self.tell_trixd('luna.node.update', {'name': name, 'group': group or ''})
        if not group:
            return False, "No group given"
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None, group=None):
        told = self.tell_trixd('luna.node.update', {'name': name, 'group': group or ''})
        if not group:
            return False, "No group given"
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------

    def rename(self, name=None, newname=None):
        processes = []
        return_code = 0
        # The old and the new name together, which nothing can recover afterwards.
        told = self.tell_trixd('luna.node.update', {'name': name, 'newnodename': newname})
        if told:
            # Where trixd is told it owns the hardware rule files and carries them itself.
            return True, "trixd notified"
        processes.append(subprocess.run(["/usr/bin/rename ." + name + ". ." + newname + ". /trinity/local/etc/prometheus_server/rules/*"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True))

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
        told = self.tell_trixd('luna.node.delete', {'name': name})
        if told:
            # Where trixd is told it retires the hardware rule files itself.
            return True, "trixd notified"
        processes.append(subprocess.run(["/bin/rm -f /trinity/local/etc/prometheus_server/rules/trix.hw." + name + ".*"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True))

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
        # One call for the whole set, never one per node: trixd makes a task per change.
        told = self.tell_trixd('luna.node.bulk', {'fullset': fullset})
        if told:
            return True, "trixd notified"
        if Slurm is None and Generate is None:
            self.logger.error("No configuration generator is installed here: neither "
                              "trinityx-config-slurm nor trinityx-config-genders could be "
                              "imported, so this controller writes neither file")
            return False, "No configuration generator installed"

        returns = []
        if Slurm:
            returns.append(Slurm().all_configs(fullset))
        if Generate:
            returns.append(Generate().Genders(fullset))
        if not min(returns):
            self.logger.error("Error writing config files")
            return False, "Error writing config files"
        # Without Slurm there is no controller to reconfigure, and asking logs an error.
        if Slurm:
            reconf = subprocess.run(["/usr/bin/scontrol", "reconfigure"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if reconf.returncode != 0:
                self.logger.error(f"Could not reconfigure slurm: {reconf.stderr.decode()}")
                return False, f"Could not reconfigure slurm: {reconf.stderr.decode()}"
        self.logger.info("Config files written")
        return True, "Config files written"

    # ---------------------------------------------------------------------------
