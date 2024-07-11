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
This File is a wrapper for the TOKEN verification.
Correct Token Should be supplied to access any Luna POST API.
If Get API Has the Token, it will get the access to fetch more data.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

from functools import wraps
from flask import request, json
import jwt
from utils.log import Log
from common.constant import CONSTANT

LOGGER = Log.get_logger()


def token_required(function):
    """
    Input - Token
    Process - After validate the Token, Return the arguments
    and keyword arguments Of The API.
    Output - Success or Failure.
    """
    @wraps(function)
    def decorator(*args, **kwargs):
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            LOGGER.error('A valid token is missing. None supplied')
            response = {'message': 'A valid token is missing'}
            code = 401
            return json.dumps(response), code
        try:
            jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) ## Decoding Token
        except jwt.exceptions.DecodeError:
            LOGGER.error('Token is invalid. Cannot decode')
            response = {'message': 'Token is invalid'}
            code = 401
            return json.dumps(response), code
        except Exception as exp:
            LOGGER.error(f'Token is invalid. {exp}')
            response = {'message': 'Token is invalid'}
            code = 401
            return json.dumps(response), code
        return function(**kwargs)
    return decorator


def agent_check(function):
    """
    This decorator will check if request is coming from tool or other client.
    """
    @wraps(function)
    def cli_check(*args, **kwargs):
        """
        This method will check HTTP_USER_AGENT.
        """
        kwargs['cli'] = False
        if 'HTTP_USER_AGENT' in request.environ:
            if 'Luna2-web' not in request.environ.get('HTTP_USER_AGENT'):
                kwargs['cli'] = True
        return function(**kwargs)
    return cli_check
