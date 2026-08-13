#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
Delivering profile changes to running nodes.

A change queues one task per affected node in the 'profile' subsystem, and this mother
drains that queue in parallel batches. Whether a node needs anything is decided by
comparing two values in the database, so a node that is already in line costs nothing -
no connection is made at all.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import concurrent.futures
import os
import shutil
import tempfile
from json import dumps
from time import sleep
from common.constant import CONSTANT
from utils.database import Database
from utils.helper import Helper
from utils.log import Log
from utils.queue import Queue
from utils.ha import HA
from base.profile import Profile

APPLIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'nodescripts', 'apply_profiles.py')
DEFAULT_BATCH = 10
DEFAULT_DELAY = 0
DEFAULT_TIMEOUT = 300
RETRY_DELAY = '300s'


class ProfileSync():
    """
    This class delivers profiles to running nodes.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        plugins_path = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.delivery_plugins = Helper().plugin_finder(f'{plugins_path}/profile/delivery')


    def batch_settings(self):
        """
        How many deliveries run at once, and the pause between batches. Unlike the BMC
        batches this protects the controller rather than the far end: every child is an
        rsync plus an ssh of its own.
        """
        batch, delay = DEFAULT_BATCH, DEFAULT_DELAY
        # [PROFILES] is read only if an admin put it in luna.ini. Declaring it as a
        # required section would abort startup on every existing configuration that
        # does not have it - and abort before the logger exists to say why
        for option, default in (('PROFILE_BATCH_SIZE', batch), ('PROFILE_BATCH_DELAY', delay)):
            value = default
            try:
                value = int(str(CONSTANT['PROFILES'][option]).replace('s', ''))
            except (KeyError, TypeError, ValueError):
                pass
            if option.endswith('SIZE'):
                batch = max(1, value)
            else:
                delay = max(0, value)
        return batch, delay


    def skip_reason(self, name=None):
        """
        Why we would not even try this node right now. Both checks are free and both
        avoid a pointless connection attempt.
        """
        state = Database().get_record_join(['monitor.state as state'],
                                           ['monitor.tablerefid=node.id'],
                                           [f'node.name="{name}"', "monitor.tableref='node'"])
        if state and state[0]['state'] and str(state[0]['state']).startswith('install.'):
            return 'it is installing'
        return None


    def build_bundle(self, name=None):
        """
        The payload and the applier, in a directory of their own. The applier travels with
        the payload every time, so there is no node-side component to keep in step with
        the daemon.
        """
        status, payload = Profile().node_payload(name)
        if not status:
            return None, None
        digest = Profile().node_digest(name)
        payload['digest'] = digest
        bundle = tempfile.mkdtemp(prefix=f'luna-profiles-{name}-')
        with open(os.path.join(bundle, 'payload.json'), 'w', encoding='utf-8') as handle:
            handle.write(dumps(payload))
        shutil.copyfile(APPLIER, os.path.join(bundle, 'apply_profiles.py'))
        return bundle, digest


    def deliver_node(self, name=None):
        """
        Bring one node into line. Returns (status, message).

        Nothing here is done unless the node's digests differ, which is the whole reason
        a sweep over a large cluster is affordable: the decision costs one comparison and
        no connection.
        """
        node = Database().get_record_join(['node.id as nodeid', 'node.name as nodename',
                                           'node.hostname as hostname',
                                           'node.profiles_digest as delivered',
                                           'group.name as groupname'],
                                          ['group.id=node.groupid'],
                                          [f'node.name="{name}"'])
        if not node:
            return False, f'node {name} is not available'
        desired = Profile().node_digest(name)
        if desired and desired == node[0]['delivered']:
            return True, 'already in line'
        skip = self.skip_reason(name)
        if skip:
            return False, f'not delivering to {name} now: {skip}'

        bundle, digest = self.build_bundle(name)
        if not bundle:
            # the node applies no profiles at all. nothing to deliver, and nothing on the
            # node to reclaim that a previous delivery did not already handle
            Database().update('node', Helper().make_rows({'profiles_digest': ''}),
                              [{"column": "id", "value": node[0]['nodeid']}])
            return True, 'no profiles apply to this node'
        try:
            plugin = Helper().plugin_load(self.delivery_plugins, 'profile/delivery',
                                          [node[0]['nodename'], node[0]['groupname']])
            status, message = plugin().deliver(node=node[0]['nodename'],
                                               hostname=node[0]['hostname'] or node[0]['nodename'],
                                               bundle=bundle, timeout=DEFAULT_TIMEOUT)
        finally:
            shutil.rmtree(bundle, ignore_errors=True)

        if not status:
            return False, message
        if message != digest:
            # the node applied something other than what we sent it. recording it would
            # claim a state we cannot account for
            self.logger.error(f"{name} reports digest {message} but was sent {digest}")
            return False, f'{name} reported an unexpected digest'
        Database().update('node', Helper().make_rows({'profiles_digest': digest}),
                          [{"column": "id", "value": node[0]['nodeid']}])
        return True, digest


    def sync_child(self, pipeline, t=0):
        """
        One node per call; the mother decides how many of these run at once.
        """
        run = 1
        while run:
            run = 0
            item = pipeline.get_node()
            if not item:
                # more workers than nodes left. not an error, and it must not raise:
                # a child that dies inside an executor takes its exception with it
                continue
            nodename, _ = item
            try:
                status, message = self.deliver_node(nodename)
            except Exception as exp:
                status, message = False, f'{exp}'
                self.logger.error(f"delivering profiles to {nodename}: {exp}")
            pipeline.add_message({nodename: f"{status}={message}"})


    def sync_mother(self, event):
        """
        Drains the profile queue in parallel batches. Runs on the master only: two
        controllers delivering to the same node would race each other's applier.
        """
        self.logger.info("Starting profile sync thread")
        ha_object = HA()
        while True:
            try:
                if (not ha_object.get_hastate()) or ha_object.get_role():
                    pipeline = Helper().Pipeline()
                    claimed = []
                    while next_id := Queue().next_task_in_queue('profile'):
                        task = Database().get_record(table='queue', where=f'id = "{next_id}"')
                        if task and task[0]['task'] == 'sync_profiles' and task[0]['param']:
                            pipeline.add_nodes({task[0]['param']: 'sync_profiles'})
                        claimed.append(next_id)
                        Queue().remove_task_from_queue(next_id)
                    if pipeline.has_nodes():
                        self.deliver_batches(pipeline)
            except Exception as exp:
                self.logger.error(f"profile sync thread encountered problem: {exp}")
            if event.is_set():
                return
            sleep(5)


    def deliver_batches(self, pipeline):
        """
        The batch loop, as the osimage push and the power control paths run it: a pool of
        children pulling from one pipeline, results collected per pass.
        """
        batch, delay = self.batch_settings()
        while pipeline.has_nodes():
            with concurrent.futures.ThreadPoolExecutor(max_workers=batch) as executor:
                _ = [executor.submit(self.sync_child, pipeline, t) for t in range(1, batch + 1)]
            sleep(0.1)
            results = pipeline.get_messages()
            for key in list(results):
                status, message, *_ = (results[key].split('=', 1) + [None])
                if status == 'True':
                    self.logger.info(f"profiles delivered to {key}: {message}")
                else:
                    # a failure leaves the node's digest untouched, so it stays out of
                    # line and is picked up again. retried here so phase one does not
                    # depend on a sweep that does not exist yet
                    self.logger.warning(f"delivering profiles to {key} failed: {message}")
                    Queue().add_task_to_queue(task='sync_profiles', param=key,
                                              subsystem='profile', when=RETRY_DELAY)
                pipeline.del_message(key)
            if delay:
                sleep(delay)
