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
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


class Monitor(object):

    def __init__(self):
        # >> lpart << runs the same install as three phases of its own. They are
        # not the operator's pre/part/post scripts - pre prepares lpart's runtime,
        # part carries the partitioning, download and extract together, post
        # finalises the bootloader - but they sit in the same stretches of the
        # flow, so a reader of a node's state sees the same progression either
        # way. Absent from here they are neither ok nor failed, and a node
        # spends its whole install unrecognised.
        self.node_state = {
            204: [
                "install.discovered",
                "install.rendered",
                "install.downloaded",
                "install.started",
                "install.completed",
                "install.scripts",
                "install.prescript",
                "install.setupbmc",
                "install.partscript",
                "install.lpart.pre",
                "install.lpart.part",
                "install.lpart.post",
                "install.download",
                "install.unpack",
                "install.setnet",
                "install.secrets",
                "install.postscript",
                "install.roles",
                "install.profiles",
                "install.image",
                "install.finalizing",
                "install.success",
                "install.booted"
            ],
            500: [
                "install.finalizing",
                "install.error"
            ]
        }

    def installer_state(self,state,status=404):
        if state in self.node_state[204]:
            state = state.replace("install.", '')
            state = f'Luna installer: {state}'
            return state,200
        elif state in self.node_state[500]:
            state = state.replace("install.", '')
            state = f'Luna installer: {state}'
            return state,500
        return state,status


    def item_state(self,state=None,status=True):
        if status:
            return state,200
        return state,501
