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
Correct Token Should be supplied to access any Luna 2 API.

"""
import os
from common.constants import *
from functools import wraps
from flask import abort, request, jsonify
from utils.log import *
import jwt
from utils.database.database import *

logger = Log.get_logger()

def login_required(f):
    @wraps(f)
    def login(**kwargs):
        if not kwargs['token'] == TOKEN:
            abort(401)
        return f(**kwargs)
    return login


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        my_auth_url = os.getenv('SECRET_KEY')
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            return jsonify({'message': 'A Valid Token Is Missing.'})
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            if data["id"] == 1:
                current_user = data["id"]
            # DB Interaction
            # select = "*"
            # table = "user"
            # where = [{"column": "id", "value": str(data["id"])}]
            # user = Database().get_record(select, table, where)
            # if user:
            #     userID = user[0]["id"]
            #     password = user[0]["password"]
            #     current_user = userID
        except:
            return jsonify({'message': 'Token Is Invalid.'})
        return f(**kwargs)
    return decorator


def validate_access(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        access = "anonymous"
        my_auth_url = os.getenv('SECRET_KEY')
        token = None
        if 'x-access-tokens' in request.headers:
            token = request.headers['x-access-tokens']
        if not token:
            access = "anonymous"
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            if data["id"] == 1:
                current_user = data["id"]
                access = "admin"
            # DB Interaction
            # select = "*"
            # table = "user"
            # where = [{"column": "id", "value": str(data["id"])}]
            # user = Database().get_record(select, table, where)
            # if user:
            #     userID = user[0]["id"]
            #     password = user[0]["password"]
            #     current_user = userID
            #     access = "admin"
        except:
            return f(**kwargs)
        return f(access=access, **kwargs)
    return decorator