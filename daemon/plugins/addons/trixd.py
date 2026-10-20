#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
Addon Class ::  Reaching the trix-daemon (trixd) beside this controller.

Offers get_credentials, get_token and get_token_for to any plugin that needs to call
trixd, and notify to tell it something changed. The mirror of trixd's own luna plugin:
each daemon reads the other's ini for facts about the other, and neither depends on the
other's signing secret.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import threading
from configparser import RawConfigParser

import requests

from utils.log import Log

# trixd's own ini, read for facts about trixd. The environment wins so a test or a
# second instance can point somewhere else, as trixd reads TRIXD_LUNA_INI for ours.
TRIXD_INI = '/trinity/local/trixd/daemon/config/trixd.ini'
API_PREFIX = '/api/v1'
# A hook runs inside Luna's request thread, so a slow or absent trixd must cost a
# write almost nothing. No retries for the same reason: the hourly sweep in trixd is
# what covers a push that did not land, not a Luna worker waiting here.
TIMEOUT = 5

_resolved = None
_token = None
_lock = threading.Lock()


def _config() -> dict:
    """
    Where trixd answers, and the account it names, from trixd.ini.
    """
    path = os.environ.get('TRIXD_INI', TRIXD_INI)
    parser = RawConfigParser()
    parser.read(path)
    bind = parser.get('API', 'BIND', fallback='').strip()
    ca_file = parser.get('REPLICATION', 'CA_FILE', fallback='').strip()
    return {
        'path': path,
        'protocol': parser.get('API', 'PROTOCOL', fallback='https').strip() or 'https',
        'port': bind.rsplit(':', 1)[-1] if ':' in bind else '8050',
        'username': parser.get('API', 'USERNAME', fallback='').strip(),
        'password': parser.get('API', 'PASSWORD', fallback='').strip(),
        'verify': ca_file if ca_file and os.path.isfile(ca_file) else True,
    }


def _me() -> str:
    """
    This controller's own address, bracketed when it is IPv6, or the loopback when this
    machine is not one of the controller rows - a development box, or a database that
    cannot answer.

    Its address and not its name, for the reason Luna's own peer calls resolve a
    controller to an address: the controller name held in the database is the short
    form, while the certificate names the fully qualified one and carries the addresses
    as alternative names. So the name fails verification against the cluster CA, and
    the address does not.
    """
    try:
        from utils.ha import HA
        from utils.helper import Helper
        address = HA().get_my_ip()
        if not address:
            return '127.0.0.1'
        return f'[{address}]' if Helper().check_if_ipv6(address) else address
    except Exception:
        return '127.0.0.1'


def where() -> dict:
    """
    Where trixd is and how to be let in, worked out once for the life of the process.
    Derived rather than configured: trixd sits on this controller, so nothing should
    have to be told twice where it is.
    """
    global _resolved
    with _lock:
        if _resolved is None:
            config = _config()
            config['base'] = f"{config['protocol']}://{_me()}:{config['port']}{API_PREFIX}"
            _resolved = config
            Log.get_logger().info(f"trixd addon will reach trixd at {config['base']}")
        return _resolved


def get_credentials() -> tuple:
    """
    The account trixd.ini names, for a caller that authenticates by itself.
    """
    config = where()
    return config['username'], config['password']


def get_token(renew: bool = False) -> str:
    """
    A token for this daemon's own calls to trixd, held for as long as it works.
    Pass renew=True after trixd has refused one: the held token is then replaced
    rather than presented again.
    """
    global _token
    username, password = get_credentials()
    # The held token is tied to what produced it, so moving trixd.ini or changing the
    # account drops it instead of presenting it to the wrong daemon until it expires.
    fingerprint = (where()['base'], username)
    with _lock:
        if not renew and _token and _token[0] == fingerprint:
            return _token[1]
        _token = None
    fetched = get_token_for(username, password)
    if fetched:
        with _lock:
            _token = (fingerprint, fetched)
    return fetched


def get_token_for(username: str, password: str) -> str:
    """
    A token as a named account, never held: a token belonging to somebody else must
    not be handed to the next caller that asks for this daemon's own.
    """
    logger = Log.get_logger()
    config = where()
    try:
        answer = requests.post(f"{config['base']}/auth/token",
                               json={'username': username, 'password': password},
                               timeout=TIMEOUT, verify=config['verify'])
        if answer.status_code >= 400:
            logger.error(f"trixd refused {username}: {answer.status_code}")
            return None
        return (answer.json() or {}).get('token')
    except Exception as exp:
        logger.error(f"no token from trixd at {config['base']}: {exp}")
        return None


def notify(event: str = None, payload: dict = None) -> bool:
    """
    Tell trixd that something changed here, and do not wait for it to act on it.

    Never raises and never holds up the write that called it: a controller without
    trixd, or with trixd down, goes on working exactly as it did before.
    """
    return notify_many([{'event': event, 'payload': payload or {}}])


def notify_many(changes: list = None) -> bool:
    """
    Tell trixd about a whole set of changes at once, on the same terms as notify: a
    caller with a hundred of them makes one call, not a hundred.
    """
    if not changes:
        # trixd refuses an empty set, so there is nothing to ask it.
        return False
    logger = Log.get_logger()
    config = where()
    body = {'changes': changes}
    for attempt in (1, 2):
        token = get_token(renew=attempt == 2)
        if not token:
            return False
        try:
            answer = requests.post(f"{config['base']}/system/bulk", json=body,
                                   headers={'x-access-tokens': token},
                                   timeout=TIMEOUT, verify=config['verify'])
        except Exception as exp:
            logger.error(f"could not tell trixd about {len(changes)} changes: {exp}")
            return False
        if answer.status_code in (401, 403) and attempt == 1:
            # The token is no longer good to trixd. One more with a fresh one.
            continue
        if answer.status_code >= 400:
            logger.error(f"trixd answered {answer.status_code} for {len(changes)} "
                         f"changes: {answer.text[:200]}")
            return False
        logger.debug(f"told trixd about {len(changes)} changes: {answer.status_code}")
        return True
    return False
