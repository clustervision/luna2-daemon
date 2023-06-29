#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
