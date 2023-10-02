#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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

This endpoint can be contacted to obtain service status.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


class Monitor(object):

    def __init__(self):
        self.node_status = {
            204: [
                "install.discovery",
                "install.downloaded",
                "install.started",
                "install.completed",
                "install.prescript",
                "install.partscript",
                "install.postscript",
                "install.image",
                "install.finalizing",
                "install.success"
            ],
            500: [
                "install.finalizing",
                "install.error"
            ]
        }

    def installer_state(self,status):
        if status in self.node_status[204]:
            status = status.replace("install.", '')
            status = f'Luna installer: {status}'
            return status,200
        elif status in self.node_status[500]:
            status = status.replace("install.", '')
            status = f'Luna installer: {status}'
            return status,500
        return status,200
