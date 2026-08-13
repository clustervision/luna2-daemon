#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
Default profile delivery: rsync the bundle to the node and run its applier over ssh.

Uses the trust that already exists for pushing an osimage to a running node, so it needs
no listener on the node, no port and no credential of its own.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.helper import Helper

STAGING = '/var/lib/luna/profiles/staging'
# The transport bounds itself. Helper().runcommand takes a timeout, but it runs the
# command under a shell and kills only that shell - an rsync and its ssh child outlive
# it, keep the pipes open, and the read that was supposed to be bounded blocks anyway.
# So ssh is told when to give up connecting, and rsync when to give up waiting.
CONNECT_TIMEOUT = 15
IO_TIMEOUT = 120
SSH_OPTIONS = (f"-o BatchMode=yes -o ConnectTimeout={CONNECT_TIMEOUT} "
               f"-o ServerAliveInterval=15 -o ServerAliveCountMax=3")


class Plugin():
    """
    Class for delivering profiles to a running node.
    """
    """
    This plugin class requires 1 mandatory method:
    -- deliver
    """

    def __init__(self):
        self.logger = Log.get_logger()

    def deliver(self, node=None, hostname=None, bundle=None, timeout=300):
        """
        Input  - node name, the host to reach it on, and a local bundle directory holding
                 the payload and the applier
        Output - (status, message). On success the message is the digest the node reports
                 it now holds, which is what the caller records.

        The timeout is the point of the whole thing: one node that accepts a connection and
        then stops answering must cost a bounded wait, not a stuck worker.
        """
        target = hostname or node
        # rsync creates only the last component of the destination, and a node that has
        # never had a profile has none of the path at all. --rsync-path does the mkdir on
        # the far side in the same connection rather than costing a second one
        # --timeout is the I/O stall bound; the connect bound is ssh's own, because
        # --contimeout applies only to an rsync daemon and is a usage error over ssh
        command = (f"rsync -aH --delete --timeout={IO_TIMEOUT} "
                   f"-e 'ssh {SSH_OPTIONS}' --rsync-path='mkdir -p {STAGING} && rsync' "
                   f"{bundle}/ {target}:{STAGING}/")
        self.logger.debug(command)
        message, exit_code = Helper().runcommand(command, True, timeout)
        if exit_code != 0:
            return False, f"could not copy the profile bundle to {target}: {message}"

        command = f"ssh {SSH_OPTIONS} {target} python3 {STAGING}/apply_profiles.py {STAGING}"
        self.logger.debug(command)
        message, exit_code = Helper().runcommand(command, True, timeout)
        output = ''
        if message:
            try:
                output = message[0].decode() if isinstance(message[0], bytes) else str(message[0])
            except (IndexError, AttributeError):
                output = str(message)
        if exit_code != 0:
            return False, f"applying profiles on {target} failed: {output}"

        digest = ''
        for line in output.splitlines():
            if line.startswith('DIGEST '):
                digest = line.split(' ', 1)[1].strip()
        if not digest:
            # the applier ran and said nothing we understand. treating that as success
            # would record a digest we never received and mark the node in sync on a guess
            return False, f"applier on {target} reported no digest: {output}"
        return True, digest
