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
This file is the entry point for provisioning usergroups, their memberships and the map
from directory groups. Node groups live under /config/group, OS groups under /config/osgroup.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name
from base.usergroup import UserGroup
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
usergroup_blueprint = Blueprint('config_usergroup', __name__)


def _answer(status, response):
    """
    A read answers with the document or with the reason it has none.
    """
    if status is True:
        return dumps(response), 200
    return {'message': response}, 404


@usergroup_blueprint.route("/config/usergroup", methods=['GET'])
@token_required
def config_usergroup():
    """
    This route will provide all usergroups with their members.
    """
    return _answer(*UserGroup().get_usergroup())


@usergroup_blueprint.route("/config/usergroup/<string:name>", methods=['GET'])
@token_required
@validate_name
def config_usergroup_get(name=None):
    """
    This route will provide one usergroup with its members.
    """
    return _answer(*UserGroup().get_usergroup(name))


@usergroup_blueprint.route("/config/usergroup/<string:name>", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:usergroup'], skip=None)
def config_usergroup_post(name=None):
    """
    This route will create or update a usergroup: its name and comment. Members are
    added and removed one at a time through the members path.
    """
    status, response = Journal().add_request(function="UserGroup.update_usergroup", object=name, payload=request.data)
    if status is True:
        status, response = UserGroup().update_usergroup(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@usergroup_blueprint.route("/config/usergroup/<string:name>/_delete", methods=['GET'])
@token_required
@validate_name
def config_usergroup_delete(name=None):
    """
    This route will delete a usergroup, its memberships and its map rows.
    """
    status, response = Journal().add_request(function="UserGroup.delete_usergroup", object=name)
    if status is True:
        status, response = UserGroup().delete_usergroup(name)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@usergroup_blueprint.route("/config/usergroup/<string:name>/members", methods=['GET'])
@token_required
@validate_name
def config_usergroup_members(name=None):
    """
    This route will provide the members of a usergroup with their roles.
    """
    return _answer(*UserGroup().get_members(name))


@usergroup_blueprint.route("/config/usergroup/<string:name>/members", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:usergroup'], skip=None)
def config_usergroup_member_add(name=None):
    """
    This route adds one user to the usergroup with a role, or changes the role.
    The body carries the username and the role.
    """
    status, response = Journal().add_request(function="UserGroup.update_member", object=name, payload=request.data)
    if status is True:
        status, response = UserGroup().update_member(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@usergroup_blueprint.route("/config/usergroup/<string:name>/members/_remove", methods=['POST'])
@token_required
@validate_name
@input_filter(checks=['config:usergroup'], skip=None)
def config_usergroup_member_remove(name=None):
    """
    This route removes one user from the usergroup. The body carries the username.
    """
    status, response = Journal().add_request(function="UserGroup.remove_member", object=name, payload=request.data)
    if status is True:
        status, response = UserGroup().remove_member(name, request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@usergroup_blueprint.route("/config/usergroupmap", methods=['GET'])
@token_required
def config_usergroupmap():
    """
    This route will provide every map entry: source, external group, usergroup, role.
    """
    return _answer(*UserGroup().get_map())


@usergroup_blueprint.route("/config/usergroupmap", methods=['POST'])
@token_required
@input_filter(checks=['config:usergroupmap'], skip=['external_group'])
def config_usergroupmap_post():
    """
    This route adds one map entry or changes the usergroup and role of one. The body
    carries source and external_group as the key; a directory group name is not a path
    segment, so it travels in the body and is not filtered.
    """
    status, response = Journal().add_request(function="UserGroup.update_map", payload=request.data)
    if status is True:
        status, response = UserGroup().update_map(request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code


@usergroup_blueprint.route("/config/usergroupmap/_remove", methods=['POST'])
@token_required
@input_filter(checks=['config:usergroupmap'], skip=['external_group'])
def config_usergroupmap_remove():
    """
    This route removes one map entry, named by source and external_group in the body.
    """
    status, response = Journal().add_request(function="UserGroup.remove_map", payload=request.data)
    if status is True:
        status, response = UserGroup().remove_map(request.data)
    access_code = Helper().get_access_code(status, response)
    return {'message': response}, access_code
