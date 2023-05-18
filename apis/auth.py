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
from utils.helper import Helper
from utils.filter import Filter
import re

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
    username, password, auth = '', '', None
    if Helper().check_json(request.data):
        auth,ret = Filter().validate_input(request.get_json(force=True))
        if not ret:
            response = {'message': request_data}
            access_code = 400
            return json.dumps(response), access_code

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

    api_expiry = datetime.timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
    expiry_time = datetime.datetime.utcnow() + api_expiry
    api_key = CONSTANT['API']['SECRET_KEY']

    if CONSTANT['API']['USERNAME'] != username:
        LOGGER.info(f'Username {username} Not belongs to INI.')
        where = f" WHERE username = '{username}' AND roleid = '1';"
        user = Database().get_record(None, 'user', where)
        if user:
            userid = user[0]["id"]
            userpassword = user[0]["password"]
            if userpassword == hashlib.md5(password.encode()).hexdigest():
                jwt_token = jwt.encode({'id': userid, 'exp': expiry_time}, api_key, 'HS256')
                LOGGER.debug(f'Login token generated successfully, Token {jwt_token}.')
                response = {'token' : jwt_token}
                code = 200
            else:
                LOGGER.warning(f'Incorrect password {password} for the user {username}.')
                response = {'message' : f'Incorrect password {password} for the user {username}.'}
                code = 401
        else:
            LOGGER.error(f'User {username} is not exists.')
            response = {'message' : f'User {username} is not exists.'}
            code = 401
    else:
        if CONSTANT['API']['PASSWORD'] != password:
            LOGGER.warning(f'Incorrect password {password}, Kindly check the INI.')
            response = {'message' : f'Incorrect password {password}, Kindly check the INI.'}
            code = 401
        else:
            # Creating Token via JWT with default id =1, expiry time
            # and Secret Key from conf file, and algo Sha 256
            jwt_token = jwt.encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
            LOGGER.debug(f'Login token generated successfully, Token {jwt_token}')
            response = {"token" : jwt_token}
            code = 201
    return json.dumps(response), code

@auth_blueprint.route('/tpm/<string:nodename>', methods=['POST'])
def tpm(nodename=None):
    """
    Input - TPM string
    Process - Validate the TPM string to match a node.
    On the success, create a token, which is valid for expiry time mentioned in configuration.
    Output - Token.
    """
    auth=None
    if Helper().check_json(request.data):
        auth,ret = Filter().validate_input(request.get_json(force=True))
        if not ret:
            response = {'message': request_data}
            access_code = 400
            return json.dumps(response), access_code

    if not auth:
        LOGGER.error('Login Required')
        response = {'message' : 'Login Required'}
        code = 401

    LOGGER.debug(f"TPM auth: {auth}")

    api_expiry = datetime.timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
    expiry_time = datetime.datetime.utcnow() + api_expiry
    api_key = CONSTANT['API']['SECRET_KEY']

    code=401
    response = {'message' : 'no result'}
    create_token=False

    nodename = Filter().filter(nodename,'name')
    cluster = Database().get_record(None, 'cluster', None)
    if cluster and 'security' in cluster[0] and cluster[0]['security']:
        LOGGER.info(f"cluster security = {cluster[0]['security']}")
        if 'tpm_sha256' in auth:
            node = Database().get_record(None, 'node', f' WHERE name = "{nodename}"')
            if node:
                if 'tpm_sha256' in node[0]:
                    if auth['tpm_sha256'] == node[0]['tpm_sha256']:
                        create_token=True
                    else:
                        response = {'message' : 'invalid TPM information'}
                else:
                    response = {'message' : 'node does not have TPM information'}
            else:
                response = {'message' : 'invalid node'}
    else:
        # we do not enforce security. just return the token
        # we store the string though
        if nodename and 'tpm_sha256' in auth:
            where = [{"column": "name", "value": nodename}]
            row = [{"column": "tpm_sha256", "value": auth['tpm_sha256']}]
            Database().update('node', row, where)
        create_token=True

    if create_token:
        jwt_token = jwt.encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
        LOGGER.debug(f'Node token generated successfully, Token {jwt_token}')
        code=200
        response = {"token" : jwt_token}

    LOGGER.debug(f"my response: {response}")
    return json.dumps(response), code


@auth_blueprint.route('/filesauth', methods=['GET'])
def auth_get():
    """
    Needed for e.g. --> nginx subrequest auth <--
    Input - just headers -> token + original uri
    Process - Validate the token if needed
    On the success, return a go, else no go
    Output - go/no go
    """

    # since some files are requested during early bootstage where no token is available (think: PXE+kernel+ramdisk)
    # we do enforce authentication for specific files. .bz2 + .torrent are most likely the images.
    auth_ext = [".bz", ".torrent"]

    token,orguri,ext=None,None,None
    needs_auth=False
    if 'X-Original-URI' in request.headers:
        orguri = request.headers['X-Original-URI']
    LOGGER.info(f"Auth request made for {orguri}")
    if orguri:
        result = re.search(r"^.+(\..[^.]+)$", orguri)
        ext = result.group(1)
        if ext in auth_ext:
            LOGGER.info(f"We enforce authentication for file extension = [{ext}]")
            needs_auth=True

    if not needs_auth:
        return "go", 200

    if 'x-access-tokens' in request.headers:
        token = request.headers['x-access-tokens']
    if not token:
        LOGGER.error('A valid token is missing.')
        code = 401
        return "A valid token is missing", code
    try:
        jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) ## Decoding Token
    except jwt.exceptions.DecodeError:
        LOGGER.error('Token is invalid.')
        code = 401
        return "Token is invalid", code
    except Exception as exp:
        LOGGER.error(f'Token is invalid. {exp}')
        code = 401
        return "Token is invalid", code
    LOGGER.info("Valid authentication - Go!")
    return "go", 200

