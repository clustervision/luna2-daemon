#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-1999 / TRIX-1954: choosing a control plugin by what the hardware is.

Control plugins were selected by name alone - node name, then group name, then
default - and neither table has a vendor column. So plugins/control/dell.py, the
only Redfish implementation in the product, loaded only if a customer happened to
have a node or a group called "dell". On any real cluster it never ran.

The search path now carries the node's manufacturer and model, derived from
nodeinventory rather than configured, and a vendor-neutral redfish plugin behind
them. The order is the thing to protect: anything an administrator named
explicitly must still win, and a node the daemon knows nothing about must resolve
exactly as it did before.
"""

import pytest

from utils.database import Database
from utils.dbstructure import DBStructure
from utils.helper import Helper
from utils.redfish import RedfishAccess


@pytest.fixture
def inventory(monkeypatch, tmp_path):
    """A throwaway database with node, group, redfishsetup and nodeinventory."""
    import common.constant as constant
    from utils import database

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'selection.db')
    database.local_thread.connection = None
    for table in ('node', 'group', 'nodeinventory', 'redfishsetup', 'redfishaccount'):
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('group', Helper().make_rows({'name': 'compute'}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': 1}))
    return Database()


def add_inventory(source='inband', manufacturer='Dell Inc.', product='PowerEdge R650'):
    Database().insert('nodeinventory', Helper().make_rows(
        {'nodeid': 1, 'source': source, 'manufacturer': manufacturer, 'product': product}))


# --- turning what the hardware reports into a filename ----------------------

@pytest.mark.parametrize('manufacturer,expected', [
    ('Dell Inc.', 'dell'),
    ('VMware, Inc.', 'vmware'),
    ('Supermicro', 'supermicro'),
    ('Lenovo', 'lenovo'),
    ('HPE', 'hpe'),
    ('Hewlett Packard Enterprise', 'hewlett'),
    ('', None),
    (None, None),
])
def test_a_vendor_string_becomes_a_plugin_name(manufacturer, expected):
    """
    Vendor strings carry punctuation and a company suffix, so the first word names
    the file. Note what that costs and is accepted: a board reporting the long HPE
    name resolves to 'hewlett'. The README says so, because the alternative is an
    alias table that has to learn about every vendor forever.
    """
    assert RedfishAccess().token(manufacturer) == expected


@pytest.mark.parametrize('product,expected', [
    ('PowerEdge R650', 'poweredger650'),
    ('VMware7,1', 'vmware71'),
    ('ProLiant DL380 Gen10', 'proliantdl380gen10'),
    ('', None),
])
def test_a_model_keeps_its_whole_name(product, expected):
    """A model does not split usefully - PowerEdge is a family, R650 is the machine."""
    assert RedfishAccess().token(product, first=False) == expected


# --- where the manufacturer comes from --------------------------------------

def test_hardware_comes_from_the_inventory(inventory):
    add_inventory(source='inband', manufacturer='Dell Inc.', product='PowerEdge R650')
    assert RedfishAccess().hardware(nodename='node001') == ('dell', 'poweredger650')


def test_a_node_with_no_inventory_yields_nothing(inventory):
    assert RedfishAccess().hardware(nodename='node001') == (None, None)


def test_redfish_beats_inband_where_both_exist(inventory):
    """
    dmidecode and Redfish do not always return the same vendor string for the same
    machine, and the two snapshots coexist. Redfish wins: it is the BMC's own
    answer, and it is the one that exists before a node has ever been provisioned.
    """
    add_inventory(source='inband', manufacturer='Dell Inc.', product='PowerEdge R650')
    add_inventory(source='redfish', manufacturer='Supermicro', product='SYS-1029P')
    assert RedfishAccess().hardware(nodename='node001') == ('supermicro', 'sys1029p')


def test_inband_is_used_when_it_is_all_there_is(inventory):
    add_inventory(source='inband')
    assert RedfishAccess().hardware(nodename='node001')[0] == 'dell'


# --- the evidence gate ------------------------------------------------------

def test_no_evidence_means_no_generic_redfish_candidate(inventory):
    """
    The gate is about cost. A redfish plugin tries Redfish and falls back to
    ipmitool, so offering it to a BMC that does not answer buys a connect timeout
    per node - nothing on a rig, half an hour on a sweep of a few thousand.
    """
    add_inventory(source='inband')
    assert RedfishAccess().speaks_redfish(nodename='node001') is False


def test_a_redfish_inventory_snapshot_is_evidence(inventory):
    """It answered Redfish once, so it speaks Redfish."""
    add_inventory(source='redfish')
    assert RedfishAccess().speaks_redfish(nodename='node001') is True


def test_an_assigned_redfishsetup_is_evidence(inventory):
    """An administrator pointing a node at a redfishsetup is the opt-in switch."""
    Database().insert('redfishsetup', Helper().make_rows({'name': 'lab', 'scheme': 'https'}))
    Database().update('node', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "name", "value": "node001"}])
    assert RedfishAccess().speaks_redfish(nodename='node001') is True


def test_a_redfishsetup_on_the_group_is_evidence_too(inventory):
    """Selection follows node then group, the same as bmcsetup."""
    Database().insert('redfishsetup', Helper().make_rows({'name': 'lab', 'scheme': 'https'}))
    Database().update('group', Helper().make_rows({'redfishsetupid': 1}),
                      [{"column": "name", "value": "compute"}])
    assert RedfishAccess().speaks_redfish(nodename='node001') is True


# --- the search path --------------------------------------------------------

def candidates_for(nodename='node001', groupname='compute', generic='redfish'):
    """The control family's search path. boot/bmc asks the same helper without a
    generic, because its plugins emit a shell snippet rather than talking to a
    service - see test_boot_bmc_asks_for_the_same_path_without_a_generic."""
    return RedfishAccess().plugin_candidates(nodename=nodename, groupname=groupname,
                                             generic=generic)


def test_a_node_the_daemon_knows_nothing_about_resolves_as_before(inventory):
    """
    The regression floor. No inventory, no redfishsetup: the search path is exactly
    what it has always been, so every existing cluster is untouched until it has
    inventory to be selected on.
    """
    assert candidates_for() == (['node001', 'compute'], None)


def test_the_manufacturer_joins_the_path_behind_the_names(inventory):
    """
    Order is the whole safety argument. Node and group come first, so a plugin an
    administrator wrote and named still wins; the manufacturer can only take a slot
    that would otherwise have gone to default.py.
    """
    add_inventory(source='inband')
    assert candidates_for() == (['node001', 'compute', 'dell'], 'poweredger650')


def test_the_generic_plugin_comes_last_and_only_with_evidence(inventory):
    add_inventory(source='redfish', manufacturer='Supermicro', product='SYS-1029P')
    names, model = candidates_for()
    assert names == ['node001', 'compute', 'supermicro', 'redfish']
    assert names.index('redfish') == len(names) - 1
    assert model == 'sys1029p'


def test_a_missing_group_does_not_leave_a_hole_in_the_path(inventory):
    add_inventory(source='inband')
    names, _ = candidates_for(groupname=None)
    assert names == ['node001', 'dell']


# --- reset types, asked rather than assumed ---------------------------------

def plugin():
    from plugins.control.redfish import Plugin
    return Plugin()


def system_with(allowable=None, action_info=None):
    action = {'target': '/redfish/v1/Systems/1/Actions/ComputerSystem.Reset'}
    if allowable is not None:
        action['ResetType@Redfish.AllowableValues'] = allowable
    if action_info is not None:
        action['@Redfish.ActionInfo'] = action_info
    return {'Actions': {'#ComputerSystem.Reset': action}}


@pytest.mark.parametrize('action,expected', [
    ('on', 'On'), ('off', 'ForceOff'), ('reset', 'ForceRestart'), ('cycle', 'PowerCycle'),
])
def test_a_board_that_says_nothing_gets_what_dell_always_sent(action, expected):
    """
    Behaviour on hardware that does not advertise its reset types is unchanged from
    the plugin this replaces. That is deliberate: this is the code path that turns
    customers' machines on and off.
    """
    assert plugin().reset_type_for(action=action, system_data=system_with()) == expected


def test_a_board_that_refuses_the_first_choice_gets_the_next_one():
    """
    Some boards do not implement ForceOff. Asking what the board accepts turns that
    from a failed power operation into a graceful shutdown.
    """
    data = system_with(allowable=['On', 'GracefulShutdown', 'GracefulRestart'])
    assert plugin().reset_type_for(action='off', system_data=data) == 'GracefulShutdown'


def test_the_preferred_type_still_wins_when_the_board_offers_it():
    data = system_with(allowable=['On', 'ForceOff', 'GracefulShutdown'])
    assert plugin().reset_type_for(action='off', system_data=data) == 'ForceOff'


def test_a_board_offering_none_of_them_is_reported_rather_than_guessed():
    """Sending something the board rejects and reading the error is one round trip
    and one failed power operation worse than not sending it."""
    data = system_with(allowable=['Nmi', 'PushPowerButton'])
    assert plugin().reset_type_for(action='off', system_data=data) is None


def test_allowable_values_are_read_from_the_action_info_resource():
    """The other place a board publishes them, and the one people forget."""
    class FakeClient():
        def get(self, path=None, cache=False):
            return True, {'Parameters': [{'Name': 'ResetType',
                                          'AllowableValues': ['On', 'GracefulShutdown']}]}
    data = system_with(action_info='/redfish/v1/Systems/1/ResetActionInfo')
    assert plugin().reset_type_for(action='off', system_data=data,
                                   redfish=FakeClient()) == 'GracefulShutdown'


# --- the vendor file ---------------------------------------------------------

def test_dell_inherits_the_whole_control_contract():
    """
    dell.py overrides nothing today. It exists as the name the search path resolves
    for a Dell node and as the place Dell behaviour goes when a board needs it - so
    what matters is that it still answers every mandatory method.
    """
    from plugins.control.dell import Plugin as DellPlugin
    from plugins.control.redfish import Plugin as RedfishControl

    assert issubclass(DellPlugin, RedfishControl)
    for method in ('power_on', 'power_off', 'power_reset', 'power_cycle', 'power_status',
                   'identify', 'no_identify', 'sel_list', 'sel_clear'):
        assert callable(getattr(DellPlugin(), method)), method


def test_every_shipped_control_plugin_answers_the_whole_contract():
    """
    The README calls nine methods mandatory. A vendor file that implements eight of
    them raises AttributeError on a live cluster, from inside a thread, on the path
    that powers machines - so it is checked here instead.
    """
    import importlib
    import os

    control = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'daemon', 'plugins', 'control')
    required = ('power_on', 'power_off', 'power_reset', 'power_cycle', 'power_status',
                'identify', 'no_identify', 'sel_list', 'sel_clear')
    shipped = [name[:-3] for name in sorted(os.listdir(control))
               if name.endswith('.py') and not name.startswith('_')]
    assert 'default' in shipped and 'redfish' in shipped and 'dell' in shipped
    for name in shipped:
        module = importlib.import_module(f'plugins.control.{name}')
        instance = module.Plugin()
        missing = [method for method in required if not callable(getattr(instance, method, None))]
        assert not missing, f'plugins/control/{name}.py does not implement {missing}'


# --- the boot/bmc family asks the same question -----------------------------

def test_boot_bmc_asks_for_the_same_path_without_a_generic(inventory):
    """
    boot/bmc/dell.py prefers racadm over ipmitool and has shipped unreachable for
    the same reason control/dell.py had: a node is not called 'dell'. It gets the
    manufacturer too, but no vendor-neutral candidate - there is no such plugin,
    because these emit a shell snippet for the install rather than talking to a
    service.
    """
    add_inventory(source='redfish', manufacturer='Dell Inc.', product='PowerEdge R650')
    names, model = candidates_for(generic=None)
    assert names == ['node001', 'compute', 'dell']
    assert 'redfish' not in names
    assert model == 'poweredger650'


def test_boot_bmc_resolves_unchanged_for_a_node_with_no_inventory(inventory):
    """
    The regression floor for the install path, which is the one that matters most:
    boot/bmc runs while a node is being provisioned, and a node nobody has collected
    inventory for must resolve exactly as it always did.
    """
    assert candidates_for(generic=None) == (['node001', 'compute'], None)


def test_the_install_path_asks_for_no_generic_candidate():
    """
    Derived from the source rather than asserted about it: offering 'redfish' to
    boot/bmc would select a plugin that does not exist, and quietly get default.
    """
    import inspect

    from base.boot import Boot

    source = inspect.getsource(Boot)
    call = source[source.index("## BMC CODE SEGMENT"):]
    call = call[:call.index("bmc_plugin = ") + 400]
    assert 'plugin_candidates(' in call
    assert 'generic' not in call.split('plugin_candidates(')[1][:200]
