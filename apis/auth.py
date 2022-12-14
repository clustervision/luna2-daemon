#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is use for authentication purpose.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import hashlib
import datetime
import jwt
from flask import Blueprint, request, json
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT

LOGGER = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/token', methods=['POST'])
def token():
    """
    Input - username and password
    Process - Validate the username and password from the conf file.
    On the success, create a token, which is valid for expiry time mentioned in configuration.
    Output - Token.
    """
    username, password = '', ''
    auth = request.get_json(force=True)
    api_expiry = datetime.timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
    expiry_time = datetime.datetime.utcnow() + api_expiry
    api_key = CONSTANT['API']['SECRET_KEY']
    if not auth:
        LOGGER.error('Login Required')
        response = {'message' : 'Login Required'}
        code = 401
    if 'username' not in auth:
        LOGGER.error('Username Is Required')
        response = {'message' : 'Login Required'}
        code = 401
    else:
        username = auth['username']
    if 'password' not in auth:
        LOGGER.error('Password Is Required')
        response = {'message' : 'Login Required'}
        code = 401
    else:
        password = auth['password']

    if CONSTANT['API']['USERNAME'] != username:
        LOGGER.info(f'Username {username} Not belongs to INI.')
        where = f" WHERE username = '{username}' AND roleid = '1';"
        user = Database().get_record(None, 'user', where)
        if user:
            userid = user[0]["id"]
            userpassword = user[0]["password"]
            if userpassword == hashlib.md5(password.encode()).hexdigest():
                jwt_token = jwt.encode({'id': userid, 'exp': expiry_time}, api_key, 'HS256')
                LOGGER.debug(f'Login Token generated Successfully, Token {jwt_token}.')
                response = {'token' : jwt_token}
                code = 200
            else:
                LOGGER.warning(f'Incorrect Password {password} for the user {username}.')
                response = {'message' : f'Incorrect Password {password} for the user {username}.'}
                code = 401
        else:
            LOGGER.error(f'User {username} is not exists.')
            response = {'message' : f'User {username} is not exists.'}
            code = 401
    else:
        if CONSTANT['API']['PASSWORD'] != password:
            LOGGER.warning(f'Incorrect Password {password}, Kindly check the INI.')
            response = {'message' : f'Incorrect Password {password}, Kindly check the INI.'}
            code = 401
        else:
            # Creating Token via JWT with default id =1, expiry time
            # and Secret Key from conf file, and algo Sha 256
            jwt_token = jwt.encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
            LOGGER.debug(f'Login Token generated Successfully, Token {jwt_token}')
            response = {"token" : jwt_token}
            code = 201
    return json.dumps(response), code
