#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

    def create(self,image_file,files_path,server_ipaddress=None,server_port=None):
        return True,"Success"

    def cleanup(self,osimage,files_path,current_packed_image_file):
        return True,"Success"

    # -------------------------------
    # the fetch variable defines the method used in the template to fetch the image_file
    # -------------------------------
    fetch = """
    echo "Luna2: Downloading imagefile {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_IMAGEFILE }} to /{{ LUNA_SYSTEMROOT }}/{{ LUNA_IMAGEFILE }}"
    curl -H "x-access-tokens: $LUNA_TOKEN" -s {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_IMAGEFILE }} > /{{ LUNA_SYSTEMROOT }}/{{ LUNA_IMAGEFILE }}
    return $?
    """
