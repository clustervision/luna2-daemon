#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
This File is the entry point for every profile request a booting node makes.
@provision_token_required is a wrapper method that validates the provision token.
"""

__author__      = "Antoine Schonewille"
__copyright__   = "Copyright 2025, Luna2 Project"
__license__     = "GPL"
__version__     = "2.2"
__maintainer__  = "Antoine Schonewille"
__email__       = "antoine.schonewille@clustervision.com"
__status__      = "Development"


from json import dumps
from flask import Blueprint
from utils.log import Log
from common.validate_auth import provision_token_required
from common.validate_input import validate_name
from base.profile import Profile

LOGGER = Log.get_logger()
boot_profiles_blueprint = Blueprint('boot_profiles', __name__)


@boot_profiles_blueprint.route('/boot/profiles/<string:profile>', methods=['GET'])
@provision_token_required
@validate_name
def get_boot_profile(profile=None):
    """
    Input - Profile name
    Process - Collects the profile's files (content, path, owner, mode) and its
              service with action, ready for the installer to apply.
    Output - json payload with files and service data
    """
    access_code = 404
    status, response = Profile().get_boot_profile(profile)
    if status is True:
        access_code = 200
        response=dumps(response)
    else:
        response = {'message': response}
    return response, access_code
