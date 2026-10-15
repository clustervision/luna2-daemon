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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log

# The trix-daemon beside this controller, where there is one. A controller without it
# carries on exactly as before.
try:
    from plugins.addons.trixd import notify as trixd_notify
except Exception:
    trixd_notify = None

class Plugin():
    """
    Class for running custom scripts during group create/update actions
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
        Returns whether it was told; never raises, and never holds up the write.
        """
        if trixd_notify is None:
            return False
        return trixd_notify(event, payload)

    # ---------------------------------------------------------------------------

    def postcreate(self, name=None, nodes=[]):
        told = self.tell_trixd('luna.group.update', {'name': name, 'nodes': nodes or []})
        if not nodes:
            return True, "No nodes in this group"
        return True, "trixd notified" if told else "Nothing to notify"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None, nodes=[]):
        told = self.tell_trixd('luna.group.update', {'name': name, 'nodes': nodes or []})
        if not nodes:
            return True, "No nodes in this group"
        return True, "trixd notified" if told else "Nothing to notify"


    # ---------------------------------------------------------------------------

    def rename(self, name=None, newname=None):
        # The old and the new name together, which nothing can recover afterwards.
        told = self.tell_trixd('luna.group.update',
                               {'name': name, 'newgroupname': newname})
        return True, "trixd notified" if told else "Nothing to notify"


    # ---------------------------------------------------------------------------

    def delete(self, name=None):
        told = self.tell_trixd('luna.group.delete', {'name': name})
        return True, "trixd notified" if told else "Nothing to notify"


    # ---------------------------------------------------------------------------

    def bulk(self, fullset=[]):
        """
        Bulk takes care of bulky operations, e.g. when writing a config file for all nodes in one go.
        This function is called through queue and will typically be called only after a massive
        node operation like cloning a big number of groups.
        """
        return True, "No config change required"

    # ---------------------------------------------------------------------------
