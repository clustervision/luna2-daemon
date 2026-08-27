
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This applies a stored BIOS configuration to a node.

It is only ever started by somebody asking for it. There is no sweep and no
reconciler, which removes most of what a queue subsystem usually needs: nothing
has to re-derive work nobody requested, and a failure is reported to the person
who asked rather than retried forever against a dark cluster.

The work is queued because it is long - a stage is a write, a reset and a wait
for POST, and a machine can need several - and it is reported through the same
status channel the osimage push and the power control paths use, so an operator
watches it arrive rather than waiting for a verdict at the end.

The reset is done over Redfish here rather than through the control path. We are
already holding a Redfish session with write credentials, and a machine that
stages BIOS settings over Redfish resets over Redfish; going through control
would drag in the ipmitool fallback and the bmcsetup credentials it needs, for
nothing.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from time import sleep
from utils.log import Log
from utils.database import Database
from utils.queue import Queue
from utils.status import Status
from utils.ha import HA
from utils.bios import Bios as BiosPlanner
from utils.redfish import CONFIGURE_COMPONENTS

# The reset that gets a machine to consume its staged settings. GracefulRestart
# is asked for first because the node may be running an operating system and
# there is no reason to pull the rug out from under it; ForceRestart is what we
# fall back to when the board does not offer it.
RESET_ORDER = ('GracefulRestart', 'ForceRestart', 'PowerCycle')

# How long to wait for a machine to come back and report where it is. Antoine's
# number: a node is back within fifteen minutes or something is wrong. It is a
# bound on one stage, not on the whole apply.
POST_DEADLINE = 900
POST_INTERVAL = 15

# What BootProgress calls far enough through POST for the BIOS to have consumed
# its settings object. Anything at or after hardware initialisation means the
# firmware has run; we do not need the operating system to be up.
POST_DONE = ('SystemHardwareInitializationComplete', 'SetupEntered',
             'OSBootStarted', 'OSRunning')


class BiosPush():
    """
    This class applies a stored BIOS configuration to a node, one stage at a time.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        self.planner = BiosPlanner()


    def report(self, request_id=None, message=None, status=200):
        """
        One line to whoever is watching. The osimage push and the power control
        paths use this channel, so the CLI already knows how to stream it.
        """
        if request_id:
            Status().add_message(request_id=request_id, username_initiator='luna',
                                 message=message, status=status)
        self.logger.info(message)


    def bios_resource(self, redfish=None):
        """
        This method reads a machine's Bios resource, and returns
        (True, path, data) or (False, reason, None).
        """
        status, path, system = redfish.system()
        if not status:
            return False, path, None
        bios_path = (system or {}).get('Bios', {}).get('@odata.id')
        if not bios_path:
            return False, 'this machine exposes no Bios resource', None
        status, bios = redfish.get(path=bios_path)
        if not status:
            return False, bios, None
        return True, bios_path, bios


    def settings_path(self, bios=None, bios_path=None):
        """
        Where a staged payload is written. The Bios resource names it, and a
        machine that does not is one we must not guess at: writing to the Bios
        resource itself is how a settings object gets bypassed on some boards and
        refused on others.
        """
        target = ((bios or {}).get('@Redfish.Settings') or {}).get('SettingsObject', {})
        return target.get('@odata.id') or None


    def allowable(self, actions=None, redfish=None, parameter='ResetType'):
        """
        This method returns the values a board says an action parameter accepts.

        There are two ways to publish them and only reading one is the same as
        not asking. The inline annotation is the older form and the one everybody
        reads; a board that offers only @Redfish.ActionInfo then looks exactly
        like a board that publishes nothing, and gets guessed at instead. Both
        real machines this was written against publish it only that way.

        The Redfish control plugin already answers this question correctly, and
        this follows it deliberately rather than inventing a second shape - down
        to reading through the cache, because the resource is per machine and a
        push resets once per stage.
        """
        actions = actions or {}
        inline = actions.get(f'{parameter}@Redfish.AllowableValues')
        if isinstance(inline, list) and inline:
            return [str(entry) for entry in inline]
        path = actions.get('@Redfish.ActionInfo')
        if not path or redfish is None:
            return []
        status, info = redfish.get(path=path, cache=True)
        if not status or not isinstance(info, dict):
            return []
        for entry in info.get('Parameters') or []:
            if entry.get('Name') == parameter:
                values = entry.get('AllowableValues')
                if isinstance(values, list) and values:
                    return [str(value) for value in values]
        return []


    def reset_type(self, system=None, redfish=None):
        """
        This method picks a reset the board says it accepts.

        Asked rather than assumed: the allowable values are published, and a
        board that is sent a type it does not offer answers 400 and stays exactly
        where it was - which reads as a failed apply rather than a failed reset.

        Returns (wanted, target, allowed). A board that publishes a list carrying
        nothing we can use answers None for wanted, and that is a different thing
        from publishing no list at all - the first is the machine telling us it
        cannot do what we need, the second is us guessing. The caller has to be
        able to tell them apart, so both come back.
        """
        actions = (system or {}).get('Actions', {}).get('#ComputerSystem.Reset', {})
        target = actions.get('target')
        if not target:
            return None, None, []
        allowed = self.allowable(actions=actions, redfish=redfish)
        for wanted in RESET_ORDER:
            if wanted in allowed:
                return wanted, target, allowed
        if allowed:
            return None, target, allowed
        # a board that publishes no list at all still has the action; ForceRestart
        # is the one every implementation carries. It is still a guess, so it is
        # logged as one rather than made quietly.
        self.logger.warning(
            'this machine publishes no allowable reset types, inline or by '
            'action info; falling back to ForceRestart'
        )
        return 'ForceRestart', target, []


    def reset(self, redfish=None):
        """
        This method resets a machine so it consumes what was staged.
        """
        status, _, system = redfish.system()
        if not status:
            return False, 'cannot read the system resource to reset it'
        wanted, target, allowed = self.reset_type(system=system, redfish=redfish)
        if not target:
            return False, 'this machine publishes no reset action'
        if not wanted:
            return False, (f'this machine offers no reset that applies staged '
                           f'settings; it accepts {sorted(allowed)}')
        status, code, data = redfish.call(method='POST', path=target,
                                          payload={'ResetType': wanted})
        if not status:
            return False, f'reset ({wanted}) refused: {data}'
        return True, wanted


    def boot_progress(self, redfish=None):
        """
        How far through POST a machine is, as it reports it, or None.
        """
        status, _, system = redfish.system()
        if not status:
            return None, None
        progress = (system or {}).get('BootProgress') or {}
        return progress.get('LastState'), str(system.get('PowerState') or '')


    def wait_for_post(self, redfish=None, deadline=POST_DEADLINE, interval=POST_INTERVAL):
        """
        This method waits for a machine to get far enough through POST that its
        BIOS has consumed the settings object.

        Bounded, and the bound is what makes an apply finish rather than hang: a
        machine that never comes back is a failure to report, not a worker to
        hold forever.

        A machine that does not publish BootProgress at all is not treated as
        broken - plenty do not. For those the wait falls back to the power state
        coming back on, which is weaker and is said to be weaker in the reason.
        """
        waited, seen_progress = 0, False
        while waited < deadline:
            sleep(interval)
            waited += interval
            state, power = self.boot_progress(redfish=redfish)
            if state:
                seen_progress = True
                if state in POST_DONE:
                    return True, f'reached {state} after {waited}s'
            elif power.lower() == 'on' and waited >= interval * 2:
                return True, (f'powered on after {waited}s; this machine does not '
                              'report BootProgress, so POST completion is assumed')
        if seen_progress:
            return False, f'did not finish POST within {deadline}s'
        return False, f'did not answer within {deadline}s'


    def apply_stage(self, redfish=None, stage=None, settings=None, request_id=None,
                    label=''):
        """
        This method applies one stage: write, reset, wait, read back, judge.

        It returns (outcome, reason) straight from the planner's verdict, so what
        counts as done, worth retrying and hopeless is decided in one place and
        the same way every time.
        """
        attempts = 0
        while True:
            payload = {'Attributes': stage,
                       '@Redfish.SettingsApplyTime': {'ApplyTime': 'OnReset'}}
            status, code, data = redfish.patch(path=settings, payload=payload)
            error = None if status else data
            if not error:
                self.report(request_id, f'{label}: staged {len(stage)} setting(s), resetting')
                status, reason = self.reset(redfish=redfish)
                if not status:
                    error = reason
            if not error:
                status, reason = self.wait_for_post(redfish=redfish)
                self.report(request_id, f'{label}: {reason}')
                if not status:
                    error = reason

            ok, path, bios = self.bios_resource(redfish=redfish)
            attributes = (bios or {}).get('Attributes') if ok else {}
            messages = ((bios or {}).get('@Redfish.Settings') or {}).get('Messages') if ok else []
            outcome, reason = self.planner.verdict(wanted=stage, attributes=attributes,
                                                   error=error, messages=messages,
                                                   attempts=attempts)
            if outcome != 'retry':
                return outcome, reason
            attempts += 1
            self.report(request_id, f'{label}: {reason}', status=200)


    def push_node(self, nodename=None, config=None, policy='warn', request_id=None):
        """
        This method applies one configuration to one node, all stages.

        The plan is recomputed from what the machine reports rather than
        remembered, so a stage that has already landed is not written again and a
        worker that died mid-apply resumes at the right place with no state to
        keep.
        """
        # imported here, not at the top: base/ imports utils/, so a utils module
        # importing base/ at module level closes the loop and the daemon will not
        # start. The layering is routes -> base -> utils, and this is the one
        # place this subsystem has to look back up it
        from base.nodeinventory import NodeInventory
        from utils.redfish import Redfish

        label = nodename
        # writing BIOS attributes and resetting the machine are both
        # ConfigureComponents, which an Operator carries. Asking for more would use
        # the strongest account a site configured, for work that never needed it
        status, access = NodeInventory().bmc_for(name=nodename,
                                                 needs=CONFIGURE_COMPONENTS)
        if not status:
            return False, access
        redfish = Redfish(device=access['device'], username=access['username'],
                          password=access['password'], scheme=access['scheme'],
                          port=access['port'], verify=access['verify'])

        status, path, bios = self.bios_resource(redfish=redfish)
        if not status:
            return False, f'{label}: {path}'
        settings = self.settings_path(bios=bios, bios_path=path)
        if not settings:
            return False, (f'{label}: this machine publishes no settings object, so '
                           'a staged write has nowhere to go')

        _, _, system = redfish.system()
        target = {'manufacturer': (system or {}).get('Manufacturer'),
                  'model': (system or {}).get('Model'),
                  'biosversion': (system or {}).get('BiosVersion')}
        allowed, difference = self.planner.compatible(config=config, target=target,
                                                      policy=policy)
        if not allowed:
            return False, f'{label}: {difference}'
        if difference:
            self.report(request_id, f'{label}: WARNING {difference}', status=200)

        status, registry = self.registry_for(redfish=redfish, bios=bios)
        if not status:
            return False, f'{label}: {registry}'
        wanted, _ = self.planner.portable(registry=registry,
                                          attributes=config.get('attributes') or {})
        status, stages = self.planner.plan(registry=registry, desired=wanted,
                                           current=bios.get('Attributes') or {})
        if not status:
            return False, f'{label}: {stages}'
        if not stages:
            return True, f'{label}: already as asked, nothing to apply'

        self.report(request_id, f'{label}: {len(stages)} stage(s), '
                                f'{sum(len(s) for s in stages)} setting(s) to apply')
        for number, stage in enumerate(stages, start=1):
            step = f'{label} stage {number}/{len(stages)}'
            outcome, reason = self.apply_stage(redfish=redfish, stage=stage,
                                               settings=settings, request_id=request_id,
                                               label=step)
            if outcome != 'done':
                # stop at the first stage that will not land. The stages after it
                # were planned on the assumption this one applied, so writing them
                # over a prerequisite that is not there is how a refusal becomes a
                # machine in a state nobody planned
                return False, f'{step}: {reason}'
            self.report(request_id, f'{step}: applied')
        return True, f'{label}: {len(stages)} stage(s) applied'


    def registry_for(self, redfish=None, bios=None):
        """
        The machine's attribute registry, resolved the same way a grab resolves
        it. Kept here rather than reached for in base/ so this module does not
        import a base class to read one document.
        """
        wanted = (bios or {}).get('AttributeRegistry')
        if not wanted:
            return False, 'this machine names no BIOS attribute registry'
        status, collection = redfish.get(path='/redfish/v1/Registries', cache=True)
        if not status:
            return False, f'registry collection unreadable: {collection}'
        for member in collection.get('Members') or []:
            path = member.get('@odata.id')
            if not path:
                continue
            status, entry = redfish.get(path=path, cache=True)
            if not status or entry.get('Registry') != wanted:
                continue
            for location in entry.get('Location') or []:
                uri = location.get('Uri')
                if not uri:
                    continue
                status, registry = redfish.get(path=uri)
                if status:
                    return True, registry
            return False, f'registry {wanted} lists no readable location'
        return False, f'registry {wanted} is not published by this machine'


    def push_mother(self, event):
        """
        This method drains the BIOS push queue. Master only: two controllers
        applying to the same machine would fight over its settings object.

        There is no reconcile sweep here, and that is the design rather than an
        omission - see the module docstring. The loop only ever runs what
        somebody asked for.
        """
        self.logger.info('Starting BIOS push thread')
        ha_object = HA()
        while True:
            try:
                if (not ha_object.get_hastate()) or ha_object.get_role():
                    self.reclaim_abandoned()
                    while next_id := Queue().next_task_in_queue('bios', status='queued'):
                        task = Database().get_record(table='queue', where=f'id = "{next_id}"')
                        if not task:
                            continue
                        # marked, not removed: a task removed at claim time is lost
                        # if the daemon stops mid-apply, and the node is then left
                        # part-configured with nothing queued to finish it
                        Queue().update_task_status_in_queue(next_id, 'in progress')
                        self.run_task(task[0])
                        Queue().remove_task_from_queue(next_id)
                else:
                    self.drop_queued()
            except Exception as exp:
                self.logger.error(f'BIOS push thread encountered problem: {exp}')
            if event.is_set():
                return
            sleep(5)


    def run_task(self, task=None):
        """
        One queued push. The parameters travel as node:config:policy, and every
        one of them is resolved now rather than carried: a rename between queueing
        and running would otherwise send this after something that no longer
        answers to the name.
        """
        request_id = task.get('request_id')
        nodename, configname, policy, *_ = (str(task.get('param') or '').split(':')
                                            + [None] + [None])
        record = Database().get_record(table='biosconfig', where=f'name = "{configname}"')
        if not record:
            self.report(request_id, f'{nodename}: BIOS configuration {configname} '
                                    'no longer exists', status=404)
            return
        from base.bios import Bios
        config = {'attributes': Bios().stored_attributes(record[0]),
                  'manufacturer': record[0]['manufacturer'],
                  'model': record[0]['model'],
                  'biosversion': record[0]['biosversion']}
        try:
            status, message = self.push_node(nodename=nodename, config=config,
                                             policy=policy or 'warn',
                                             request_id=request_id)
        except Exception as exp:
            status, message = False, f'{nodename}: {exp}'
        if status:
            # what the machine holds now, recorded so that weeks later somebody can
            # ask what is running which configuration without waking the cluster.
            # Only on success: a half-applied push has not reached the configuration,
            # and recording it as though it had is the lie the status view exists to
            # avoid telling
            self.record_applied(nodename=nodename, configname=configname)
        self.report(request_id, message, status=200 if status else 500)


    def record_applied(self, nodename=None, configname=None):
        """
        This method records the configuration a node now holds, and the digest it
        held when it did.

        The digest is read back from the machine rather than computed from what we
        sent: what we sent is what we asked for, and the whole reason this feature
        has stages is that the two are not the same thing until the board says so.
        """
        # same import note as push_node: base/ imports utils/, so this looks back
        # up the layering here rather than at module level
        from base.bios import Bios
        from base.nodeinventory import NodeInventory
        from utils.journal import Journal
        from utils.redfish import Redfish

        status, access = NodeInventory().bmc_for(name=nodename)
        if not status:
            return
        redfish = Redfish(device=access['device'], username=access['username'],
                          password=access['password'], scheme=access['scheme'],
                          port=access['port'], verify=access['verify'])
        status, _, system = redfish.system()
        if not status:
            return
        digest = NodeInventory().bios_digest(redfish=redfish, system=system)
        if not digest:
            return
        # both halves, in this order, exactly as a mutating route does it.
        # add_request queues the change for the PEER and does not apply it here, so
        # the local write is a separate call - and it is conditional, because a
        # controller that is not in sync must not write what it cannot replicate.
        # Getting this wrong is invisible on a single controller, where add_request
        # answers 'Not in H/A mode' and the local call does all the work
        payload = {'config': configname, 'digest': digest}
        status, _ = Journal().add_request(function='Bios.record_match',
                                          object=nodename, payload=payload)
        if status is True:
            Bios().record_match(name=nodename, payload=payload)


    def reclaim_abandoned(self):
        """
        A push the daemon was in the middle of when it stopped. Nothing else will
        pick it up, and the node it names is part-configured with no record of it.
        """
        stale = Database().get_record(table='queue',
                                      where="subsystem='bios' AND status='in progress' "
                                            "AND created<datetime('now','-60 minute')")
        for task in stale or []:
            self.logger.warning(f"BIOS push task {task['id']} for {task['param']} was "
                                'left in progress; queueing it again')
            Queue().remove_task_from_queue(task['id'])
            Queue().add_task_to_queue(task='push_bios', param=task['param'],
                                      subsystem='bios', request_id=task['request_id'],
                                      force=True)


    def drop_queued(self):
        """
        BIOS work queued on a controller that must not act on it. The journal
        replays the request that queues this, so tasks land on a secondary too;
        left alone they are never claimed, never reaped and never expire.
        """
        stale = Database().get_record(table='queue', where="subsystem='bios'")
        for task in stale or []:
            Queue().remove_task_from_queue(task['id'])
        if stale:
            self.logger.debug(f'dropped {len(stale)} BIOS push task(s) queued on a '
                              'controller that is not the master')
