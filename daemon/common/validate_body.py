#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""
What a request body may hold for the object it addresses, checked before a base method
reads it. The token is checked in validate_auth and the text of each field in
validate_input; this is the shape of the body itself.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from functools import wraps


def body_checked(segment=None, lists=()):
    """
    Input - the segment the body keeps the object under, and the fields that hold a list
            of objects
    Output - a decorator for a base method taking (name, request_data). The body's name
             must be the name addressed, since a rename has a field of its own; a listed
             field holds a list of objects; nothing (null) in either reads as not given and
             is taken out of the body. Refused before the method runs, in the method's own
             (status, message) shape. A body without the object is left to the method.
    """
    def wrap(function):
        @wraps(function)
        def decorator(self, name=None, request_data=None, *args, **kwargs):
            try:
                body = request_data['config'][segment][name]
            except (KeyError, TypeError):
                body = None
            if isinstance(body, dict):
                for message in [name_addressed(body, name)] + [list_of_objects(body, field) for field in lists]:
                    if message:
                        return False, message
            return function(self, name, request_data, *args, **kwargs)
        return decorator
    return wrap


def name_addressed(body=None, name=None):
    """
    Output - None, or the message when the body names another object than the one addressed
    """
    if 'name' in body and body['name'] is None:
        del body['name']
    if 'name' in body and str(body['name']) != str(name):
        return f"Invalid request: the body names {body['name']}, the request addresses {name}"
    return None


def list_of_objects(body=None, field=None):
    """
    Output - None, or the message when the field holds anything but a list of objects
    """
    if field in body and body[field] is None:
        del body[field]
    entries = body.get(field, [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return f'Invalid request: {field} takes a list of objects'
    return None
