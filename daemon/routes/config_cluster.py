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
This is a entry file for cluster configurations.
@token_required wrapper Method is used to Validate the token.
@input_filter wrapper Method is used to Validate the POST data.
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint, request
from utils.log import Log
from common.validate_auth import token_required
from common.validate_input import input_filter
from base.cluster import Cluster
from utils.journal import Journal
from utils.helper import Helper

LOGGER = Log.get_logger()
cluster_blueprint = Blueprint('config_cluster', __name__)


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@cluster_blueprint.route("/config/cluster", methods=['GET'])
@token_required
def config_cluster():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    access_code = 404
    status, response = Cluster().information()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code


@cluster_blueprint.route("/config/cluster", methods=['POST'])
@token_required
@input_filter(checks=['config:cluster'], skip=None)
def config_cluster_post():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    message = "Cluster.update_cluster"
    status, response = Journal().add_request(function=message, payload=request.data)
    if status is True:
        status, response = Cluster().update_cluster(request.data)
    access_code = Helper().get_access_code(status,response)
    response = {'message': response}
    return response, access_code


@cluster_blueprint.route("/config/cluster/export", methods=['GET'])
@token_required
def config_cluster_export():
    """
    Input - None
    Process - Get all database table data
    Outout - All cluster config in importable json format.
    """
    access_code = 404
    status, response = Cluster().export_config()
    if status is True:
        access_code = 200
        response = dumps(response)
    else:
        response = {'message': response}
    return response, access_code

