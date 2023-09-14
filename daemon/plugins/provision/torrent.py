#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the Torrent plugin, which takes care of nay torrent related things

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import libtorrent
from utils.log import Log
from common.constant import CONSTANT
from utils.helper import Helper


class Plugin():
    """
    Class for operating with torrents.
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

    def create(self, image_file=None, files_path=None, server_ipaddress=None, server_port=None, server_protocol=None):
        """
        This method will create a imagefile.
        """
        self.logger = Log.get_logger()

        if not os.path.exists(files_path + '/' + image_file):
            self.logger.error(f"{files_path}/{image_file} does not exist.")
            return False, f"{files_path}/{image_file} does not exist"

        host = server_ipaddress
        port = server_port
        proto = server_protocol or 'http'

        if (not host) or (not port):
            self.logger.error("Tracker host/port not configured.")
            return False,"Tracker host/port not configured"

        if not os.path.exists(files_path):
            os.makedirs(files_path)
            # os.chown(files_path, user_id, grp_id)
            os.chmod(files_path, 0o755)

        old_cwd = os.getcwd()
        os.chdir(files_path)
        # torrent_file = files_path + '/' + image_file + ".torrent"
        torrent_file = image_file + ".torrent"

        command = f"transmission-create -t {proto}://{host}:{port}/announce -o {torrent_file} {image_file}"
        message, exit_code = Helper().runcommand(command, True, 600)

        if exit_code == 0:
            os.chmod(torrent_file, 0o644)
        os.chdir(old_cwd)

        if exit_code != 0:
            self.logger.error(f"transmission-create returned exit_code [{exit_code}]")
            return False, message

        if not os.path.exists(files_path + '/' + torrent_file):
            self.logger.error(f"{files_path}/{torrent_file} does not exist.")
            return False, f"{files_path}/{torrent_file} does not exist"

        torrent_file = files_path + '/' + torrent_file
        command = f"transmission-remote --add {torrent_file}"
        message, exit_code = Helper().runcommand(command, True, 60)
        if exit_code == 0:
            return True,"Success"
        return False, message



    # osimage = the name of the image, e.g. compute
    # current_packed_image_file = the currently used compressed image file, most likely a tar.bz2 file
    def cleanup(self, osimage=None, files_path=None, current_packed_image_files=[]):
        """
        This method will cleanup the imagefile.
        """
        self.logger = Log.get_logger()
        grep = '|'.join(current_packed_image_files)
        command = f"transmission-remote -l | grep {osimage} | grep -vE \"{grep}\""
        command += " | awk '{ print $1 }' | grep -oE '[0-9]+' | xargs -i transmission-remote -t {} --remove-and-delete"
        self.logger.info(f"what i will run: {command}")
        message, exit_code = Helper().runcommand(command, True, 60)
        self.logger.debug(f"what i got back: {message}")
        command = f"cd {files_path} && ls {osimage}*.torrent | grep -vwE \"{grep}\" | grep \".torrent\" | xargs rm -f"
        self.logger.info(f"what i will run: {command}")
        message, exit_code = Helper().runcommand(command, True, 60)
        if exit_code == 0:
            return True, message
        return False, message

    # -------------------------------
    # the fetch variable defines the method used in the template to fetch the image_file
    # -------------------------------
    fetch = """
    echo "Luna2: Downloading torrent" | tee -a /tmp/luna-installer.log
    cd /{{ LUNA_SYSTEMROOT }}
    curl -H "x-access-tokens: $LUNA_TOKEN" -s {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_IMAGEFILE }}.torrent > {{ LUNA_IMAGEFILE }}.torrent
    #aria2c --seed-time=0 --enable-dht=false --max-connection-per-server=2 --bt-stop-timeout=300 {{ WEBSERVER_PROTOCOL }}://{{ LUNA_CONTROLLER }}:{{ WEBSERVER_PORT }}/files/{{ LUNA_TORRENT }}
    aria2c --seed-time=0 --enable-dht=false --max-connection-per-server=2 --bt-stop-timeout=120 --check-certificate=false {{ LUNA_IMAGEFILE }}.torrent
    ret=$?
    rm -f {{ LUNA_IMAGEFILE }}.torrent *.aria 2> /dev/null
    return $ret
    """
