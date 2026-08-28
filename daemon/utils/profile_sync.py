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
from base.profile import Profile, OUTCOME_REF, RETRY_SECONDS

APPLIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'nodescripts', 'apply_profiles.py')
DEFAULT_BATCH = 20
DEFAULT_DELAY = 0
# generous on purpose: the applier may be waiting on a service that takes minutes to
# settle. Reachability is bounded by the transport's own connect and keepalive limits,
# so this does not need to be the thing that notices a dead node
DEFAULT_TIMEOUT = 900
RETRY_DELAY = f'{RETRY_SECONDS}s'
# where an install stops. anything else under install. is a step still in flight, and
# these two stay on the record long after the install finished
INSTALL_DONE = ('install.success', 'install.booted')
# the mother wakes every five seconds; this many passes puts a reconcile sweep roughly
# every five minutes, which is often enough for a node that has just come back and rare
# enough that it is never the thing doing the work
RECONCILE_PASSES = 60
# a persistently unreachable node warns on the first failure and then only every
# LOG_EVERY-th retry, so an offline node cannot fill the log with one line per cool-off
LOG_EVERY = 12
# how long to leave a node alone after a failed attempt. Measured on a live pair: with a
# fifteen second connect bound and twenty deliveries in flight, a thousand unreachable
# nodes take about twelve minutes to work through. Without a cool-off the sweep would
# queue them all again every five minutes, so the worker would never be idle and a
# legitimate delivery would wait behind a cluster that is simply switched off.
FAILURE_COOLOFF = 15


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
        Why we would not even try this node right now. The check is free and it avoids a
        pointless connection attempt - and, for a node that really is mid-install, avoids
        racing the installer over the very files we are delivering.

        'install.' as a prefix is NOT the test: an install ends at install.success and
        the node then reports install.booted, and those sit on the record for the rest of
        the node's life. Testing the prefix alone would exclude every successfully
        installed node in the cluster, permanently and quietly.
        """
        state = Database().get_record_join(['monitor.state as state'],
                                           ['monitor.tablerefid=node.id'],
                                           [f'node.name="{name}"', "monitor.tableref='node'"])
        if not state or not state[0]['state']:
            return None
        current = str(state[0]['state'])
        if current.startswith('install.') and current not in INSTALL_DONE:
            return f'it is installing ({current})'
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


    def deliver_node(self, nodeid=None):
        """
        Bring one node into line. Returns (status, message).

        Nothing here is done unless the node's digests differ, which is the whole reason
        a sweep over a large cluster is affordable: the decision costs one comparison and
        no connection.
        """
        # the node name is the target, as the osimage push uses it: there is no
        # separate hostname column on node
        node = Database().get_record_join(['node.id as nodeid', 'node.name as nodename',
                                           'node.profiles_digest as delivered',
                                           'group.name as groupname'],
                                          ['group.id=node.groupid'],
                                          [f'node.id="{nodeid}"'])
        if not node:
            return False, f'node {nodeid} is not available'
        # the name is read now, at delivery time, rather than carried from whenever the
        # task was queued: a rename in between would otherwise send us looking for a
        # node that no longer answers to it
        name = node[0]['nodename']
        desired = Profile().node_digest(name)
        if desired and desired == node[0]['delivered']:
            return True, 'already in line'
        stopped = Profile().given_up(nodeid)
        if stopped:
            # queued before we gave up, run after. None rather than False: it has not
            # failed here, we simply are not trying any more
            return None, (f'not delivering to {name}: {stopped} failed attempts in a row, '
                          'no longer retrying')
        skip = self.skip_reason(name)
        if skip:
            # None, not False: a node that is not ready has not failed, and recording it
            # as a failure sends somebody chasing a problem that does not exist. It stays
            # behind, which it is, and the sweep takes it when its state clears
            return None, f'not delivering to {name} now: {skip}'

        bundle, digest = self.build_bundle(name)
        if not bundle:
            return False, f'could not build a profile bundle for {name}'
        try:
            plugin = Helper().plugin_load(self.delivery_plugins, 'profile/delivery',
                                          [node[0]['nodename'], node[0]['groupname']])
            if not plugin:
                return False, ('no profile delivery plugin could be loaded; '
                               f'looked under {self.delivery_plugins}')
            status, message = plugin().deliver(node=node[0]['nodename'],
                                               hostname=node[0]['nodename'],
                                               bundle=bundle, timeout=DEFAULT_TIMEOUT)
        finally:
            shutil.rmtree(bundle, ignore_errors=True)

        if not status:
            return False, message
        # a plugin may append notes after the digest: the first line is the answer
        reported, _, notes = str(message).partition('\n')
        if reported != digest:
            # the node applied something other than what we sent it. recording it would
            # claim a state we cannot account for
            self.logger.error(f"{name} reports digest {reported} but was sent {digest}")
            return False, f'{name} reported an unexpected digest'
        Database().update('node', Helper().make_rows({'profiles_digest': digest}),
                          [{"column": "id", "value": node[0]['nodeid']}])
        if notes:
            self.logger.warning(f"{name} applied its profiles with warnings: {notes}")
        return True, notes.replace('\n', '; ') if notes else 'delivered'


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
            nodeid, _ = item
            try:
                status, message = self.deliver_node(nodeid)
            except Exception as exp:
                status, message = False, f'{exp}'
                self.logger.error(f"delivering profiles to node id {nodeid}: {exp}")
            pipeline.add_message({nodeid: f"{status}={message}"})


    def sync_mother(self, event):
        """
        Drains the profile queue in parallel batches. Runs on the master only: two
        controllers delivering to the same node would race each other's applier.
        """
        self.logger.info("Starting profile sync thread")
        ha_object = HA()
        sweep_counter = 0
        while True:
            try:
                if (not ha_object.get_hastate()) or ha_object.get_role():
                    # the reconcile sweep is deliberately infrequent: it exists to catch
                    # what the event-driven path missed, not to do the work
                    sweep_counter += 1
                    if sweep_counter >= RECONCILE_PASSES:
                        sweep_counter = 0
                        self.reconcile()
                    pipeline = Helper().Pipeline()
                    claimed = {}
                    while next_id := Queue().next_task_in_queue('profile', status='queued'):
                        task = Database().get_record(table='queue', where=f'id = "{next_id}"')
                        if task and task[0]['task'] == 'sync_profiles' and task[0]['param']:
                            pipeline.add_nodes({task[0]['param']: 'sync_profiles'})
                            claimed[task[0]['param']] = next_id
                        # marked, not removed: a task removed at claim time is lost if the
                        # daemon stops before the delivery finishes, and the node then sits
                        # out of line with nothing queued to bring it back
                        Queue().update_task_status_in_queue(next_id, 'in progress')
                    self.reclaim_abandoned()
                    if pipeline.has_nodes():
                        self.deliver_batches(pipeline, claimed)
                else:
                    # not the master: delivering from here would race the master's
                    # applier, so there is nothing to do - but the journal replays the
                    # requests that queue this work, so tasks land here anyway. Left
                    # alone they are never claimed, never reaped and never expire, so
                    # they are dropped: the master holds the same work, and whoever is
                    # master next re-derives it from the digests
                    self.drop_queued()
            except Exception as exp:
                self.logger.error(f"profile sync thread encountered problem: {exp}")
            if event.is_set():
                return
            sleep(5)


    def drop_queued(self):
        """
        Clear profile work queued on a controller that must not act on it.
        """
        stale = Database().get_record(table='queue',
                                      where="subsystem='profile' AND task='sync_profiles'")
        for task in stale or []:
            Queue().remove_task_from_queue(task['id'])
        if stale:
            self.logger.debug(f"dropped {len(stale)} profile task(s) queued on a "
                              "controller that is not the master")


    def nodes_behind(self):
        """
        Every node whose profiles are not what they should be. This is the whole of the
        reconciler's decision, and it costs one query plus a digest per node - no
        connection is made, so sweeping a large cluster is affordable.

        A node that has never been delivered to AND has no profiles assigned is not
        behind, it is uninvolved. Without that, a cluster where nobody uses profiles
        would have every node "differ" - an empty digest against no digest at all - and
        the sweep would ssh to all of them to deliver nothing.
        """
        behind = []
        for node in Database().get_record(table='node') or []:
            delivered = node['profiles_digest']
            assigned = Profile().merged_profiles(node['id'])
            if not delivered and not assigned:
                continue
            if Profile().node_digest(node['name']) == delivered:
                continue
            if self.skip_reason(node['name']):
                # it would be skipped at delivery anyway; queueing it here only churns
                continue
            if Profile().given_up(node['id']):
                # we have stopped chasing it. It stays out of line and stays visible as
                # such, but it no longer takes a worker's time every quarter of an hour
                continue
            recent = Database().get_record(
                table='monitor',
                where=f'tableref = "{OUTCOME_REF}" AND tablerefid = "{node["id"]}" '
                      f'AND state LIKE "failed%" '
                      f'AND updated > datetime("now","-{FAILURE_COOLOFF} minute")')
            if recent:
                # it failed a moment ago and nothing has changed since; trying again now
                # only spends the worker's time on a node that is still not there
                continue
            behind.append((node['id'], node['name']))
        return behind


    def reconcile(self):
        """
        Queue whatever has drifted. This is what makes a node that was unreachable
        converge on its own once it comes back, with no retry list to maintain: it is
        simply a node whose digests still differ, and it stays that way until it is
        delivered to. It is also what makes the queue's own sixty-minute window
        harmless, since anything that ages out of it is added again here.
        """
        behind = self.nodes_behind()
        if behind:
            names = [name for _, name in behind]
            self.logger.info(f"profiles out of line on {len(behind)} node(s): "
                             f"{', '.join(names[:10])}{' ...' if len(behind) > 10 else ''}")
            Profile().queue_nodes([nodeid for nodeid, _ in behind])
        return behind


    def record_outcome(self, nodeid=None, status=None, message=None):
        """
        What happened the last time we tried this node, so the status view can answer
        'did it work' without anyone reading a log. Kept under a reference of its own:
        the node's own monitor row carries its install state, and one would overwrite
        the other.
        """
        # the count rides along in the state, so how long this has been going on needs no
        # second row to be kept in step with this one
        state = 'delivered'
        if not status:
            state = f'failed {Profile().failed_attempts(nodeid) + 1}'
        row = [{"column": "tableref", "value": OUTCOME_REF},
               {"column": "tablerefid", "value": nodeid},
               {"column": "state", "value": state},
               {"column": "status", "value": str(message)[:2000]},
               {"column": "updated", "value": "NOW"}]
        Database().insert('monitor', row, replace=True)


    def reclaim_abandoned(self):
        """
        Tasks left 'in progress' by a daemon that stopped mid-delivery. Nothing else will
        ever pick them up, and the node they name is out of line with no record of it.
        """
        stale = Database().get_record(table='queue',
                                      where="subsystem='profile' AND status='in progress' "
                                            "AND created<datetime('now','-30 minute')")
        for task in stale or []:
            self.logger.warning(f"profile task {task['id']} for {task['param']} was left "
                                "in progress; queueing it again")
            Queue().remove_task_from_queue(task['id'])
            Queue().add_task_to_queue(task='sync_profiles', param=task['param'],
                                      subsystem='profile')


    def deliver_batches(self, pipeline, claimed=None):
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
                taskid = (claimed or {}).get(key)
                if taskid:
                    Queue().remove_task_from_queue(taskid)
                if status == 'None':
                    # deferred, not failed: nothing recorded, nothing re-queued
                    self.logger.info(message)
                    pipeline.del_message(key)
                    continue
                # for the operator's benefit the log names the node, resolved now
                node = Database().get_record(table='node', where=f'id = "{key}"')
                label = node[0]['name'] if node else f'node id {key}'
                if node:
                    # a node that has been deleted gets no outcome row: nothing will ever
                    # read it, and it would sit in the monitor table for the life of the
                    # cluster referring to something that no longer exists
                    self.record_outcome(key, status == 'True', message)
                if status == 'True':
                    self.logger.info(f"profiles delivered to {label}: {message}")
                elif not node:
                    # the node was removed while its delivery was queued. re-queueing
                    # would retry it forever against something that cannot come back
                    self.logger.info(f"node id {key} no longer exists; dropping its "
                                     "profile delivery")
                else:
                    # a failure leaves the node's digest untouched, so it stays out of
                    # line and the sweep picks it up again once its cool-off has passed.
                    # an unreachable node would otherwise warn every cool-off forever, so
                    # it is loud the first time and then only every LOG_EVERY-th retry;
                    # the full detail stays at debug in between.
                    attempts = Profile().failed_attempts(key)
                    detail = f"delivering profiles to {label} failed (attempt {attempts}): {message}"
                    if attempts <= 1 or attempts % LOG_EVERY == 0:
                        self.logger.warning(detail)
                    else:
                        self.logger.debug(detail)
                    Queue().add_task_to_queue(task='sync_profiles', param=key,
                                              subsystem='profile', when=RETRY_DELAY)
                pipeline.del_message(key)
            if delay:
                sleep(delay)
