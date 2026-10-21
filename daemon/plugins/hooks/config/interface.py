#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
Plugin Class ::  Default interface plugin. is being called during node interface
create/update
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log

# The trix-daemon beside this controller, where there is one; absent is normal.
try:
    from plugins.addons.trixd import notify as trixd_notify
except Exception:
    trixd_notify = None

class Plugin():
    """
    Class for running custom scripts during node interface create/update actions
    """

    def __init__(self):
        """
        five defined methods are mandatory:
        - postcreate
        - postupdate
        - macaddressupdate
        - rename
        - delete
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

    def postcreate(self, name=None, interface=None, macaddress=None, ipaddress=None,
                   ipaddress_ipv6=None, network=None, networktype=None, zone=None):
        # An interface has no identity downstream, so the node is what is announced.
        # Nothing without a value: a blank reads as an address that was looked for and
        # found gone, and a new interface may have neither address nor network yet.
        told = self.tell_trixd('luna.node.update', {key: value for key, value in {
            'name': name, 'interface': interface, 'macaddress': macaddress,
            'ipaddress': ipaddress, 'ipaddress_ipv6': ipaddress_ipv6,
            'network': network, 'networktype': networktype, 'zone': zone
        }.items() if value is not None})
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None, interface=None, macaddress=None, ipaddress=None,
                   ipaddress_ipv6=None, network=None, networktype=None, zone=None):
        told = self.tell_trixd('luna.node.update', {key: value for key, value in {
            'name': name, 'interface': interface, 'macaddress': macaddress,
            'ipaddress': ipaddress, 'ipaddress_ipv6': ipaddress_ipv6,
            'network': network, 'networktype': networktype, 'zone': zone
        }.items() if value is not None})
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------

    def macaddressupdate(self, name=None, interface=None, macaddress=None):
        # A stub on purpose: nothing downstream reads a macaddress, and announcing one
        # would wake every render to repair a value none of them look at.
        return True, "nothing consumes a macaddress change here"

    # ---------------------------------------------------------------------------

    def rename(self, name=None, interface=None, newinterfacename=None):
        # The old and the new name together, which nothing can recover afterwards.
        told = self.tell_trixd('luna.node.update', {'name': name, 'interface': interface,
                                                    'newinterfacename': newinterfacename})
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------

    def delete(self, name=None, interface=None):
        # Never luna.node.delete: one interface went and the node did not, and a node
        # delete retires the hardware rule files of a node that is still there.
        told = self.tell_trixd('luna.node.update', {'name': name, 'interface': interface})
        return True, "trixd notified" if told else "trixd not notified"

    # ---------------------------------------------------------------------------
