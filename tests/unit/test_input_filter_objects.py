#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.

"""
TRIX-2163: every route behind @input_filter refuses a body whose object is not a
dict or list with a 400, before the base class reads fields from it. It used to
reach the base class and end in an unhandled 500.
"""

import json

from jwt import encode

from cases.route_requirements_cases import app as routes_app


def _filtered(view):
    """Whether @input_filter wraps this view: its wrapper is named filter_input."""
    while view is not None:
        if getattr(getattr(view, '__code__', None), 'co_name', None) == 'filter_input':
            return True
        view = getattr(view, '__wrapped__', None)
    return False


def test_every_filtered_route_refuses_a_body_whose_object_is_text(sqlite_db):
    from common.constant import CONSTANT
    app = routes_app()
    token = encode({'id': 0}, CONSTANT['API']['SECRET_KEY'], 'HS256')
    client, checked, crashed = app.test_client(), [], []
    for rule in app.url_map.iter_rules():
        # the /config routes declare the path to their object; the others take a body of their own
        if 'POST' not in rule.methods or not rule.rule.startswith('/config/') \
                or not _filtered(app.view_functions[rule.endpoint]):
            continue
        args = {argument: 'probe' for argument in rule.arguments}
        path = rule.rule
        for argument in rule.arguments:
            path = path.replace(f'<string:{argument}>', 'probe')
        parts = path.strip('/').split('/')
        # the object sits at the route's own path, as the CLI builds it: config.<entity>.<name>
        top = parts[0]
        body = {top: 'x'} if len(parts) < 2 else {top: {parts[1]: {args.get('name', 'probe'): 'x'} if len(parts) > 2 else 'x'}}
        response = client.post(path, headers={'x-access-tokens': token}, data=json.dumps(body),
                               content_type='application/json')
        checked.append(rule.rule)
        if response.status_code >= 500:
            crashed.append(f'{rule.rule} -> {response.status_code}')
    assert len(checked) >= 60, checked
    assert not crashed, 'routes that crash on a body whose object is text:\n  ' + '\n  '.join(crashed)
