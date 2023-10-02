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
This Is the Http plugin, which takes care of the http based provisioning

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    Class for operating with regular http provisioning
    """
    """
    This plugin class requires 2 mandatory methods:
    -- create
    -- cleanup
    it also needs a mandatory variable set for template functionality
    -- fetch
    """

    def __init__(self):
        self.logger = ""

    def create(self, image_file, files_path, server_ipaddress=None, server_port=None, server_protocol=None):
        return True,"Success"

    def cleanup(self, files_path=None, image_file=None):
        return True,"Success"

    # -------------------------------
    # the fetch variable defines the method used in the template to fetch the image_file
    # -------------------------------
    fetch = """
    echo "Luna2: Downloading imagefile {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_IMAGEFILE }} to /{{ LUNA_SYSTEMROOT }}/{{ LUNA_IMAGEFILE }}"
    curl -H "x-access-tokens: $LUNA_TOKEN" -s {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_IMAGEFILE }} > /{{ LUNA_SYSTEMROOT }}/{{ LUNA_IMAGEFILE }}
    return $?
    """
