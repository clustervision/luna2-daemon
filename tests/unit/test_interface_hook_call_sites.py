#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2298: which hook method each interface write reaches, and why never two of them.

The method is chosen from the change itself and not from who asked for it. A rename wins,
then an address or network that moved, and a macaddress on its own falls to the extension
point that ships empty - so one write is one call, and a booting node writing nothing but
its macaddress reaches a method that does nothing rather than announcing a value no
consumer reads. Removing an interface that never had an address announces nothing either.

What none of it covers is a node write that carries an address: update_node applies it
through the same function and then announces the node itself, so that one change is
announced twice. That is accepted rather than fixed, and pinned below so it stays visible.
"""

import pytest


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.helper import Helper

    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in DBStructure().tables:
        Database().create(table, DBStructure().get_database_table_structure(table))
    Database().insert('cluster', Helper().make_rows({'name': 'cluster'}))
    Database().insert('osimage', Helper().make_rows({'name': 'theosimage'}))
    Database().insert('network', Helper().make_rows({'name': 'cluster', 'network': '10.141.0.0',
                                                    'subnet': '16', 'type': 'ethernet',
                                                    'zone': 'internal'}))
    Database().insert('network', Helper().make_rows({'name': 'ibnet', 'network': '10.149.0.0',
                                                    'subnet': '16', 'type': 'infiniband',
                                                    'zone': 'ib'}))
    Database().insert('group', Helper().make_rows({'name': 'compute', 'osimageid': 1}))
    Database().insert('node', Helper().make_rows({'name': 'node001', 'groupid': 1}))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


@pytest.fixture
def fired(monkeypatch):
    """Which config hook each route loaded, and what it asked of it.

    Recorded at plugin_load rather than inside the plugins: what these tests pin is which
    hook a route reaches, and one recorder standing in for all of them is the only way to
    tell the node hook firing from the interface hook firing.
    """
    from utils.helper import Helper

    called = []

    class Recorder:
        """Stands in for any config hook plugin, and records being called."""

        def __init__(self, hook):
            self.hook = hook

        def __call__(self):
            return self

        def __getattr__(self, method):
            def record(**facts):
                called.append((self.hook, method, facts))
                return True, 'recorded'
            return record

    monkeypatch.setattr(Helper, 'plugin_load',
                        lambda self, plugins=None, root=None, levelone=None,
                        leveltwo=None, class_name=None: Recorder(levelone))
    return called


def hook_calls(fired, hook):
    """What one hook was asked to do, tolerant of its not having been asked at all."""
    return [entry for entry in fired if entry[0] == hook]


BOOTIF = {'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:01',
          'ipaddress': '10.141.0.9', 'network': 'cluster'}


def change(name='node001', interfaces=None):
    """One POST to the dedicated interface route, in the shape the body arrives in."""
    from base.interface import Interface
    return Interface().change_node_interface_by_name(
        name=name, request_data={'config': {'node': {name: {'interfaces': interfaces}}}})


def test_an_interface_create_fires_the_interface_hook_once(db, fired):
    """One request, one announcement, carrying what the write already knew."""
    status, message = change(interfaces=[BOOTIF])
    assert status is True, message
    calls = hook_calls(fired, 'interface')
    assert len(calls) == 1, f'the interface hook fired {len(calls)} times: {calls}'
    hook, method, facts = calls[0]
    assert method == 'postcreate', f'a new interface announced {method}'
    assert facts['name'] == 'node001', facts
    assert facts['interface'] == 'BOOTIF', facts
    assert facts['ipaddress'] == '10.141.0.9', facts
    assert facts['network'] == 'cluster', facts
    assert facts['macaddress'] == 'aa:bb:cc:dd:ee:01', facts


def test_every_interface_is_announced_whichever_one_it_is(db, fired):
    """Nothing is filtered by interface name: an interface a node does not provision over
    announces exactly as the provisioning one does, carrying its own address.

    Which of them is reachable from a controller is a property of the node rather than of
    the change, so a consumer reads the node's resolved provision_interface from the API
    and compares. The README says so, because an address on an interface no controller can
    route to is the one a consumer would wrongly scrape.
    """
    status, message = change(interfaces=[{'interface': 'ib0', 'ipaddress': '10.149.0.9',
                                          'network': 'ibnet'}])
    assert status is True, message
    assert hook_calls(fired, 'interface'), f'the interface hook never fired: {fired}'
    hook, method, facts = hook_calls(fired, 'interface')[-1]
    assert method == 'postcreate', f'a new interface announced {method}'
    assert facts['interface'] == 'ib0' and facts['ipaddress'] == '10.149.0.9', facts


def test_an_interface_update_carries_the_network_type_and_zone(db, fired):
    """Two strings added to a select the write already makes, so they cost nothing.

    They describe the network the row is on, which is why an update that leaves the
    interface there is where they can be believed.
    """
    change(interfaces=[BOOTIF])
    status, message = change(interfaces=[{'interface': 'BOOTIF', 'ipaddress': '10.141.0.10'}])
    assert status is True, message
    assert hook_calls(fired, 'interface'), f'the interface hook never fired: {fired}'
    hook, method, facts = hook_calls(fired, 'interface')[-1]
    assert method == 'postupdate', f'an interface that was already there announced {method}'
    assert facts['networktype'] == 'ethernet', facts
    assert facts['zone'] == 'internal', facts
    assert facts['network'] == 'cluster', facts
    # The request left the macaddress alone, so what travels is the one on the row.
    assert facts['macaddress'] == 'aa:bb:cc:dd:ee:01', facts


def test_an_interface_rename_carries_both_names(db, fired):
    """The one operation where the old and the new name together cannot be recovered."""
    change(interfaces=[BOOTIF])
    status, message = change(interfaces=[{'interface': 'BOOTIF', 'newinterfacename': 'eth0'}])
    assert status is True, message
    assert hook_calls(fired, 'interface'), f'the interface hook never fired: {fired}'
    hook, method, facts = hook_calls(fired, 'interface')[-1]
    assert method == 'rename', f'a body carrying newinterfacename announced {method}'
    assert facts['interface'] == 'BOOTIF', f'the name it was called is gone: {facts}'
    assert facts['newinterfacename'] == 'eth0', facts


def test_an_interface_delete_fires_the_delete_hook_once(db, fired):
    """The delete route, which has the node and the interface and nothing else to hand."""
    from base.interface import Interface
    change(interfaces=[BOOTIF])
    fired.clear()
    status, message = Interface().delete_node_interface_by_name('node001', 'BOOTIF')
    assert status is True, message
    calls = hook_calls(fired, 'interface')
    assert len(calls) == 1, f'the interface hook fired {len(calls)} times: {calls}'
    hook, method, facts = calls[0]
    assert method == 'delete', f'removing an interface announced {method}'
    assert facts == {'name': 'node001', 'interface': 'BOOTIF'}, facts


def test_a_macaddress_only_write_reaches_the_extension_point_and_not_postupdate(db, fired):
    """What the journal replays once per booting node, and which method it must land on.

    Every one of boot.py's six entries carries the interface and a macaddress and nothing
    else. No address and no network moved, so postupdate would report a change no consumer
    of it can see; the macaddress method takes it instead, and that one ships empty. What
    keeps a boot cheap is therefore the body of that method, pinned in test_trixd_hooks.
    """
    from base.interface import Interface
    nodeid = db.get_record(table='node', where="name = 'node001'")[0]['id']
    change(interfaces=[BOOTIF])
    assert hook_calls(fired, 'interface'), (
        f'the interface hook never fires in this harness, so nothing below means '
        f'anything: {fired}'
    )
    fired.clear()
    status, message = Interface().change_node_interface(
        nodeid, [{'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:02'}])
    assert status is True, message
    assert [entry[1] for entry in hook_calls(fired, 'interface')] == ['macaddressupdate'], (
        f'a macaddress on its own belongs to the macaddress method and to no other, and '
        f'this write reached {fired}'
    )
    assert hook_calls(fired, 'interface')[0][2] == {
        'name': 'node001', 'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:02'}, (
        f'the macaddress method takes the node, the interface and the macaddress and '
        f'nothing else: {fired}'
    )


def test_a_link_only_write_announces_nothing_today(db, fired):
    """A known gap, recorded so that closing it is a decision rather than a surprise.

    An mtu, an options string, a vlan or a bond setting is a real change to a real
    interface and reaches no hook. The methods carry the addressing, so there is nothing
    for such a write to say in the shape they have. Whoever adds those fields will find
    this test red, which is where to read what the behaviour used to be.
    """
    change(interfaces=[BOOTIF])
    fired.clear()
    status, message = change(interfaces=[{'interface': 'BOOTIF', 'mtu': '9000'}])
    assert status is True, message
    assert hook_calls(fired, 'interface') == [], (
        f'the link settings are not part of any method today, and this write announced '
        f'{fired}'
    )


def test_a_new_interface_cannot_be_made_of_link_settings_alone(db, fired):
    """An interface cannot be brought into being out of link settings alone.

    A body naming only an mtu, on an interface with no address row behind it, is turned
    away. Pinned because the reading that it is allowed is the obvious one and it is
    wrong - the second of the two guards in change_node_interface catches it, not the
    first - and because a wrong claim about it cost real time.
    """
    status, message = change(interfaces=[{'interface': 'ib0', 'mtu': '2044'}])
    assert status is False, f'a link-only create was accepted and announced {fired}'
    assert 'minimal parameters' in str(message), message
    assert hook_calls(fired, 'interface') == [], fired


def test_a_macaddress_beside_a_link_setting_still_reaches_the_macaddress_method(db, fired):
    """The addressing is what outranks the macaddress, and a link setting is not it.

    So a write moving a macaddress and an mtu announces the macaddress, and the mtu is not
    reported anywhere - the same gap the test above records, from the other side.
    """
    change(interfaces=[BOOTIF])
    fired.clear()
    status, message = change(interfaces=[{'interface': 'BOOTIF', 'mtu': '9000',
                                          'macaddress': 'aa:bb:cc:dd:ee:04'}])
    assert status is True, message
    assert [entry[1] for entry in hook_calls(fired, 'interface')] == ['macaddressupdate'], (
        f'a write that moved a macaddress and an mtu reached {fired}'
    )
    assert hook_calls(fired, 'interface')[0][2] == {
        'name': 'node001', 'interface': 'BOOTIF',
        'macaddress': 'aa:bb:cc:dd:ee:04'}, hook_calls(fired, 'interface')[0][2]


def test_a_write_moving_an_address_reaches_postupdate_and_not_the_macaddress_method(db,
                                                                                   fired):
    """One write is one call. An address that moved outranks a macaddress that moved too.

    postupdate already carries the macaddress, so a second call for the same write would
    tell a consumer twice about one change and leave it to work out they are the same.
    """
    change(interfaces=[BOOTIF])
    fired.clear()
    status, message = change(interfaces=[{'interface': 'BOOTIF', 'ipaddress': '10.141.0.11',
                                          'macaddress': 'aa:bb:cc:dd:ee:03'}])
    assert status is True, message
    assert [entry[1] for entry in hook_calls(fired, 'interface')] == ['postupdate'], (
        f'a write that moved both reached {fired}'
    )
    assert hook_calls(fired, 'interface')[0][2]['macaddress'] == 'aa:bb:cc:dd:ee:03', (
        f'postupdate is the one call for that write, so it has to carry the macaddress '
        f'the write set: {fired}'
    )


def test_a_node_write_carrying_an_address_is_announced_twice(db, fired):
    """An accepted cost, written down so it stays deliberate.

    update_node applies the interfaces through the same function and then announces the
    node through the node hook, so one luna node change -I produces both. Nothing can
    tell the two callers apart from inside: the bodies are identical. Both events are
    luna.node.update and the repair behind them is idempotent, so the cost is one extra
    call and not a conflict. Should this ever be closed, this test is where to read why
    it was not.
    """
    from base.node import Node
    status, message = Node().update_node(name='node001', request_data={'config': {'node': {'node001': {
        'interfaces': [{'interface': 'BOOTIF', 'ipaddress': '10.141.0.9',
                        'network': 'cluster'}]}}}})
    assert status is True, message
    assert len(hook_calls(fired, 'node')) == 1, (
        f'the node hook is the one that always announced this change, and it fired '
        f'{len(hook_calls(fired, "node"))} times: {fired}'
    )
    assert len(hook_calls(fired, 'interface')) == 1, (
        f'the interface hook fired {len(hook_calls(fired, "interface"))} times: {fired}'
    )
