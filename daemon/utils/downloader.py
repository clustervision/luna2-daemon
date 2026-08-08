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
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
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
from utils.hashes import Hashes


class Downloader(object):
    """Class for downloading and copying operations"""

    def __init__(self):
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.osimage_plugins = Helper().plugin_finder(f'{plugins_path}/osimage')


    def pull_image_data(self,osimage,host):
        # host is the remote server from where we want to pull/sync from
        status=False
        image = Database().get_record(table='osimage', where=f"name='{osimage}'")
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
        image = Database().get_record(table='osimage', where=f"name='{osimage}'")
        if image:
            location=CONSTANT["FILES"]["IMAGE_FILES"]
            failed=[]
            for file in ['kernelfile','initrdfile','imagefile']:
                if image[0][file]:
                    expected=self.remote_hash(host,osimage,image[0][file])
                    status,_=Request().download_file(host,image[0][file],location,expected_sha256=expected)
                    if not status:
                        # Same shape as the unpack retry in tasks_mother: a transfer that
                        # failed once is usually worth one more attempt, and here is the
                        # only place that knows it failed - the controller that queued the
                        # sync saw whether the journal accepted the request, never whether
                        # a byte arrived, and its task is long gone by now.
                        sleep(5)
                        self.logger.warning(f"first attempt to fetch {file} for osimage {osimage} failed. Retrying one more time")
                        status,_=Request().download_file(host,image[0][file],location,expected_sha256=expected)
                    if not status:
                        failed.append(image[0][file])
                        self.logger.error(f"downloading {file} for osimage {osimage} returned an error")
                    else:
                        # Record what we now hold, whether or not the peer could tell
                        # us what to expect. Roles flip: a controller that pulled today
                        # is master tomorrow, and it has to answer the same question it
                        # just asked - otherwise a gap propagates, because the next
                        # slave pulls from a master that never learned its own hashes.
                        # hash_value is used when the download was verified (free, the
                        # bytes already went through a digest); path makes it compute
                        # one when the peer offered nothing.
                        Hashes().record('osimage',osimage,image[0][file],
                                        hash_value=expected,
                                        path=f"{location}/{image[0][file]}")
                else:
                    self.logger.warning(f"could not download {file} for osimage {osimage}. it has no value")
            self.report_sync_outcome(osimage,failed)
        # deliberately unconditional. the journal dispatch is ordered and unguarded:
        # raising holds the queue until someone fixes the cause, returning lets the
        # records behind this one apply. a file transfer must not hold replication,
        # so a failed pull is logged and life goes on. see journal.handle_requests.
        return True


    def report_sync_outcome(self,osimage,failed):
        """
        Say what actually happened, because the return value is not allowed to.

        The return above means 'the journal may carry on', never 'the files
        arrived' - and it has to stay that way. But the controller that queued the
        sync reported success before the first byte was fetched: it only ever saw
        whether the journal accepted the request, and by the time this runs it has
        long since moved on. So this is the only place that knows the outcome, and
        the only place that can correct the claim.
        """
        if failed:
            state=f"Image sync failed for {osimage}: {', '.join(failed)} did not arrive"
            code='501'
            self.logger.error(state)
        else:
            state=f"Image sync success for {osimage}"
            code='200'
            self.logger.info(state)
        try:
            # Imported here rather than at module scope: utils must not depend on base,
            # and update_itemstatus has no utils-level equivalent. Keeping it local
            # confines the exception to the one call that needs it and keeps this
            # module's import graph to utils, which is what it otherwise is.
            from base.monitor import Monitor
            Monitor().update_itemstatus(item='sync', name=osimage,
                                        request_data={'monitor':{'status':{osimage:{'state':state,'status':code}}}})
        except Exception as exp:
            # Reporting must never be what breaks the journal path. A status we
            # could not write is bad; an exception here would be worse.
            self.logger.error(f"could not report the sync outcome for {osimage}: {exp}")



    def remote_hash(self,host,osimage,file):
        # Ask the peer what its own copy hashes to. Best effort by design: a peer
        # that predates the hash table, or an artefact packed before it existed,
        # answers nothing - and that means 'cannot verify', not 'fail'.
        status,data,code=Request().get_request_code(host,f'/hash/osimage/{osimage}/{file}')
        if not status or not data:
            # 404 means the peer genuinely holds no hash for this artefact. Anything
            # else - no code at all, a 5xx, an auth failure - means we could not ask,
            # which is a different thing and must not be mistaken for it.
            if code == 404:
                self.logger.info(f"{host} holds no hash for {file}; it will not be verified")
            else:
                self.logger.warning(f"could not ask {host} for the hash of {file} (code {code}); it will not be verified")
            return None
        try:
            return data['config']['hash']['osimage'][osimage][file]['hash']
        except (KeyError, TypeError, ValueError, IndexError):
            # Whatever shape a peer answers with, an unusable answer means 'cannot
            # verify' and never an error. Deliberately NOT a bare except: this runs
            # on the journal path, where a genuine code fault should still raise and
            # hold the queue rather than be swallowed.
            self.logger.info(f"{host} returned no usable hash for {file}; it will not be verified")
        return None



