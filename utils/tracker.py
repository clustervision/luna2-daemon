#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the tracker Class, which takes care of torrent tracker business

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

#import os
#import pwd
#import shutil
#import json
from configparser import RawConfigParser
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT, LUNAKEY
from utils.helper import Helper
from time import sleep, time
#import sys
from utils.status import Status
from utils.queue import Queue
#import libtorrent

import random
import logging
import binascii
import datetime

from struct import pack
from socket import inet_aton
#from httplib import responses
from libtorrent import bencode


class Tracker(object):
    """Class for operating with torrents"""

    def __init__(self):
        self.logger = Log.get_logger()
        self.PEER_INCREASE_LIMIT = 30
        self.DEFAULT_ALLOWED_PEERS = 50
        self.MAX_ALLOWED_PEERS = 200
        self.INFO_HASH_LEN = 20
        self.PEER_ID_LEN = 20

        # HTTP Error Codes for BitTorrent Tracker
        self.INVALID_REQUEST_TYPE = 100
        self.MISSING_INFO_HASH = 101
        self.MISSING_PEER_ID = 102
        self.MISSING_PORT = 103
        self.INVALID_INFO_HASH = 150
        self.INVALID_PEER_ID = 151
        self.INVALID_NUMWANT = 152
        self.GENERIC_ERROR = 900
        self.PYTT_RESPONSE_MESSAGES = {
            self.INVALID_REQUEST_TYPE: 'Invalid Request type',
            self.MISSING_INFO_HASH: 'Missing info_hash field',
            self.MISSING_PEER_ID: 'Missing peer_id field',
            self.MISSING_PORT: 'Missing port field',
            self.INVALID_INFO_HASH: ('info_hash is not %d bytes' %
                                     self.INFO_HASH_LEN),
            self.INVALID_PEER_ID: 'peer_id is not %d bytes' % self.PEER_ID_LEN,
            self.INVALID_NUMWANT: ('Peers more than %d is not allowed.' %
                                   self.MAX_ALLOWED_PEERS),
            self.GENERIC_ERROR: 'Error in request',
        }
        self.tracker_interval = 120
        self.tracker_min_interval = 120
        self.tracker_maxpeers = 100

#        responses.update(self.PYTT_RESPONSE_MESSAGES)

#        self.tracker_interval = params['luna_tracker_interval']
#        self.tracker_min_interval = params['luna_tracker_min_interval']
#        self.tracker_maxpeers = params['luna_tracker_maxpeers']
#        self.mongo_db = params['mongo_db']


    def get_error(self,myerror):
        mesg="<html><title>900: unknown error</title><body>900: unknown error</body></html>"
        if myerror in self.PYTT_RESPONSE_MESSAGES.keys():
            mesg=f"<html><title>{myerror}: {self.PYTT_RESPONSE_MESSAGES[myerror]}</title><body>{myerror}: {self.PYTT_RESPONSE_MESSAGES[myerror]}</body></html>"
        return 200,mesg


    #CREATE TABLE `tracker` ( `id`  INTEGER  NOT NULL ,  `infohash`  VARCHAR ,  `peer`  VARCHAR ,  `ipaddress`  VARCHAR ,  `port`  INTEGER ,  `download`  INTEGER ,  `upload`  INTEGER ,  `left`  INTEGER ,  `updated`  VARCHAR ,  `status`  VARCHAR , PRIMARY KEY (`id` AUTOINCREMENT));

    def update_peers(self, info_hash, peer_id, ip, port, status=None, uploaded=None, downloaded=None, left=None):
        """Store the information about the peer"""

        result=False
        row = [{"column": "infohash", "value": f"{info_hash}"},
               {"column": "ipaddress", "value": f"{ip}"},
               {"column": "port", "value": f"{port}"},
               {"column": "updated", "value": "current_datetime"}]
        if status:
            row.append({"column": "status", "value": f"{status}"})
        if uploaded:
            row.append({"column": "upload", "value": f"{uploaded}"})
        if downloaded:
            row.append({"column": "download", "value": f"{downloaded}"})
        if left:
            row.append({"column": "left", "value": f"{left}"})
        peercheck = Database().get_record(None, 'tracker', f"WHERE peer='{peer_id}'")
        if peercheck:
            where = [{"column": "peer", "value": f"{peer_id}"}]
            result = Database().update('tracker', row, where)
        else:
            row.append({"column": "peer", "value": f"{peer_id}"})
            result = Database().insert('tracker', row)
        return result


    def get_peers(self, info_hash, numwant, compact, no_peer_id, age):
#        time_age = datetime.datetime.utcnow() - datetime.timedelta(seconds=age)
        peer_tuple_list = [('luna2controller','10.141.255.254','51413')]
        n_leechers = 0
        n_seeders = 0

        peers = Database().get_record(None, 'tracker', f"WHERE infohash='{info_hash}' AND updated>datetime('now','-{age} second') ORDER BY updated DESC")

        if peers:
            for peer in peers:
                self.logger.info(f"peer [{peer['peer']}]")
                if peer['peer']:
                    peer_tuple_list.append((binascii.unhexlify(peer['peer']),peer['ipaddress'], peer['port']))
                    try:
                        n_leechers += int(peer['status'] == 'started')
                        n_seeders += int(peer['status'] == 'completed')
                    except:
                        pass
            

#        nodes = self.mongo_db['tracker'].find({'info_hash': info_hash,
#                                               'updated': {'$gte': time_age}},
#                                              {'peer_id': 1, 'ip': 1,
#                                               'port': 1, 'status': 1})
#        for doc in nodes:
#            peer_tuple_list.append((binascii.unhexlify(doc['peer_id']),
#                                    doc['ip'], doc['port']))
#
#            try:
#                n_leechers += int(doc['status'] == 'started')
#                n_seeders += int(doc['status'] == 'completed')
#            except:
#                pass
#
#        peer_id = binascii.hexlify('lunalunalunalunaluna')
#        servers = self.mongo_db['tracker'].find({'info_hash': info_hash,
#                                                 'peer_id': peer_id,
#                                                 'port': {'$ne': 0}},
#                                                {'peer_id': 1, 'ip': 1,
#                                                 'port': 1, 'status': 1})
#        for doc in servers:
#            peer_tuple_list.append((binascii.unhexlify(doc['peer_id']),
#                                    doc['ip'], doc['port']))
#
#            try:
#                n_leechers += int(doc['status'] == 'started')
#                n_seeders += int(doc['status'] == 'completed')
#            except:
#                pass

        if numwant > len(peer_tuple_list):
            numwant = len(peer_tuple_list)

        peers = []
        compact_peers = b''
        random_peer_list = random.sample(peer_tuple_list, numwant)
        for peer_info in random_peer_list:
            if compact:
                try:
                    ip = inet_aton(peer_info[1])
                    port = pack('>H', int(peer_info[2]))
                    compact_peers += (ip+port)
                except:
                    pass

                continue

            p = {}
            p['peer_id'], p['ip'], p['port'] = peer_info
            peers.append(p)

#        self.response['complete'] = n_seeders
#        self.response['incomplete'] = n_leechers

        if compact:
            self.logger.debug('compact peer list: %r' % compact_peers)
            peers = compact_peers
#            self.response['peers'] = compact_peers

        else:
            self.logger.debug('peer list: %r' % peers)
#            self.response['peers'] = peers

        return peers

    def announce(self,params,peerip=None):
        failure_reason = ''
        warning_message = ''

        info_hash=None
        if 'info_hash' in params:
            info_hash = params['info_hash']
        if info_hash is None:
            return self.get_error(self.MISSING_INFO_HASH)
        elif len(info_hash) != self.INFO_HASH_LEN:
            return self.get_error(self.INVALID_INFO_HASH)
        info_hash=binascii.hexlify(b"{info_hash}")
        info_hash=info_hash.decode()

        peer_id = None
        if 'peer_id' in params:
            peer_id=params['peer_id']
        if peer_id is None:
            return self.get_error(self.MISSING_PEER_ID)
        elif len(peer_id) != self.PEER_ID_LEN:
            return self.get_error(self.INVALID_PEER_ID)
        peer_id=binascii.hexlify(b"{peer_id}")
        peer_id=peer_id.decode()

        #xreal_ip = self.request.headers.get('X-Real-IP', default=None)
        announce_ip=None
        if 'ip' in params:
            ip=params['ip']
        if announce_ip == '0.0.0.0':
            announce_ip = None
        ip = announce_ip or peerip

        port=None
        if 'port' in params:
            try:
                port = int(params['port'])
            except:
                return self.get_error(self.MISSING_PORT)
        if port is None:
            return self.get_error(self.MISSING_PORT)

        info_hash = str(info_hash)
        uploaded,downloaded,left,compact,no_peer_id,event,tracker_id = '0','0','0','0','0',None,None
        if 'uploaded' in params:
            uploaded = params['uploaded']
        if 'downloaded' in params:
            downloaded = params['downloaded']
        if 'left' in params:
            left = params['left']
        if 'compact' in params:
            compact = params['compact']
        if 'no_peer_id' in params:
            no_peer_id = params['no_peer_id']
        if 'event' in params:
            event = params['event']
        if 'tracker_id' in params:
            tracker_id = params['tracker_id']

        numwant=self.DEFAULT_ALLOWED_PEERS
#        numwant = int(self.get_argument('numwant',
#                                        default=self.DEFAULT_ALLOWED_PEERS))

        if numwant > self.tracker_maxpeers:
            # XXX: cannot request more than MAX_ALLOWED_PEERS.
            return self.get_error(self.INVALID_NUMWANT)

        self.update_peers(info_hash, peer_id, ip, port, event, uploaded, downloaded, left)

        # generate response
        response = {}

        # Interval in seconds that the client should wait between sending
        # regular requests to the tracker.
        response['interval'] = self.tracker_interval

        # Minimum announce interval. If present clients must not re-announce
        # more frequently than this.
        response['min interval'] = self.tracker_min_interval

        response['tracker id'] = tracker_id

        if failure_reason:
            response['failure reason'] = failure_reason

        if warning_message:
            response['warning message'] = warning_message

        self.get_peers(info_hash, numwant, compact, no_peer_id,
                       self.tracker_interval * 2)

#        self.set_header('Content-Type', 'text/plain')
#        self.write(bencode(self.response))
#        self.finish()
        return 200,bencode(response)


    def scrape(self):
        """Returns the state of all torrents this tracker is managing"""
        response = {}

        info_hashes = self.get_arguments('info_hash')
        for info_hash in info_hashes:
            info_hash = str(info_hash)
            response[info_hash] = {}
            numwant = 100
            compact = True
            no_peer_id = 1

            complete, incomplete, _ = self.get_peers(info_hash, numwant,
                                                     compact, no_peer_id,
                                                     self.tracker_interval * 2)

            response[info_hash]['complete'] = complete
            response[info_hash]['downloaded'] = complete
            response[info_hash]['incomplete'] = incomplete

#        self.set_header('content-type', 'text/plain')
#        self.write(bencode(response))
#        self.finish()


