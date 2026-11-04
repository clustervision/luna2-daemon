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
This Is the default OS Create plugin, which takes care of having an image's content built

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log

# The trix-daemon beside this controller builds the image; absent is normal, and then there
# is no builder here at all.
try:
    from plugins.addons.trixd import submit as trixd_submit
except Exception:
    trixd_submit = None

# Where the builder takes a job, below the addon's /api/v1.
BUILDER_PATH = '/osimage/create'


class Plugin():
    """
    Class for having the content of an image built
    """
    """
    This plugin class requires 1 mandatory method:
    -- create
    """

    def __init__(self):
        self.logger = Log.get_logger()

    def create(self, name=None, architecture=None, distribution=None, osrelease=None,
               path=None, request_id=None):
        """
        Hand the build to the builder beside this controller and report that it took the
        job. Returns (status, message, build_state): 'accepted' because the builder runs the
        build on its own and calls the pack route itself when it is done, so nothing here
        waits, polls or retries. Progress arrives on request_id while it runs.
        """
        if trixd_submit is None:
            return False, (f"no builder for osimage {name}: this controller has no trix-daemon "
                           f"addon, so there is nothing to build the image"), 'accepted'
        answer = trixd_submit(path=BUILDER_PATH, payload={
            'image': name,
            'architecture': architecture,
            'distribution': distribution,
            'osrelease': osrelease,
            'path': path,
            'request_id': request_id,
        })
        if answer is None:
            # Refused, unreachable, or no such builder. Saying so is the whole job here: the
            # caller ends the stream on it, where a quiet success leaves the operator polling
            # a build that nobody is doing.
            return False, (f"the builder did not take the build of osimage {name}. is the "
                           f"trix-daemon running beside this controller, with its osimage "
                           f"plugin enabled?"), 'accepted'
        self.logger.info(f"builder accepted the build of osimage {name}: {answer}")
        return True, f"the builder accepted the build of osimage {name}", 'accepted'
