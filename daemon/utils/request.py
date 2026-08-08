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
Journal class tracks incoming requests that requires replication to other controllers.
It also receives requests that need to be dealt with by the controller itself.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from json import dumps,loads
from common.constant import CONSTANT
from utils.database import Database
from utils.log import Log
from utils.helper import Helper

import os
import re
import hashlib
from uuid import uuid4
from glob import glob
import requests
from requests import Session
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util import Retry

urllib3.disable_warnings()
session = Session()
retries = Retry(
    total = 3,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500, 404],
    allowed_methods = {'GET', 'POST'}
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# A second session for lookups where 404 is a legitimate answer rather than a
# transient fault. The shared session above lists 404 in its status_forcelist, so
# it retries three times and then raises - which makes "this object is gone"
# indistinguishable from "the peer is down", and acting on that would abandon live
# work every time a peer blinked.
lookup_retries = Retry(
    total = 3,
    backoff_factor = 0.3,
    status_forcelist = [502, 503, 504, 500],
    allowed_methods = {'GET'}
)
lookup_session = Session()
lookup_session.mount('https://', HTTPAdapter(max_retries=lookup_retries))

class Request():
    """
    This class offers remote token functionality. get remote token etc.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.protocol = CONSTANT['API']['PROTOCOL']
        self.verify = Helper().make_bool(CONSTANT['API']["VERIFY_CERTIFICATE"])
        _,self.alt_serverport,*_=(CONSTANT['API']['ENDPOINT'].split(':')+[None]+[None])
        self.bad_ret=['400','401','500','502','503']
        self.good_ret=['200','201','204']
        self.dict_controllers=None
        self.all_controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
                                                          ['ipaddress.tablerefid=controller.id'],
                                                          ["ipaddress.tableref='controller'"])
        if self.all_controllers:
            self.dict_controllers = Helper().convert_list_to_dict(self.all_controllers, 'hostname')


    def get_token(self,host):
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token_credentials = {'username': CONSTANT['API']['USERNAME'], 'password': CONSTANT['API']['PASSWORD']}
        token = None
        try:
            self.logger.debug(f"json for token: {token_credentials}")
            x = session.post(f'{self.protocol}://{endpoint}:{serverport}/token', json=token_credentials, stream=True, timeout=10, verify=self.verify)
            if (str(x.status_code) not in self.bad_ret) and x.text:
                data = loads(x.text)
                self.logger.debug(f"data received for token: {data}")
                if 'token' in data:
                    token=data["token"]
        except Exception as exp:
            self.logger.error(f"{exp}")
        return token

    def get_request(self,host,uri):
        uri = re.sub('^/', '', uri)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.get(f'{self.protocol}://{endpoint}:{serverport}/{uri}', headers=headers, stream=True, timeout=10, verify=self.verify)
                if str(x.status_code) in self.good_ret:
                    self.logger.debug(f"get request {uri} on {host} success. returned {x.status_code}")
                    data=None
                    if x.text:
                        data = loads(x.text)
                        self.logger.debug(f"data received for {uri}: {data}")
                    return True, data
                else:
                    self.logger.error(f"get request {uri} on {host} failed. returned {x.status_code}")
                    return False, None
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
        return False, None

    def sweep_dead_partials(self, location, filename):
        """
        Remove leftover .part files whose writer is gone.

        A download killed outright - SIGKILL, a power cut - cannot run its own
        cleanup, so the temporary survives and can be gigabytes. The pid is in the
        name, so liveness is checkable rather than guessed at: only a temporary
        belonging to a process that no longer exists is removed. That is why this
        is safe with several gunicorn workers, where an age-based sweep would
        eventually delete a slow but perfectly healthy download.
        """
        try:
            for path in glob(f'{location}/{filename}.part-*'):
                try:
                    pid = int(os.path.basename(path).rsplit('.part-', 1)[1].split('-')[0])
                except (IndexError, ValueError):
                    continue
                if os.path.isdir(f'/proc/{pid}'):
                    continue
                size = os.path.getsize(path)
                os.remove(path)
                self.logger.warning(f"removed stale partial download {os.path.basename(path)} ({size} bytes); its writer {pid} is gone")
        except Exception as exp:
            # Never fatal: failing to tidy up must not stop the download that is
            # about to start.
            self.logger.error(f"could not sweep stale partial downloads: {exp}")


    def get_request_code(self,host,uri):
        """
        Like get_request, but hands back the HTTP status code so a caller can tell
        'gone' from 'unreachable'. A separate method on purpose: get_request's
        (status, data) contract has callers that would break on a third value.
        Returns (status, data, code); code is None when there was no answer at all.
        """
        uri = re.sub('^/', '', uri)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if not token:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
            return False, None, None
        headers = {'x-access-tokens': token}
        try:
            x = lookup_session.get(f'{self.protocol}://{endpoint}:{serverport}/{uri}',
                                   headers=headers, stream=True, timeout=10, verify=self.verify)
            code = x.status_code
            if str(code) in self.good_ret:
                data = loads(x.text) if x.text else None
                return True, data, code
            self.logger.debug(f"get request {uri} on {host} returned {code}")
            return False, None, code
        except Exception as exp:
            # No answer at all - unreachable, TLS, timeout. Deliberately distinct
            # from a 404: the caller must not read this as 'the object is gone'.
            self.logger.error(f"{exp}")
        return False, None, None


    def post_request(self,host,uri,json):
        uri = re.sub('^/', '', uri)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if token:
            headers = {'x-access-tokens': token}
            try:
                x = session.post(f'{self.protocol}://{endpoint}:{serverport}/{uri}', headers=headers, json=json, stream=True, timeout=10, verify=self.verify)
                if str(x.status_code) in self.good_ret:
                    self.logger.debug(f"post request {uri} on {host} success. returned {x.status_code}")
                    data=None
                    if x.text:
                        data = loads(x.text)
                        self.logger.debug(f"data received for {uri}: {data}")
                    return True, data
                else:
                    self.logger.error(f"post request {uri} on {host} failed. returned {x.status_code}")
                    return False, None
            except Exception as exp:
                self.logger.error(f"{exp}")
        else:
            self.logger.error(f"no token for {uri} on host {host}. invalid credentials or host is down.")
        return False, None


    def download_file(self,host,filename,location,expected_sha256=None):
        # expected_sha256 is optional on purpose: an artefact produced before this
        # existed has no recorded hash, and must download exactly as it did then.
        # Absent means 'do not verify', never 'fail'.
        # The (status, message) return is unchanged - existing callers unpack two
        # values and a third would break them. A caller that wants the digest
        # recorded already has it: when expected_sha256 was supplied and we got
        # here, it matched by definition.
        filename = re.sub('^/', '', filename)
        endpoint=self.get_host_ip(host)
        serverport=self.get_host_port(host)
        if Helper().check_if_ipv6(endpoint):
            endpoint='['+endpoint+']'
        token=self.get_token(host)
        if not token:
            self.logger.error(f"no token for {filename} on host {host}. invalid credentials or host is down.")
            return False, None
        headers = {'x-access-tokens': token}
        target = location+'/'+filename
        # Download beside the target and rename in only once the transfer is complete
        # and verified. Writing straight to the served name means a failure part-way
        # leaves a truncated file under a name that nodes trust, and nothing removes it.
        # Unique per attempt, not per process: two pulls of the same file inside one
        # daemon share a pid, and would otherwise write to the same temporary and
        # trip over each other. Same directory, so the rename stays atomic.
        self.sweep_dead_partials(location, filename)
        partial = f'{target}.part-{os.getpid()}-{uuid4().hex[:8]}'
        try:
            url = f'{self.protocol}://{endpoint}:{serverport}/files/{filename}'
            # 'with': a streamed response returns its connection to the pool when the
            # body is consumed, and the early return below never consumes it.
            with session.get(url, headers=headers, stream=True, timeout=10, verify=self.verify) as x:
                if str(x.status_code) not in self.good_ret:
                    self.logger.error(f"get request download {filename} on {host} failed. returned {x.status_code}")
                    return False, None
                self.logger.debug(f"get request download {filename} on {host} success. returned {x.status_code}")
                # streamed rather than through x.content: the digest needs the bytes
                # anyway, and an imagefile is measured in gigabytes.
                advertised = x.headers.get('Content-Length')
                digest = hashlib.sha256()
                written = 0
                with open(partial, 'wb') as handle:
                    for chunk in x.iter_content(chunk_size=1048576):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            # length is the cheap early exit; it catches truncation and nothing else.
            if advertised is not None and written != int(advertised):
                self.logger.error(f"download of {filename} from {host} is short: {written} of {advertised} bytes")
                return False, None
            # the hash is the actual guarantee: a corrupted body of the right length
            # passes the check above.
            if expected_sha256 and digest.hexdigest() != expected_sha256:
                self.logger.error(f"checksum mismatch for {filename} from {host}")
                return False, None
            os.replace(partial, target)
            return True, 'success'
        except Exception as exp:
            self.logger.error(f"{exp}")
        finally:
            # on success the rename already consumed it; on any failure this is what
            # keeps a partial file from ever appearing under the served name.
            if os.path.exists(partial):
                try:
                    os.remove(partial)
                except OSError as exp:
                    self.logger.error(f"could not remove partial download {partial}: {exp}")
        return False, None


    def get_host_ip(self,host):
        endpoint=host
        if host in self.dict_controllers.keys():
            endpoint=self.dict_controllers[host]['ipaddress_ipv6'] or self.dict_controllers[host]['ipaddress']
        return endpoint

    def get_host_port(self,host):
        port=self.alt_serverport
        if host in self.dict_controllers.keys():
            port=self.dict_controllers[host]['serverport'] or self.alt_serverport
        return port

