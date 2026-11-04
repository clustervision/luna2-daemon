#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2355: every column the osimage layout declares must be settable through the path
that writes an osimage record.

update_osimage checks the whole body against the table's columns and refuses all of it
when one key is not a column, so a declared column the write path drops or shadows does
not lose one field -- it refuses the request that carries it. A column named like one of
the body's control keys (tag, newosimage) is the shape to catch.

Derived from DATABASE_LAYOUT_osimage, so the next column added is covered without anybody
remembering this file.
"""

# Columns that are not body fields, each with the reason it cannot be one. A name goes
# here with its reason, never to reach green.
NOT_A_BODY_FIELD = {
    'id': 'the primary key, never sent',
    'name': 'the object addressed; the body may only repeat it, a rename sends newosimage',
    'tagid': 'the body carries tag, a name the daemon resolves to this id',
    'changed': 'the rename path sets it itself',
}


def _declared():
    """Every column DATABASE_LAYOUT_osimage declares, as (name, datatype)."""
    from common.database_layout import DATABASE_LAYOUT_osimage
    return [(entry['column'], entry.get('datatype', '')) for entry in DATABASE_LAYOUT_osimage]


def _value(datatype):
    """
    A value of the right kind, so a column added later needs no entry here, and one no
    default produces: a probe that happened to match the default would pass against a
    column the body cannot set at all.
    """
    return '1' if 'INT' in datatype.upper() else 'probe'


def test_the_exclusions_are_still_columns():
    """A renamed or dropped column must not linger above, silently excusing nothing."""
    declared = {column for column, _ in _declared()}
    assert not set(NOT_A_BODY_FIELD) - declared, sorted(set(NOT_A_BODY_FIELD) - declared)


def test_every_column_of_the_osimage_layout_is_reachable_through_update_osimage(sqlite_db):
    """A declared column that the write path will not store is the class this closes."""
    from base.osimage import OSImage
    from utils.database import Database

    columns = [(column, datatype) for column, datatype in _declared()
               if column not in NOT_A_BODY_FIELD]
    assert len(columns) > 10, 'the layout did not enumerate'

    unreachable = []
    for column, datatype in columns:
        name = f'probe-{column}'
        value = _value(datatype)
        status, message = OSImage().update_osimage(
            name, {'config': {'osimage': {name: {column: value}}}})
        if not status:
            unreachable.append(f'{column}: refused with {message}')
            continue
        record = Database().get_record(table='osimage', where=f"name = '{name}'")
        stored = record[0][column] if record else None
        if str(stored) != value:
            unreachable.append(f'{column}: sent {value}, stored {stored}')
    assert not unreachable, (
        'columns DATABASE_LAYOUT_osimage declares that update_osimage does not store:\n  '
        + '\n  '.join(unreachable)
        + '\nA column the body cannot carry belongs in NOT_A_BODY_FIELD with its reason.'
    )
