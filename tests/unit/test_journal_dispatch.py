#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.

"""
TRIX-1937 unit tests guarding the class imports the replication journal dispatches through.

A mutating route replicates by naming its base method as a string:

    Journal().add_request(function="Route.update_route", ...)

The receiving controller resolves that string against utils/journal.py's own module
globals. So every base class named this way must be imported at the top of journal.py.
Nothing enforces the pairing and nothing fails at import time -- the peer raises
KeyError while the originating API call has already returned success.

The cost is not confined to the resource that was forgotten. The dispatch is bare and
the delete that clears a handled record is the last statement of the loop, so a record
that cannot resolve is never removed, comes back first on the next pass -- the query
orders by created -- and blocks every entry behind it. Replication for the whole peer
stops, not just for that resource.

The route classes are the declarative reality: whatever the codebase asks the journal
to call. These tests keep journal.py's imports in step with it.
"""

import ast
import os

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon')

# Names built at runtime rather than written as a literal, with where they are built.
# add_request is called with a variable there, so no static read can see the class name;
# these are checked by hand and listed so the gap is declared rather than silent.
DYNAMIC = {
    'Cluster.update_cluster': 'routes/config_cluster.py assigns the string to a message variable first',
}


def _dispatched():
    """Every "Class.method" literal handed to Journal().add_request anywhere in the daemon."""
    found = set()
    for root, _, files in os.walk(DAEMON):
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            with open(path, 'r', encoding='utf-8') as source:
                tree = ast.parse(source.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Attribute) and node.func.attr == 'add_request'):
                    continue
                for keyword in node.keywords:
                    if keyword.arg == 'function' and isinstance(keyword.value, ast.Constant):
                        if isinstance(keyword.value.value, str) and '.' in keyword.value.value:
                            found.add(keyword.value.value)
    return found


def _journal_globals():
    import utils.journal
    return vars(utils.journal)


def test_dispatched_classes_are_imported_in_journal():
    """Every class the journal is asked to call resolves in journal.py -- or the peer stalls."""
    namespace = _journal_globals()
    missing = sorted({
        function for function in _dispatched() | set(DYNAMIC)
        if function.split('.')[0] not in namespace
    })
    assert not missing, (
        f"replicated but not imported in utils/journal.py: {missing}. "
        "Add 'from base.<module> import <Class>' there. Without it the peer cannot resolve the "
        "name, the record is never cleared, and all replication behind it stops."
    )


def test_dispatched_methods_exist_on_their_class():
    """A renamed or dropped base method wedges the journal exactly like a missing import."""
    namespace = _journal_globals()
    broken = []
    for function in sorted(_dispatched() | set(DYNAMIC)):
        class_name, method_name = function.split('.', 1)
        if class_name in namespace and not hasattr(namespace[class_name], method_name):
            broken.append(function)
    assert not broken, (
        f"journal dispatches to methods that do not exist: {broken}. "
        "Renaming a replicated base method means renaming it at the add_request call too."
    )


def test_dynamic_dispatch_list_is_still_accurate():
    """The hand-listed runtime names must not quietly become literals we could have read."""
    literals = _dispatched()
    stale = sorted(set(DYNAMIC) & literals)
    assert not stale, (
        f"listed as dynamic but now written as a literal: {stale}. Remove them from DYNAMIC -- "
        "they are read from the source directly and the exemption hides them from that read."
    )


def test_unresolvable_record_is_dropped_not_left_to_block(tmp_path):
    """A record naming an unknown class is removed, so the entries behind it still run."""
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.dbstructure import DBStructure
    from utils.journal import Journal

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'journal.db')
    database.local_thread.connection = None
    Database().create('journal', DBStructure().get_database_table_structure('journal'))

    me = 'controller2'
    Database().insert('journal', [
        {"column": "function", "value": "NoSuchClass.no_such_method"},
        {"column": "object", "value": "node001"},
        {"column": "sendfor", "value": me},
        {"column": "sendby", "value": "controller1"},
        {"column": "created", "value": "2026-01-01 00:00:00"},
    ])

    journal = Journal()
    journal.me = me
    journal.handle_requests()

    left = Database().get_record(table='journal', where=f"sendfor='{me}'")
    assert not left, (
        "an unresolvable journal record survived handle_requests. It will be read first on every "
        "subsequent pass and block every record queued behind it."
    )
