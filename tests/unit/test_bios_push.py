#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-143: applying a stored BIOS configuration to a node.

The machine here is a fake, and it is a fake that behaves like the real thing in
the one way that matters: *a write does not take effect*. It goes into a settings
object and is consumed on the next reset. That is what makes a staged apply a
loop rather than a call, and a fake that applied writes immediately would let
every test pass while proving nothing.

It can also be told to refuse an attribute until another one has landed, which is
the whole reason stages exist, and to accept a payload and quietly drop part of
it - the failure nobody predicts and the one the bounded retry is for.

Nothing here touches a BMC, so the awkward paths are testable: a machine that
publishes no settings object, one that never finishes POST, one that reports no
BootProgress at all.
"""

import pytest

from utils.bios_push import BiosPush, POST_DONE
from utils.bios import MAX_ATTEMPTS
from utils.database import Database
from utils.helper import Helper


REGISTRY = {'RegistryEntries': {
    'Attributes': [
        {'AttributeName': 'BootMode', 'Type': 'Enumeration'},
        {'AttributeName': 'SriovGlobalEnable', 'Type': 'Enumeration'},
        {'AttributeName': 'ProcVirtualization', 'Type': 'Enumeration'},
    ],
    # SriovGlobalEnable cannot be written while BootMode is Bios. This is the
    # cascade the planner derives its stages from, and the reason one payload is
    # not enough on the machines that need this feature at all.
    'Dependencies': [{
        'DependencyFor': 'SriovGlobalEnable',
        'Type': 'Map',
        'Dependency': {
            'MapFromAttribute': 'BootMode', 'MapFromProperty': 'CurrentValue',
            'MapFromCondition': 'EQU', 'MapFromValue': 'Bios',
            'MapToAttribute': 'SriovGlobalEnable', 'MapToProperty': 'ReadOnly',
            'MapToValue': True,
            'MapFrom': [{'MapFromAttribute': 'BootMode',
                         'MapFromProperty': 'CurrentValue',
                         'MapFromCondition': 'EQU', 'MapFromValue': 'Bios'}],
        }}]}}


class FakeBmc():
    """
    A machine that stages writes and applies them on reset, as Redfish does.

    drop      attribute names to silently discard on apply - accepted, never applied
    refuse    answer the PATCH itself with an error
    messages  what the settings object reports back
    progress  what BootProgress says once it is up; None means it publishes none
    """

    def __init__(self, attributes=None, drop=(), refuse=None, messages=None,
                 progress='OSRunning', settings_object=True, power='On'):
        self.attributes = dict(attributes or {})
        self.staged = {}
        self.drop = set(drop)
        self.refuse = refuse
        self.messages = messages or []
        self.progress = progress
        self.settings_object = settings_object
        self.power = power
        self.resets = 0
        self.patches = 0

    # --- the Redfish client surface the pusher uses --------------------------

    def forget(self, path=None):
        """The real client caches; a poller has to be able to drop that."""
        return True

    def system(self):
        data = {
            'Manufacturer': 'Contoso', 'Model': 'PowerThing R750',
            'BiosVersion': '2.15.1', 'PowerState': self.power,
            'Bios': {'@odata.id': '/redfish/v1/Systems/1/Bios'},
            'Actions': {'#ComputerSystem.Reset': {
                'target': '/redfish/v1/Systems/1/Actions/ComputerSystem.Reset',
                'ResetType@Redfish.AllowableValues': ['On', 'ForceOff',
                                                      'GracefulRestart', 'ForceRestart'],
            }},
        }
        if self.progress:
            data['BootProgress'] = {'LastState': self.progress}
        return True, '/redfish/v1/Systems/1', data

    def get(self, path=None, cache=False):
        if path == '/redfish/v1/Systems/1/Bios':
            bios = {'Attributes': dict(self.attributes),
                    'AttributeRegistry': 'BiosAttributeRegistry.v1_0_0'}
            if self.settings_object:
                bios['@Redfish.Settings'] = {
                    'SettingsObject': {'@odata.id': '/redfish/v1/Systems/1/Bios/Settings'},
                    'Messages': list(self.messages)}
            return True, bios
        if path == '/redfish/v1/Registries':
            return True, {'Members': [{'@odata.id': '/redfish/v1/Registries/Bios'}]}
        if path == '/redfish/v1/Registries/Bios':
            return True, {'Registry': 'BiosAttributeRegistry.v1_0_0',
                          'Location': [{'Uri': '/registries/bios.json'}]}
        if path == '/registries/bios.json':
            return True, REGISTRY
        return False, f'{path} not found'

    def patch(self, path=None, payload=None):
        """(status, data) - the arity utils/redfish.py actually returns.

        It used to answer with three values, and the executor unpacked three, so
        the two agreed with each other and with nothing else. Every real push
        raised ValueError on its first stage while the suite stayed green: a fake
        that encodes the wrong contract tests the fake.
        """
        self.patches += 1
        if self.refuse:
            return False, self.refuse
        # staged, NOT applied - this is the property the whole feature turns on
        self.staged.update(payload.get('Attributes') or {})
        return True, {}

    def call(self, method='GET', path=None, payload=None, headers=None):
        if 'ComputerSystem.Reset' in str(path):
            self.resets += 1
            for name, value in self.staged.items():
                if name not in self.drop:
                    self.attributes[name] = value
            self.staged = {}
            return True, 204, {}
        return False, 404, 'no such action'


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """The pusher sleeps between POST polls; nothing here needs real time."""
    monkeypatch.setattr('utils.bios_push.sleep', lambda _: None)


# --- asking the board rather than assuming ----------------------------------

def test_the_reset_type_is_one_the_board_says_it_accepts():
    _, _, system = FakeBmc().system()
    wanted, target, _ = BiosPush().reset_type(system=system)
    assert wanted == 'GracefulRestart', (
        'a node may be running an operating system; there is no reason to pull '
        'the rug out when the board offers a graceful restart'
    )
    assert target.endswith('ComputerSystem.Reset')


def test_it_falls_back_when_the_board_does_not_offer_a_graceful_restart():
    _, _, system = FakeBmc().system()
    system['Actions']['#ComputerSystem.Reset']['ResetType@Redfish.AllowableValues'] = \
        ['On', 'ForceRestart']
    assert BiosPush().reset_type(system=system)[0] == 'ForceRestart'


def test_a_board_publishing_no_list_still_gets_reset():
    _, _, system = FakeBmc().system()
    del system['Actions']['#ComputerSystem.Reset']['ResetType@Redfish.AllowableValues']
    assert BiosPush().reset_type(system=system)[0] == 'ForceRestart'


def test_a_machine_with_no_settings_object_is_refused_not_guessed_at():
    """
    Writing to the Bios resource instead is how a settings object gets bypassed
    on some boards and refused on others. Neither is a guess worth making.
    """
    bmc = FakeBmc(settings_object=False)
    _, _, bios = BiosPush().bios_resource(redfish=bmc)
    assert BiosPush().settings_path(bios=bios) is None


# --- waiting for POST --------------------------------------------------------

@pytest.mark.parametrize('state', POST_DONE)
def test_any_state_at_or_past_hardware_init_counts_as_posted(state):
    """The firmware has run by then; we do not need the OS to be up."""
    status, reason = BiosPush().wait_for_post(redfish=FakeBmc(progress=state), interval=1)
    assert status is True and state in reason


def test_a_machine_that_never_finishes_post_is_a_failure_not_a_hang():
    status, reason = BiosPush().wait_for_post(redfish=FakeBmc(progress='PrimaryProcessorInitializationStarted'),
                                              deadline=30, interval=10)
    assert status is False
    assert 'did not finish POST within 30s' in reason


def test_a_machine_that_reports_no_bootprogress_falls_back_and_says_so():
    """
    Plenty do not publish it. Treating that as broken would refuse a working
    machine - but the weaker signal has to be described as weaker.
    """
    status, reason = BiosPush().wait_for_post(redfish=FakeBmc(progress=None, power='On'),
                                              interval=1)
    assert status is True
    assert 'does not report BootProgress' in reason


# --- the stage loop ----------------------------------------------------------

def test_a_stage_is_written_then_reset_then_read_back():
    """
    The shape of the whole feature: the write alone changes nothing, and the
    reset is what makes it true.
    """
    bmc = FakeBmc(attributes={'BootMode': 'Bios'})
    outcome, reason = BiosPush().apply_stage(redfish=bmc, stage={'BootMode': 'Uefi'},
                                             settings='/redfish/v1/Systems/1/Bios/Settings')
    assert (outcome, bmc.resets) == ('done', 1)
    assert bmc.attributes['BootMode'] == 'Uefi'


def test_a_refused_write_stops_at_once_without_resetting():
    """
    Retrying a refusal costs a reboot and earns the same refusal. Note the
    machine must not have been reset at all.
    """
    bmc = FakeBmc(attributes={'BootMode': 'Bios'}, refuse='value not supported')
    outcome, reason = BiosPush().apply_stage(redfish=bmc, stage={'BootMode': 'Uefi'},
                                             settings='/x')
    assert outcome == 'failed'
    assert 'value not supported' in reason
    assert bmc.resets == 0, 'a refused write must not reboot the machine'
    assert bmc.patches == 1, 'and must not be attempted again'


def test_accepted_and_silently_dropped_is_retried_then_given_up_on():
    """
    The failure nobody predicts: the PATCH succeeds, the machine reboots, and the
    attribute is simply not there. Bounded, and the bound is spent exactly once.
    """
    bmc = FakeBmc(attributes={'BootMode': 'Bios'}, drop={'BootMode'})
    outcome, reason = BiosPush().apply_stage(redfish=bmc, stage={'BootMode': 'Uefi'},
                                             settings='/x')
    assert outcome == 'failed'
    assert 'never took' in reason and 'no error from the machine' in reason
    assert bmc.resets == MAX_ATTEMPTS + 1, (
        'one attempt plus the retries, and not one reboot more'
    )


def test_a_rejection_in_the_settings_object_stops_after_the_first_reset():
    """
    The machine took the write, rebooted, and then said no. That is a refusal,
    not a silent drop - so it must not burn the retry budget.
    """
    bmc = FakeBmc(attributes={'BootMode': 'Bios'}, drop={'BootMode'},
                  messages=[{'Message': 'BootMode is locked', 'Severity': 'Critical'}])
    outcome, reason = BiosPush().apply_stage(redfish=bmc, stage={'BootMode': 'Uefi'},
                                             settings='/x')
    assert outcome == 'failed'
    assert 'BootMode is locked' in reason
    assert bmc.resets == 1


# --- a whole push ------------------------------------------------------------

@pytest.fixture
def node(monkeypatch):
    """A node whose BMC is whatever the test hands over."""
    def install(bmc):
        monkeypatch.setattr('base.nodeinventory.NodeInventory.bmc_for',
                            lambda self, name=None, needs=None: (True, {
                                'device': '10.0.0.1', 'username': 'admin', 'password': 'x',
                                'scheme': 'https', 'port': None, 'verify': False}))
        monkeypatch.setattr('utils.redfish.Redfish', lambda **kwargs: bmc)
        return bmc
    return install


CONFIG = {'attributes': {'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled'},
          'manufacturer': 'Contoso', 'model': 'PowerThing R750', 'biosversion': '2.15.1'}


def test_a_dependent_attribute_needs_a_second_stage_and_a_second_reboot(node):
    """
    The reason this feature exists. SriovGlobalEnable is read-only while BootMode
    is Bios, so one payload cannot do it - the machine has to go through a reboot
    in between, and the plan is derived from what the registry says rather than
    from a recipe we maintain.
    """
    bmc = node(FakeBmc(attributes={'BootMode': 'Bios', 'SriovGlobalEnable': 'Disabled'}))
    status, message = BiosPush().push_node(nodename='node001', config=CONFIG)
    assert status is True, message
    assert '2 stage(s) applied' in message
    assert bmc.resets == 2
    assert bmc.attributes['BootMode'] == 'Uefi'
    assert bmc.attributes['SriovGlobalEnable'] == 'Enabled'


def test_a_machine_already_as_asked_is_not_rebooted_at_all(node):
    """
    A stage that changes nothing still costs a reboot, so there must not be one.
    """
    bmc = node(FakeBmc(attributes={'BootMode': 'Uefi', 'SriovGlobalEnable': 'Enabled'}))
    status, message = BiosPush().push_node(nodename='node001', config=CONFIG)
    assert status is True
    assert 'already as asked' in message
    assert bmc.resets == 0 and bmc.patches == 0


def test_a_push_stops_at_the_first_stage_that_will_not_land(node):
    """
    The stages after it were planned assuming this one applied. Carrying on would
    write over a prerequisite that is not there - the same reasoning that makes
    the replication journal halt rather than skip.
    """
    bmc = node(FakeBmc(attributes={'BootMode': 'Bios', 'SriovGlobalEnable': 'Disabled'},
                       drop={'BootMode'}))
    status, message = BiosPush().push_node(nodename='node001', config=CONFIG)
    assert status is False
    assert 'stage 1/2' in message
    assert bmc.attributes['SriovGlobalEnable'] == 'Disabled', (
        'the second stage must not have been attempted'
    )


def test_a_different_board_is_refused_before_anything_is_written(node):
    bmc = node(FakeBmc(attributes={'BootMode': 'Bios'}))
    config = dict(CONFIG, model='PowerThing R650')
    status, message = BiosPush().push_node(nodename='node001', config=config)
    assert status is False
    assert 'model differs' in message
    assert bmc.patches == 0 and bmc.resets == 0


def test_a_bios_version_difference_is_refused_under_strict_and_allowed_under_warn(node):
    bmc = node(FakeBmc(attributes={'BootMode': 'Bios', 'SriovGlobalEnable': 'Disabled'}))
    config = dict(CONFIG, biosversion='2.09.0')
    status, message = BiosPush().push_node(nodename='node001', config=config, policy='strict')
    assert status is False and 'BIOS version differs' in message
    assert bmc.patches == 0

    bmc = node(FakeBmc(attributes={'BootMode': 'Bios', 'SriovGlobalEnable': 'Disabled'}))
    status, message = BiosPush().push_node(nodename='node001', config=config, policy='warn')
    assert status is True, message


def test_a_machine_with_no_settings_object_is_refused_before_writing(node):
    bmc = node(FakeBmc(attributes={'BootMode': 'Bios'}, settings_object=False))
    status, message = BiosPush().push_node(nodename='node001', config=CONFIG)
    assert status is False
    assert 'no settings object' in message
    assert bmc.patches == 0


def test_an_unreachable_bmc_is_reported_not_raised(node, monkeypatch):
    monkeypatch.setattr('base.nodeinventory.NodeInventory.bmc_for',
                        lambda self, name=None, needs=None: (False, 'node001 has no BMC address configured'))
    status, message = BiosPush().push_node(nodename='node001', config=CONFIG)
    assert status is False and 'no BMC address' in message


# --- queueing ----------------------------------------------------------------

def test_a_group_push_queues_one_task_per_node(sqlite_db):
    """
    The group is expanded at the edge rather than carried into the queue, so a
    node added afterwards is not silently included in something nobody saw.
    """
    from base.bios import Bios
    Database().insert('group', Helper().make_rows({'name': 'compute'}))
    for name in ('node001', 'node002', 'node003'):
        Database().insert('node', Helper().make_rows({'name': name, 'groupid': 1}))
    Database().insert('biosconfig', Helper().make_rows(
        {'name': 'golden', 'attributes': Bios().encode('{"BootMode": "Uefi"}')}))

    returned = Bios().push_bios(object_type='group', name='compute',
                                request_data={'config': {'group': {'compute': {
                                    'biosconfig': 'golden'}}}})
    assert returned[0] is True, returned[1]
    tasks = Database().get_record(table='queue', where="subsystem='bios'")
    assert len(tasks) == 3
    assert sorted(t['param'] for t in tasks) == [
        'node001:golden:warn', 'node002:golden:warn', 'node003:golden:warn']
    assert len({t['request_id'] for t in tasks}) == 1, 'one request to watch, not three'


def test_a_configuration_with_no_settings_is_refused(sqlite_db):
    """Queueing a reboot to apply nothing is worse than saying no."""
    from base.bios import Bios
    Database().insert('node', Helper().make_rows({'name': 'node001'}))
    Database().insert('biosconfig', Helper().make_rows({'name': 'empty'}))
    status, response = Bios().push_bios(object_type='node', name='node001',
                                        request_data={'config': {'node': {'node001': {
                                            'biosconfig': 'empty'}}}})[:2]
    assert status is False and 'carries no settings' in response


def test_asking_twice_queues_twice(sqlite_db):
    """
    The queue folds an identical task inside fifteen minutes, and here that is
    wrong: the operator asked again, and the machine may well have moved on.
    """
    from base.bios import Bios
    Database().insert('node', Helper().make_rows({'name': 'node001'}))
    Database().insert('biosconfig', Helper().make_rows(
        {'name': 'golden', 'attributes': Bios().encode('{"BootMode": "Uefi"}')}))
    body = {'config': {'node': {'node001': {'biosconfig': 'golden'}}}}
    Bios().push_bios(object_type='node', name='node001', request_data=body)
    Bios().push_bios(object_type='node', name='node001', request_data=body)
    assert len(Database().get_record(table='queue', where="subsystem='bios'")) == 2


def test_bios_work_on_a_non_master_is_dropped(sqlite_db):
    """
    The journal replays the request that queues this, so tasks land on a
    secondary too. Left alone they are never claimed, never reaped and never
    expire - the leak the queue rules exist to prevent.
    """
    from base.bios import Bios
    Database().insert('node', Helper().make_rows({'name': 'node001'}))
    Database().insert('biosconfig', Helper().make_rows(
        {'name': 'golden', 'attributes': Bios().encode('{"BootMode": "Uefi"}')}))
    Bios().push_bios(object_type='node', name='node001',
                     request_data={'config': {'node': {'node001': {'biosconfig': 'golden'}}}})
    assert Database().get_record(table='queue', where="subsystem='bios'")
    BiosPush().drop_queued()
    assert not Database().get_record(table='queue', where="subsystem='bios'")


def test_a_group_that_does_not_exist_is_distinguished_from_one_with_no_nodes(sqlite_db):
    """
    'group' is a reserved SQL word, so a where clause naming it is a syntax
    error - and this daemon logs that error and swallows it, so the caller sees
    an empty result. Empty and broken look identical, which is how a real group
    got reported as having no nodes.

    Asserting the two answers differ is what pins it: a query that cannot run
    returns nothing, and nothing cannot say which of these it means.
    """
    from base.bios import Bios
    Database().insert('group', Helper().make_rows({'name': 'empty-group'}))
    Database().insert('biosconfig', Helper().make_rows(
        {'name': 'golden', 'attributes': Bios().encode('{"BootMode": "Uefi"}')}))
    body = lambda g: {'config': {'group': {g: {'biosconfig': 'golden'}}}}

    status, response = Bios().push_bios(object_type='group', name='empty-group',
                                        request_data=body('empty-group'))[:2]
    assert status is False and response == 'group empty-group has no nodes'

    status, response = Bios().push_bios(object_type='group', name='no-such-group',
                                        request_data=body('no-such-group'))[:2]
    assert status is False and response == 'group no-such-group does not exist'


# --- the reset type, published only by action info ---------------------------

class ActionInfoBmc():
    """A board that publishes its allowable reset types the other way."""

    def __init__(self, allowed=('On', 'ForceRestart', 'GracefulShutdown', 'ForceOff')):
        self.allowed = list(allowed)
        self.reads = 0

    def get(self, path=None, cache=False):
        if path == '/redfish/v1/Systems/Self/ResetActionInfo':
            self.reads += 1
            return True, {'Parameters': [
                {'Name': 'SomethingElse', 'AllowableValues': ['nonsense']},
                {'Name': 'ResetType', 'AllowableValues': self.allowed}]}
        return False, f'{path} not found'


def system_publishing_only_action_info():
    """Verbatim shape of the real board: a target and an action info, no list."""
    return {'Actions': {'#ComputerSystem.Reset': {
        '@Redfish.ActionInfo': '/redfish/v1/Systems/Self/ResetActionInfo',
        'target': '/redfish/v1/Systems/Self/Actions/ComputerSystem.Reset'}}}


def test_the_allowable_reset_types_are_read_from_the_action_info():
    bmc = ActionInfoBmc()
    wanted, target, allowed = BiosPush().reset_type(
        system=system_publishing_only_action_info(), redfish=bmc)
    assert allowed == ['On', 'ForceRestart', 'GracefulShutdown', 'ForceOff'], (
        'read from the action info, and from the ResetType parameter rather '
        'than whichever parameter happens to come first'
    )
    assert wanted == 'ForceRestart', 'this board offers no GracefulRestart'
    assert target.endswith('ComputerSystem.Reset')


def test_a_board_offering_no_usable_reset_is_told_apart_from_one_that_is_silent():
    """
    The distinction the caller needs. A board that says On/GracefulShutdown/
    ForceOff has told us it cannot restart to apply settings, and sending it
    ForceRestart earns a 400 that reads as a failed apply. A board that says
    nothing has told us nothing, and is worth the guess.
    """
    quiet = BiosPush().reset_type(system={'Actions': {'#ComputerSystem.Reset': {
        'target': '/redfish/v1/Systems/1/Actions/ComputerSystem.Reset'}}})
    assert quiet == ('ForceRestart', '/redfish/v1/Systems/1/Actions/ComputerSystem.Reset', [])

    bmc = ActionInfoBmc(allowed=['On', 'GracefulShutdown', 'ForceOff'])
    wanted, target, allowed = BiosPush().reset_type(
        system=system_publishing_only_action_info(), redfish=bmc)
    assert wanted is None, 'not a guess - the board has answered, and the answer is no'
    assert target and allowed == ['On', 'GracefulShutdown', 'ForceOff']


def test_the_inline_annotation_still_wins_where_a_board_publishes_one():
    """The older form is not dropped; a board serving both is not read twice."""
    bmc = ActionInfoBmc()
    system = system_publishing_only_action_info()
    system['Actions']['#ComputerSystem.Reset'][
        'ResetType@Redfish.AllowableValues'] = ['GracefulRestart', 'ForceRestart']
    wanted, _, _ = BiosPush().reset_type(system=system, redfish=bmc)
    assert wanted == 'GracefulRestart'
    assert bmc.reads == 0, 'no round trip when the board already told us inline'


def test_the_action_info_is_read_through_the_cache():
    """A push resets once per stage; the document does not change under us."""
    bmc = ActionInfoBmc()
    original = bmc.get

    def counting(path=None, cache=False):
        assert cache is True, 'a per-machine document read once per stage'
        return original(path=path, cache=cache)

    bmc.get = counting
    BiosPush().reset_type(system=system_publishing_only_action_info(), redfish=bmc)


def test_a_board_with_no_reset_action_at_all_is_still_refused():
    assert BiosPush().reset_type(system={'Actions': {}}) == (None, None, [])
