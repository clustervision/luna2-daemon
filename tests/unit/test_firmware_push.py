
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
TRIX-1996a unit tests: what a board does with a firmware image.

The fake below is written to be able to LIE in the specific way a real board lies:
it can report a task as Completed and go on running the old version, which is what
an image landing in the inactive slot looks like from the outside. A fake that
changed the version whenever it accepted an image would agree with the code about
everything and prove none of it.

It resolves the update service with the client's own methods rather than its own,
so the discovery under test is the discovery that ships.
"""

class FakeBoard():
    """A Redfish service that answers from a path -> document map."""

    def __init__(self, resources=None):
        self.resources = dict(resources or {})
        self.posted = []

    def get(self, path=None, cache=False):
        if path in self.resources:
            return True, self.resources[path]
        return False, f'no such resource {path}'

    def service_root(self):
        return self.get('/redfish/v1/')

    def post(self, path=None, payload=None):
        self.posted.append({'path': path, 'payload': payload})
        return True, self.resources.get('__post__', {})

    # The real implementations over this fake's transport, so the singleton walk
    # and the failure wording under test are the ones that ship.
    from utils.redfish import Redfish
    singleton = Redfish.singleton
    update_service = Redfish.update_service
    allowable = Redfish.allowable
    parameter_names = Redfish.parameter_names
    reason = Redfish.reason
    del Redfish


def board(service=None, extra=None):
    """A board whose root points at an update service."""
    resources = {'/redfish/v1/': {'UpdateService': {'@odata.id': '/redfish/v1/UpdateService'}},
                 '/redfish/v1/UpdateService': service if service is not None else {}}
    resources.update(extra or {})
    return FakeBoard(resources=resources)


def test_a_service_that_is_enabled_will_take_work():
    from utils.firmware_push import FirmwarePush

    assert FirmwarePush().ready(redfish=board({'Status': {'State': 'Enabled'}})) == (True, None)


def test_a_service_that_is_not_enabled_is_come_back_rather_than_broken():
    """The AMI window: pushing into it is accepted and silently discarded."""
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().ready(redfish=board({'Status': {'State': 'Starting'}}))
    assert status is False
    assert 'Starting' in reason


def test_a_board_with_no_update_service_says_so():
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().ready(redfish=FakeBoard({'/redfish/v1/': {}}))
    assert status is False
    assert 'UpdateService' in reason


def test_simpleupdate_is_preferred_because_the_board_fetches_for_itself():
    from utils.firmware_push import FirmwarePush, SIMPLE

    service = {'MultipartHttpPushUri': '/redfish/v1/UpdateService/multipart',
               'HttpPushUri': '/redfish/v1/UpdateService/push',
               'Actions': {'#UpdateService.SimpleUpdate':
                           {'target': '/redfish/v1/UpdateService/Actions/SimpleUpdate'}}}
    assert FirmwarePush().push_target(service=service) == (
        SIMPLE, '/redfish/v1/UpdateService/Actions/SimpleUpdate')


def test_multipart_is_used_where_the_board_will_not_fetch():
    from utils.firmware_push import FirmwarePush, MULTIPART

    service = {'MultipartHttpPushUri': '/redfish/v1/UpdateService/multipart',
               'HttpPushUri': '/redfish/v1/UpdateService/push'}
    assert FirmwarePush().push_target(service=service) == (
        MULTIPART, '/redfish/v1/UpdateService/multipart')


def test_a_board_offering_nothing_is_reported_not_guessed_at():
    from utils.firmware_push import FirmwarePush

    kind, reason = FirmwarePush().push_target(service={})
    assert kind is None and 'no way to send it an image' in reason


def test_the_submitted_payload_names_the_image_and_the_protocol():
    from utils.firmware_push import FirmwarePush, SIMPLE

    machine = board({}, extra={'__post__': {'@odata.type': '#Task.v1_4_3.Task',
                                            '@odata.id': '/redfish/v1/TaskService/Tasks/3',
                                            'TaskState': 'Running'}})
    status, task = FirmwarePush().submit(
        redfish=machine, kind=SIMPLE, uri='/redfish/v1/UpdateService/Actions/SimpleUpdate',
        image_url='http://10.141.0.1:7051/files/bmc.bin', targets=['/redfish/v1/Managers/1'])
    assert status is True
    assert task == '/redfish/v1/TaskService/Tasks/3'
    assert machine.posted[0]['payload'] == {
        'ImageURI': 'http://10.141.0.1:7051/files/bmc.bin',
        'TransferProtocol': 'HTTP',
        'Targets': ['/redfish/v1/Managers/1']}


def test_a_running_task_is_waited_on():
    from utils.firmware_push import FirmwarePush

    machine = FakeBoard({'/redfish/v1/TaskService/Tasks/3': {'TaskState': 'Running'}})
    assert FirmwarePush().track(redfish=machine,
                                task='/redfish/v1/TaskService/Tasks/3') == ('waiting', 'Running')


def test_a_task_that_ran_out_of_time_is_a_failure_that_says_so():
    from utils.firmware_push import FirmwarePush

    machine = FakeBoard({'/redfish/v1/TaskService/Tasks/3': {'TaskState': 'Running'}})
    state, reason = FirmwarePush().track(redfish=machine, task='/redfish/v1/TaskService/Tasks/3',
                                         deadline=1800, waited=1800)
    assert state == 'failed' and 'still Running' in reason


def test_a_refused_task_is_a_failure():
    from utils.firmware_push import FirmwarePush

    machine = FakeBoard({'/redfish/v1/TaskService/Tasks/3': {
        'TaskState': 'Exception',
        '@Message.ExtendedInfo': [{'Message': 'image rejected'}]}})
    state, reason = FirmwarePush().track(redfish=machine, task='/redfish/v1/TaskService/Tasks/3')
    assert state == 'failed' and reason == 'image rejected'


def test_a_vanished_task_is_not_a_failure():
    """
    The trap the specification does not prepare anybody for. Many services delete
    the monitor the moment the work finishes, so a task that is gone is the ordinary
    end of a successful flash. Calling it a failure fails successful updates.
    """
    from utils.firmware_push import FirmwarePush

    state, _ = FirmwarePush().track(redfish=FakeBoard({}),
                                    task='/redfish/v1/TaskService/Tasks/3')
    assert state == 'gone'
    assert state != 'failed'


def test_a_completed_task_is_finished_and_not_succeeded():
    """Nothing in the tracker may conclude success. Only the version can."""
    from utils.firmware_push import FirmwarePush

    machine = FakeBoard({'/redfish/v1/TaskService/Tasks/3': {'TaskState': 'Completed'}})
    state, _ = FirmwarePush().track(redfish=machine, task='/redfish/v1/TaskService/Tasks/3')
    assert state == 'finished'
    assert state != 'succeeded'


def inventory(version):
    """A board publishing one firmware component at the given version."""
    return board(
        {'FirmwareInventory': {'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory'}},
        extra={'/redfish/v1/UpdateService/FirmwareInventory':
               {'Members': [{'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/BMC'}]},
               '/redfish/v1/UpdateService/FirmwareInventory/BMC':
               {'Id': 'BMC', 'Name': 'BMC', 'Version': version}})


def test_a_flash_is_verified_by_the_version_the_board_reports():
    from utils.firmware_push import FirmwarePush

    assert FirmwarePush().verify(redfish=inventory('7.10'),
                                 component='BMC', wanted='7.10') == (True, '7.10')


def test_a_completed_task_over_an_unchanged_version_is_a_failure():
    """
    The inactive-slot case, and the reason verify() exists at all: the task said
    Completed, the service is happy, and the board is still running what it was.
    """
    from utils.firmware_push import FirmwarePush

    machine = inventory('7.00')
    state, _ = FirmwarePush().track(
        redfish=FakeBoard({'/redfish/v1/TaskService/Tasks/3': {'TaskState': 'Completed'}}),
        task='/redfish/v1/TaskService/Tasks/3')
    assert state == 'finished'

    status, reason = FirmwarePush().verify(redfish=machine, component='BMC', wanted='7.10')
    assert status is False
    assert 'inactive slot' in reason


def test_a_component_the_board_does_not_publish_is_reported():
    from utils.firmware_push import FirmwarePush

    status, reason = FirmwarePush().verify(redfish=inventory('7.10'),
                                           component='CPLD', wanted='1.0')
    assert status is False and 'no component called CPLD' in reason


def action_board(parameters=None, inline=None):
    """A board whose SimpleUpdate declares its parameters in an ActionInfo."""
    action = {'target': '/redfish/v1/UpdateService/Actions/SimpleUpdate'}
    if inline:
        action.update(inline)
    if parameters is not None:
        action['@Redfish.ActionInfo'] = '/redfish/v1/UpdateService/SimpleUpdateActionInfo'
    machine = board({'Actions': {'#UpdateService.SimpleUpdate': action}})
    if parameters is not None:
        machine.resources['/redfish/v1/UpdateService/SimpleUpdateActionInfo'] = {
            'Parameters': parameters}
    return machine, action


# The parameters a real AMI board declares, transcribed from the hardware.
AMI_PARAMETERS = [
    {'Name': 'ImageURI', 'DataType': 'String', 'Required': True},
    {'Name': 'TransferProtocol', 'DataType': 'String', 'Required': True,
     'AllowableValues': ['HTTP', 'FTP', 'HTTPS']},
    {'Name': 'User', 'DataType': 'String', 'Required': False},
    {'Name': 'Password', 'DataType': 'String', 'Required': False},
    {'Name': 'UpdateComponent', 'DataType': 'String', 'Required': False,
     'AllowableValues': ['BMC', 'BIOS', 'MB_CPLD', 'BPB_CPLD',
                         'HPM_BMC', 'HPM_BIOS', 'HPM_SCP']},
]


def test_the_payload_uses_the_component_parameter_the_board_declares():
    """
    The board names it UpdateComponent and takes one string, not the standard
    Targets array. A payload written from the specification is not the one this
    board accepts, and it declares which it wants.
    """
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=AMI_PARAMETERS)
    status, body = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://10.141.0.1:7051/files/bmc.bin',
        component='BMC', targets=['/redfish/v1/Managers/1'])
    assert status is True
    assert body['UpdateComponent'] == 'BMC'
    assert 'Targets' not in body


def test_a_board_declaring_targets_gets_targets():
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=[
        {'Name': 'ImageURI'}, {'Name': 'Targets'}])
    status, body = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin',
        component='BMC', targets=['/redfish/v1/Managers/1'])
    assert status is True
    assert body['Targets'] == ['/redfish/v1/Managers/1']
    assert 'UpdateComponent' not in body


def test_the_transfer_protocol_comes_from_the_url_and_is_checked():
    """Published only in ActionInfo on the boards measured, never inline."""
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=AMI_PARAMETERS)
    status, body = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin',
        component='BMC')
    assert status is True and body['TransferProtocol'] == 'HTTP'


def test_a_protocol_the_board_refuses_is_refused_here_rather_than_by_the_board():
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=[
        {'Name': 'TransferProtocol', 'AllowableValues': ['HTTPS']},
        {'Name': 'UpdateComponent', 'AllowableValues': ['BMC']}])
    status, reason = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin',
        component='BMC')
    assert status is False and 'does not accept HTTP' in reason


def test_a_component_the_board_does_not_offer_is_refused():
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=AMI_PARAMETERS)
    status, reason = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin',
        component='GPU')
    assert status is False and 'no component GPU' in reason


def test_a_board_asking_which_component_and_given_none_is_refused():
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(parameters=AMI_PARAMETERS)
    status, reason = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin')
    assert status is False and 'none was named' in reason


def test_inline_allowable_values_are_honoured_where_a_board_publishes_them():
    """Both forms are legal; a board using the inline one must still work."""
    from utils.firmware_push import FirmwarePush

    machine, action = action_board(
        parameters=None,
        inline={'TransferProtocol@Redfish.AllowableValues': ['HTTPS']})
    status, reason = FirmwarePush().payload(
        redfish=machine, action=action, image_url='http://host/files/bmc.bin')
    assert status is False and 'does not accept HTTP' in reason
