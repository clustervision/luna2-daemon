#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
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
This file is the entry point for changing who may do what with a governed object:
its mode, its usergroups and its owners, as chmod, chgrp and chown do for a file.
One route each, for every governed entity, named in the path.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from flask import Blueprint, request, g
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from utils.access import Access, AccessRefused, GOVERNED
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
access_blueprint = Blueprint('config_access', __name__)


def _change(verb, entity, name):
    """
    The three verbs differ only in the method they call and the field they take. The
    object is a path argument called objectname rather than name: the input filter would
    otherwise look for it under a fixed entity it cannot know here. Its rule is keyed on
    that word alone; a journal payload carries a free-form field called object.
    """
    if entity not in GOVERNED:
        return {'message': f'Invalid request: {entity} is not a governed object'}, 400
    try:
        # the rule is checked here, on the controller that took the request; the peer
        # replays the change as the system user
        status, response = getattr(Access(), verb)(entity, name, request.data, g.userid, dry=True)
    except AccessRefused as exp:
        return {'message': exp.message}, exp.code
    if status is not True:
        return {'message': response}, Helper().get_access_code(status, response)
    status, response = Journal().add_request(function=f"Access.{verb}", object=entity, param=name, payload=request.data)
    if status is True:
        status, response = getattr(Access(), verb)(entity, name, request.data, g.userid)
    return {'message': response}, Helper().get_access_code(status, response)


@access_blueprint.route("/config/<string:entity>/<string:objectname>/_chmod", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config'], skip=None)
def config_chmod(entity=None, objectname=None):
    """
    Body: access as ls shows it, nine characters.
    """
    return _change('chmod', entity, objectname)


@access_blueprint.route("/config/<string:entity>/<string:objectname>/_chgrp", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config'], skip=None)
def config_chgrp(entity=None, objectname=None):
    """
    Body: usergroups as names; a bare list replaces, +name adds, -name removes.
    """
    return _change('chgrp', entity, objectname)


@access_blueprint.route("/config/<string:entity>/<string:objectname>/_chown", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config'], skip=None)
def config_chown(entity=None, objectname=None):
    """
    Body: owners as usernames; a bare list replaces, +name adds, -name removes.
    """
    return _change('chown', entity, objectname)
