#!/usr/bin/env python3
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
from flask import request, json, abort
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT
import jwt


LOGGER = Log.get_logger()


def token_required(f):
    """
    Input - Token
    Process - After validate the Token, Return the arguments
    and keyword arguments Of The API.
    Output - Success or Failure.
    """
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            LOGGER.error("A Valid Token Is Missing.")
            response = {"message": "A Valid Token Is Missing."}
            code = 401
            return json.dumps(response), code
        try:
            data = jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=["HS256"]) ## Decoding Token
            if data["id"] == 1:
                current_user = data["id"]
        except Exception as exp:
            LOGGER.error("Token Is Invalid.")
            response = {"message": "Token Is Invalid."}
            code = 401
            return json.dumps(response), code
        return f(**kwargs)
    return decorator


def validate_access(f):
    """
    Input - Token
    Process - After validate the Token, Return the arguments and keyword
    arguments Of The API Along access key with admin value to use further.
    Output - With/Without Access.
    """
    @wraps(f)
    def decorator(*args, **kwargs):
        access = "anonymous"
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            access = "anonymous"
        try:
            data = jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=["HS256"]) ## Decoding Token
            if data["id"] == 1:
                current_user = data["id"]
                access = "admin"  ## Adding Access admin to retirve the full data set or perform the admin level action.
        except:
            return f(**kwargs)  ## Without Access admin to perform the minimal operation.
        return f(access=access, **kwargs)
    return decorator


def dbcheck(f):
    """
    Input - None
    Process - Verify If Database is present & Active and Working.
    Output - Success OR Abort to 503.
    """
    @wraps(f)
    def decorator(*args, **kwargs):
        result = Database().check_db()
        if result:
            LOGGER.info("Database Is Ready For The Transaction.")
        else:
            LOGGER.error("Database Is Not Ready.")
            abort(503, "Database")

        return f(**kwargs)
    return decorator
