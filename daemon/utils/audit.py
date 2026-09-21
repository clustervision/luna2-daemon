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
The audit trail: who did what to which object, and what came of it. One line per
state-changing call and per refusal, in a file of its own beside the daemon log, so it
can be handed over on its own and kept on its own schedule. Every line starts with the
label AUDIT and carries key=value pairs, so one grep finds a person, an object or every
refusal. Never a request body: no password and no secret content can land here.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import logging
import os
import socket
from utils.log import Log
from common.constant import CONSTANT

# Suffixes that change state on a GET; every POST does.
STATE_CHANGING_SUFFIXES = {'_delete', '_remove', '_unassign', '_pack', '_cancel', '_updatecerts', '_clone',
                           '_osgrab', '_ospush', '_biosgrab', '_biospush', '_firmwarepush', '_redfish',
                           '_provision', '_couple', '_decouple', '_chmod', '_chgrp', '_chown', '_set'}


class Audit():
    """
    This class writes the audit trail. The file is [AUDIT] LOGFILE in the ini, default
    luna2-audit.log beside the daemon log; every line also reaches the daemon log at debug.
    """

    _logger = None

    @classmethod
    def logger(cls):
        """
        The audit logger, a child of the daemon's, with its own file handler attached once.
        """
        if cls._logger is not None:
            return cls._logger
        logger = logging.getLogger('luna2-daemon.audit')
        logger.setLevel(logging.INFO)
        path = CONSTANT.get('AUDIT', {}).get('LOGFILE') or cls.default_path()
        if path:
            try:
                handler = logging.FileHandler(path)
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                logger.addHandler(handler)
            except OSError as exp:
                Log.get_logger().error(f'audit trail cannot open {path}: {exp}; audit lines go to the daemon log only')
        cls._logger = logger
        return logger

    @classmethod
    def default_path(cls):
        """
        Beside the daemon log, so the installer's rotation rule for that directory covers it.
        """
        daemon_log = CONSTANT.get('LOGGER', {}).get('LOGFILE')
        if not daemon_log:
            return None
        return os.path.join(os.path.dirname(daemon_log), 'luna2-audit.log')

    @classmethod
    def state_changing(cls, method=None, rule=None, action=None):
        """
        Whether a call changes state: every POST, and a GET on an action suffix. A control
        action is dynamic: status is a read, everything else acts on the node.
        """
        if method == 'POST':
            return True
        last = (rule or '').rstrip('/').split('/')[-1]
        if last == '_<string:action>':
            return 'status' not in str(action or '')
        return last in STATE_CHANGING_SUFFIXES

    def record(self, userid=None, username=None, source=None, method=None, path=None,
               requirement=None, outcome=None, code=None, detail=None, request_id=None):
        """
        Input - who (id, name, source), what (method, path), which object (from the
                requirement the grammar computed), and what came of it. No body, ever.
        """
        entity = (requirement or {}).get('entity') or '-'
        name = (requirement or {}).get('name') or '-'
        fields = [('user', username or '-'), ('id', '-' if userid is None else userid), ('source', source or '-'),
                  ('action', f'{method} {path}'), ('object', f'{entity} {name}' if name != '-' else entity),
                  ('outcome', outcome), ('code', code), ('controller', socket.gethostname().split('.')[0])]
        if request_id:
            fields.append(('request', request_id))
        if detail:
            fields.append(('detail', detail))
        line = 'AUDIT ' + ' '.join(f'{key}={self._quote(value)}' for key, value in fields)
        self.logger().info(line)
        Log.get_logger().debug(line)

    @staticmethod
    def _quote(value):
        text = str(value)
        return f'"{text}"' if ' ' in text or '=' in text else text
