#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import pwd
import shutil
import json
from configparser import RawConfigParser
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT, LUNAKEY
from utils.helper import Helper
from time import sleep, time
import sys
from utils.status import Status
from utils.queue import Queue
import libtorrent


class Torrent(object):
    """Class for operating with torrents"""

    def __init__(self):
        self.logger = Log.get_logger()


    def create_torrent(self,tarball):
        # TODO check if root

        path_to_store = CONSTANT['FILES']['TARBALL']

        if not os.path.exists(path_to_store +'/'+ tarball):
            self.logger.error(f"{path_to_store}/{tarball} does not exist.")
            return False,f"{path_to_store}/{tarball} does not exist"

        host,port=None,9091
        controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
        if controller:
            host = controller[0]['ipaddress']
            port = controller[0]['serverport']
            if 'TORRENTSERVER' in CONSTANT.keys():
               if 'PORT' in CONSTANT['TORRENTSERVER']:
                   port = CONSTANT['TORRENTSERVER']['PORT']
               if 'HOST' in CONSTANT['TORRENTSERVER']:
                   host = CONSTANT['TORRENTSERVER']['HOST']

        if (not host) or (not port):
            self.logger.error("Tracker host/port not configured.")
            return False,"Tracker host/port not configured"

        if not os.path.exists(path_to_store):
            os.makedirs(path_to_store)
#            os.chown(path_to_store, user_id, grp_id)
            os.chmod(path_to_store, 0o755)

        old_cwd = os.getcwd()
#        os.chdir(os.path.dirname(tarball))
        os.chdir(path_to_store)

        torrentfile = path_to_store +'/'+ tarball + ".torrent"

        fs = libtorrent.file_storage()
#        libtorrent.add_files(fs, os.path.basename(tarball))
        libtorrent.add_files(fs, tarball)
        t = libtorrent.create_torrent(fs)
##        if cluster.get('frontend_https'):
##            proto = 'https'
##        else:
##            proto = 'http'
##        t.add_tracker((proto + "://" + str(tracker_address) +
##                       ":" + str(tracker_port) + "/announce"))
##
##        t.set_creator(torrent_key)
##        t.set_comment(uid)
        libtorrent.set_piece_hashes(t, ".")

        f = open(torrentfile, 'wb')
        f.write(libtorrent.bencode(t.generate()))
        f.close()
##        os.chown(torrentfile, user_id, grp_id)

##        self.set('torrent', str(uid))
        os.chdir(old_cwd)

        return True,"success"



