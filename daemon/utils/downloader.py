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
This Is the osimage Class, which takes care of images

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import sys
from time import sleep
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT
from utils.helper import Helper
from utils.request import Request


class Downloader(object):
    """Class for downloading and copying operations"""

    def __init__(self):
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.osimage_plugins = Helper().plugin_finder(f'{plugins_path}/osimage')


    def pull_image_data(self,osimage,host):
        # host is the remote server from where we want to pull/sync from
        status=False
        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if image:
            image_directory = CONSTANT['FILES']['IMAGE_DIRECTORY']
            filesystem_plugin = 'default'
            if 'IMAGE_FILESYSTEM' in CONSTANT['PLUGINS'] and CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']:
                filesystem_plugin = CONSTANT['PLUGINS']['IMAGE_FILESYSTEM']
            os_image_plugin=Helper().plugin_load(self.osimage_plugins,'osimage/filesystem',filesystem_plugin)
            status, path = os_image_plugin().getpath(image_directory=image_directory, osimage=image[0]['name'], tag=None) # we feed no tag as tagged/versioned FS is normally R/O
            if status is True:
                hostip = Request().get_host_ip(host)
                status, mesg = os_image_plugin().syncimage(remote_host=hostip, remote_image_directory=path, osimage=image[0]['name'], local_image_directory=path)
                if status is False:
                    self.logger.error(f"error copying data from {host} for {osimage}: {mesg}")
        return status


    def pull_image_files(self,osimage,host):
        # host is the remote server from where we want to pull/sync from
        image = Database().get_record(None, 'osimage', f"WHERE name='{osimage}'")
        if image:
            location=CONSTANT["FILES"]["IMAGE_FILES"]
            for file in ['kernelfile','initrdfile','imagefile']:
                status,_=Request().download_file(host,image[0][file],location)
        return True



