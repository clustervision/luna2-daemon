#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a wrapper for the TOKEN verification.
Correct Token Should be supplied to access any Luna POST API.
If Get API Has the Token, it will get the access to fetch more data.

"""
import os
from functools import wraps
from flask import request, json
from utils.log import *
import jwt

logger = Log.get_logger()


"""
Input - Token
Process - After validate the Token, Return the arguments and keyword arguments Of The API.
Output - Success or Failure.
"""
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            logger.error("A Valid Token Is Missing.")
            response = {"message": "A Valid Token Is Missing."}
            code = 401
            return json.dumps(response), code
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"]) ## Decoding Token
            if data["id"] == 1:
                current_user = data["id"]
        except:
            logger.error("Token Is Invalid.")
            response = {"message": "Token Is Invalid."}
            code = 401
            return json.dumps(response), code
        return f(**kwargs)
    return decorator


"""
Input - Token
Process - After validate the Token, Return the arguments and keyword arguments Of The API Along access key with admin value to use further.
Output - With/Without Access.
"""
def validate_access(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        access = "anonymous"
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            access = "anonymous"
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"]) ## Decoding Token
            if data["id"] == 1:
                current_user = data["id"]
                access = "admin"  ## Adding Access admin to retirve the full data set or perform the admin level action.
        except:
            return f(**kwargs)  ## Without Access admin to perform the minimal operation.
        return f(access=access, **kwargs)
    return decorator