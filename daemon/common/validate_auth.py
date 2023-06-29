#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
            LOGGER.error('A valid token is missing.')
            response = {'message': 'A valid token is missing.'}
            code = 401
            return json.dumps(response), code
        try:
            jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) ## Decoding Token
        except jwt.exceptions.DecodeError:
            LOGGER.error('Token is invalid.')
            response = {'message': 'Token is invalid.'}
            code = 401
            return json.dumps(response), code
        except Exception as exp:
            LOGGER.error(f'Token is invalid. {exp}')
            response = {'message': 'Token is invalid.'}
            code = 401
            return json.dumps(response), code
        return function(**kwargs)
    return decorator
