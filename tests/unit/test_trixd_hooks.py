#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2276: what the config hooks hand to trixd, and what they stop doing once it has it.

Two rules, both invisible from a single node. A bulk operation is one change carrying the
whole set, because trixd stores and runs one task per change it is given: a set handed
over node by node is a task per node, and a set pushed without its entries is a render
with nothing to render. And where trixd took a rename or a delete it owns the hardware
rule files under the Prometheus rules directory - it carries them to the new name and
retires them with a copy - so the hook's own rename and rm are the fallback for a
controller without trixd, not something that runs as well and undoes it.

TRIX-2298 adds the interface hook to the same family. An interface has no identity
downstream, so an interface write is announced as the node it belongs to - never as a
node delete, which retires the rule files of a node that is still there - and it carries
only the fields its call site already held.
"""

import logging

import pytest

INI = """[API]
PROTOCOL = http
BIND = 127.0.0.1:8050
USERNAME = luna
PASSWORD = secret
"""

FULLSET = [{'name': f'node{number:04d}', 'group': 'compute' if number % 2 else 'gpu'}
           for number in range(1, 41)]


class Answer:
    """The parts of a requests response the addon reads."""
    status_code = 200
    text = ''

    @staticmethod
    def json():
        return {'token': 'a-token'}


@pytest.fixture
def trixd(tmp_path, monkeypatch):
    """A trixd that accepts everything and records each set, with no network behind it.

    Where trixd answers and the token it gave are both held in module globals for the
    life of the process, so they are reset here: one test must not answer for the next.
    """
    import plugins.addons.trixd as addon

    ini = tmp_path / 'trixd.ini'
    ini.write_text(INI)
    monkeypatch.setenv('TRIXD_INI', str(ini))
    monkeypatch.setattr(addon, '_resolved', None)
    monkeypatch.setattr(addon, '_token', None)

    posted = []

    class Requests:
        @staticmethod
        def post(url, json=None, **kwargs):
            if url.endswith('/system/bulk'):
                posted.append(json)
            return Answer()

    monkeypatch.setattr(addon, 'requests', Requests)
    return posted


@pytest.fixture
def rule_files(monkeypatch):
    """Records what the node hook shells out to run, and keeps it off the filesystem."""
    import plugins.hooks.config.node as hook

    ran = []

    class Finished:
        args = 'recorded'
        returncode = 0
        stderr = b''

    class Subprocess:
        PIPE = -1

        @staticmethod
        def run(command, **kwargs):
            ran.append(command)
            return Finished()

    monkeypatch.setattr(hook, 'subprocess', Subprocess)
    return ran


@pytest.fixture
def generators(monkeypatch):
    """Installs both config generators as present, recording what they are asked to write.

    Present rather than stood down on purpose: what has to be proven once trixd is told
    is that these are never called, and a generator set to None cannot tell being left
    alone apart from not being there at all.
    """
    import plugins.hooks.config.node as hook

    called = []

    class Recorder:
        """Stands in for a generator package, and records being asked to write."""

        def __init__(self, label):
            self.label = label

        def __call__(self):
            return self

        def all_configs(self, fullset):
            called.append((self.label, len(fullset)))
            return True

        def Genders(self, fullset):
            called.append((self.label, len(fullset)))
            return True

    monkeypatch.setattr(hook, 'Slurm', Recorder('slurm'))
    monkeypatch.setattr(hook, 'Generate', Recorder('genders'))
    return called


def errors(caplog, hook='hooks/config/node.py'):
    """The errors one hook itself logged, for a test that pins their absence.

    Scoped to the hook: resolving where trixd is reads the database, which logs errors
    of its own in this harness, and they are not what these tests are about.
    """
    return [record.getMessage() for record in caplog.records
            if record.levelno >= logging.ERROR
            and record.pathname.endswith(hook)]


def events(posted):
    """Every event the recorded sets carried, in the order trixd was told them."""
    return [change.get('event') for body in posted
            for change in body.get('changes', [])]


def entries(posted, event):
    """What the recorded sets carried for one event.

    Tolerant on purpose: a push that never happened reads as an empty set here rather
    than raising in the test's own setup, so the assertion is what reports it. The
    entries themselves are read field by field for the same reason - an entry is free to
    carry more than the hook happens to hold today.
    """
    carried = []
    for body in posted:
        for change in body.get('changes', []):
            if change.get('event') == event:
                carried.extend((change.get('payload') or {}).get('fullset', []))
    return carried


def payloads(posted, event):
    """What the recorded sets carried as the payload of one event, in order."""
    return [change.get('payload') or {} for body in posted
            for change in body.get('changes', [])
            if change.get('event') == event]


# ------------------------------------------------- a set is one change, with the set in it


def test_a_node_bulk_tells_trixd_once_for_the_whole_set(trixd, rule_files, generators):
    """One call carrying one change, whatever the size of the set.

    Told, the method returns before anything else runs, so the push arriving at all is
    what proves it sits above that return.
    """
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().bulk(FULLSET)
    assert events(trixd) == ['luna.node.bulk'], (
        f'a bulk over {len(FULLSET)} nodes pushed {events(trixd)}. One change carrying '
        f'the set is the contract; one change per node is a task per node in trixd.'
    )
    assert len(trixd) == 1, f'the set reached trixd in {len(trixd)} calls, not one'
    assert status is True, message


# ------------------------------------- the generators are a fallback, not a requirement


def test_a_node_bulk_told_does_not_run_the_generators(trixd, rule_files, generators):
    """Told, trixd writes these files and Luna does not: one writer per file.

    A luna.node.bulk event wakes trixd's slurm and genders renders, which write through
    the same packages, so running them here as well is a second writer of one file.
    """
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().bulk(FULLSET)
    assert events(trixd) == ['luna.node.bulk'], events(trixd)
    assert status is True, message
    assert generators == [], (
        f'trixd has the set and wrote these files itself, and the hook ran {generators} '
        f'over them as well'
    )


def test_a_node_bulk_told_without_generators_is_quiet_and_successful(
        trixd, rule_files, caplog, monkeypatch):
    """The state Luna is heading for: the packages gone, trixd the only writer.

    Absent generators must not be an error on a controller where trixd has the set, or
    every bulk on a finished controller logs one and reports failure.
    """
    import plugins.hooks.config.node as hook
    monkeypatch.setattr(hook, 'Slurm', None)
    monkeypatch.setattr(hook, 'Generate', None)
    with caplog.at_level(logging.ERROR):
        status, message = hook.Plugin().bulk(FULLSET)
    assert status is True, message
    assert errors(caplog) == [], (
        f'an absent generator is the normal state once trixd writes these files, and '
        f'the hook logged {errors(caplog)}'
    )


def test_a_node_bulk_without_trixd_runs_the_generators(rule_files, generators,
                                                       monkeypatch):
    """No trixd on this controller: the generators are the fallback and still run."""
    import plugins.hooks.config.node as hook
    monkeypatch.setattr(hook, 'trixd_notify', None)
    status, message = hook.Plugin().bulk(FULLSET)
    assert status is True, message
    assert generators == [('slurm', len(FULLSET)), ('genders', len(FULLSET))], (
        f'without trixd nothing writes these files but the generators, and they ran '
        f'{generators}'
    )


def test_a_node_bulk_without_trixd_or_generators_is_a_failure(rule_files, caplog,
                                                              monkeypatch):
    """With neither, nothing writes those files at all - the one genuinely broken case."""
    import plugins.hooks.config.node as hook
    monkeypatch.setattr(hook, 'trixd_notify', None)
    monkeypatch.setattr(hook, 'Slurm', None)
    monkeypatch.setattr(hook, 'Generate', None)
    with caplog.at_level(logging.ERROR):
        status, message = hook.Plugin().bulk(FULLSET)
    assert status is False, message
    assert len(errors(caplog)) == 1, (
        f'the one case that is really broken has to say so loudly, and it logged '
        f'{errors(caplog)}'
    )


def test_a_node_bulk_carries_every_entry_of_the_set(trixd, rule_files):
    """The payload is the fullset itself: trixd is fed the estate, not told to go and ask."""
    from plugins.hooks.config.node import Plugin
    Plugin().bulk(FULLSET)
    carried = entries(trixd, 'luna.node.bulk')
    assert len(carried) == len(FULLSET), (
        f'the push carried {len(carried)} of {len(FULLSET)} nodes. A dropped or '
        f'truncated set renders short, and nothing downstream can tell.'
    )
    found = [entry for entry in carried if entry.get('name') == 'node0007']
    assert found, f'no entry for node0007 came through at all: {carried[:3]}'
    assert found[0].get('group') == 'compute', (
        f'node0007 arrived without the group it was handed with: {found[0]}'
    )


def test_a_group_bulk_tells_trixd_once_for_the_whole_set(trixd):
    """The same for groups, where the hook has nothing else to do."""
    from plugins.hooks.config.group import Plugin
    status, message = Plugin().bulk(FULLSET)
    assert status is True, message
    assert events(trixd) == ['luna.group.bulk'], (
        f'a bulk over {len(FULLSET)} groups pushed {events(trixd)}'
    )
    assert len(trixd) == 1, f'the set reached trixd in {len(trixd)} calls, not one'


def test_a_group_bulk_carries_every_entry_of_the_set(trixd):
    """Both hooks are handed the same data, so both carry it the same way."""
    from plugins.hooks.config.group import Plugin
    Plugin().bulk(FULLSET)
    carried = entries(trixd, 'luna.group.bulk')
    assert len(carried) == len(FULLSET), (
        f'the push carried {len(carried)} of {len(FULLSET)} entries'
    )
    found = [entry for entry in carried if entry.get('name') == 'node0007']
    assert found, f'no entry for node0007 came through at all: {carried[:3]}'
    assert found[0].get('group') == 'compute', (
        f'node0007 arrived without the group it was handed with: {found[0]}'
    )


# ------------------------------------------------------- the rule files are trixd's


def test_a_rename_leaves_the_rule_files_to_trixd(trixd, rule_files):
    """Told, the hook does not touch the files trixd is about to carry itself."""
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().rename('node001', 'node002')
    assert len(trixd) == 1, 'the rename was not handed to trixd at all'
    assert rule_files == [], (
        f'trixd took the rename and the hook ran {rule_files} as well. Both move the '
        f'same files, and only trixd knows where it has already put them.'
    )
    assert status is True, message


def test_a_rename_renames_the_rule_files_itself_without_trixd(rule_files, monkeypatch):
    """No addon on this controller: exactly what ran before still runs."""
    import plugins.hooks.config.node as hook
    monkeypatch.setattr(hook, 'trixd_notify', None)
    status, message = hook.Plugin().rename('node001', 'node002')
    assert len(rule_files) == 1, (
        f'without trixd nothing carries the rule files but the hook, and it ran '
        f'{rule_files}'
    )
    assert '/usr/bin/rename' in rule_files[0][0]
    assert 'prometheus_server/rules' in rule_files[0][0]
    assert status is True, message


def test_a_delete_leaves_the_rule_files_to_trixd(trixd, rule_files):
    """The same for a delete: trixd retires them with a copy, the hook's rm does not."""
    from plugins.hooks.config.node import Plugin
    status, message = Plugin().delete('node001')
    assert len(trixd) == 1, 'the delete was not handed to trixd at all'
    assert rule_files == [], (
        f'trixd took the delete and the hook ran {rule_files} as well, which removes '
        f'the files trixd keeps a copy of.'
    )
    assert status is True, message


# --------------------------------------- an interface write is a change to its node


# The four methods and what each operation can supply, as base/interface.py supplies it:
# a create and an update have the row and its network, a rename has the pair of names,
# and a delete has neither once the row is gone.
INTERFACE_CALLS = {
    'postcreate': {'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:01',
                   'ipaddress': '10.141.0.9', 'ipaddress_ipv6': 'fd00:141::9',
                   'network': 'cluster', 'networktype': 'ethernet', 'zone': 'cluster'},
    'postupdate': {'interface': 'BOOTIF', 'macaddress': 'aa:bb:cc:dd:ee:01',
                   'ipaddress': '10.141.0.9', 'ipaddress_ipv6': 'fd00:141::9',
                   'network': 'cluster', 'networktype': 'ethernet', 'zone': 'cluster'},
    'rename': {'interface': 'BOOTIF', 'newinterfacename': 'eth0'},
    'delete': {'interface': 'BOOTIF'},
}

# Shipped empty, so it is held to the signature but not to announcing anything.
INTERFACE_STUBS = {'macaddressupdate': {'interface': 'BOOTIF',
                                        'macaddress': 'aa:bb:cc:dd:ee:01'}}


@pytest.mark.parametrize('method', list(INTERFACE_CALLS))
def test_an_interface_write_is_announced_as_a_node_update(trixd, method):
    """Every one of the four, under the one event a trixd render and handler both know.

    luna.nodeinterface.update would pass trixd's shape check, wake the renders and repair
    nothing, reporting a string that reads as an outcome. The object segment of an event
    is a render-input name, so an interface event is one nothing is listening for.
    """
    from plugins.hooks.config.interface import Plugin
    status, message = getattr(Plugin(), method)(name='node001', **INTERFACE_CALLS[method])
    assert events(trixd) == ['luna.node.update'], (
        f'{method} announced {events(trixd)}. luna.node.update is the only name that both '
        f'repairs the rule files and wakes the renders.'
    )
    assert status is True, message
    carried = payloads(trixd, 'luna.node.update')[0]
    assert carried['name'] == 'node001', f'{method} announced {carried}'
    for field, value in INTERFACE_CALLS[method].items():
        assert carried.get(field) == value, (
            f'{method} carried {field}={carried.get(field)!r}, not {value!r}: {carried}'
        )


def test_each_method_declares_exactly_what_its_operation_can_supply(trixd):
    """The signature is the contract a site plugin is written against.

    Enumerated from the methods themselves rather than asserted one by one, so a field
    added to one of them has to be added here - and so no kwargs can creep back in, which
    would leave a customer unable to tell from the method what it will be handed.
    """
    from inspect import signature
    from plugins.hooks.config.interface import Plugin
    for method, fields in {**INTERFACE_CALLS, **INTERFACE_STUBS}.items():
        declared = signature(getattr(Plugin, method)).parameters
        assert set(declared) == {'self', 'name'} | set(fields), (
            f'{method} declares {sorted(declared)}, and its call site supplies '
            f'{sorted({"name"} | set(fields))}'
        )
        assert all(parameter.kind == parameter.POSITIONAL_OR_KEYWORD
                   for parameter in declared.values()), (
            f'{method} takes something other than named parameters: {declared}'
        )


def test_an_interface_delete_is_not_a_node_delete(trixd):
    """One interface went and the node did not.

    luna.node.delete reaches remove_hw_rules in the trix-daemon, which retires every
    hardware rule file of the node named - so announcing an interface removal that way
    takes a node that is still running out of its own alerting.
    """
    from plugins.hooks.config.interface import Plugin
    status, message = Plugin().delete(name='node001', interface='BOOTIF')
    assert status is True, message
    assert 'luna.node.delete' not in events(trixd), (
        f'removing one interface announced {events(trixd)}, and a node delete retires '
        f'the rule files of a node that is still there'
    )
    assert events(trixd) == ['luna.node.update'], events(trixd)


def test_a_field_the_write_could_not_read_is_absent_rather_than_empty(trixd):
    """A create whose interface has no address yet leaves the address out of the payload.

    An empty string cannot be told apart from an address that was looked for and found
    gone, and the trix-daemon takes whatever it is handed.
    """
    from plugins.hooks.config.interface import Plugin
    Plugin().postcreate(name='node001', interface='BOOTIF')
    carried = payloads(trixd, 'luna.node.update')[0]
    assert set(carried) == {'name', 'interface'}, (
        f'a create that knew only the node and the interface carried {sorted(carried)}'
    )


@pytest.mark.parametrize('method', list(INTERFACE_CALLS))
def test_an_interface_write_without_trixd_is_quiet_and_successful(method, caplog,
                                                                 monkeypatch):
    """No addon on this controller, which is the normal state of most of them.

    Nothing was asked of trixd and nothing failed, so this is success. The hook has no
    files of its own to write instead, which is why there is no fallback to run here.
    """
    import plugins.hooks.config.interface as hook
    monkeypatch.setattr(hook, 'trixd_notify', None)
    assert hook.trixd_notify is None, 'the addon is still in place, so this proves nothing'
    with caplog.at_level(logging.ERROR):
        status, message = getattr(hook.Plugin(), method)(name='node001',
                                                         **INTERFACE_CALLS[method])
    assert status is True, message
    assert message == 'trixd not notified', message
    assert errors(caplog, 'hooks/config/interface.py') == [], (
        f'a controller without trixd is the normal case and the hook logged '
        f'{errors(caplog, "hooks/config/interface.py")}'
    )


def test_a_macaddress_change_announces_nothing_at_all(trixd):
    """The extension point ships empty, and empty means no event rather than a quiet one.

    Nothing in the trix-daemon reads a macaddress - no handler takes one and no render
    declares one - so announcing a change to it would wake every render to repair a value
    none of them look at, and report an outcome that reads like success. The method is
    there for somebody else's plugin; until one exists, the right amount of work is none.
    """
    from plugins.hooks.config.interface import Plugin
    status, message = Plugin().macaddressupdate(name='node001', interface='BOOTIF',
                                                macaddress='aa:bb:cc:dd:ee:01')
    assert status is True, message
    assert events(trixd) == [], (
        f'the stub announced {events(trixd)}. A node writes its macaddress as it boots, '
        f'so anything outward-facing here is paid once per node per boot.'
    )


