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

from json import dumps
from  hashlib import md5
from datetime import datetime, timedelta
from re import search
from jwt import encode, decode, exceptions
from utils.log import Log
from utils.database import Database
from common.constant import CONSTANT


class Authentication():
    """
    This class is responsible to authenticate tokens.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_token(self, http_request=None):
        """
        This method will provide a PyJWT encoded token.
        """
        status = False
        message, jwt_token = "", ""
        http_request = http_request.data

        if http_request:
            if 'username' in http_request:
                username = http_request['username']
                if 'password' in http_request:
                    password = http_request['password']
                    api_expiry = timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
                    expiry_time = datetime.utcnow() + api_expiry
                    api_key = CONSTANT['API']['SECRET_KEY']
                    if username and password:
                        if CONSTANT['API']['USERNAME'] != username:
                            message = f'Username {username} Not belongs to INI.'
                            self.logger.info(message)
                            where = f" WHERE username = '{username}' AND roleid = '1';"
                            user = Database().get_record(None, 'user', where)
                            if user:
                                user_id = user[0]["id"]
                                user_password = user[0]["password"]
                                if user_password == md5(password.encode()).hexdigest():
                                    jwt_token = encode(
                                        {'id': user_id, 'exp': expiry_time},
                                        api_key,
                                        'HS256'
                                    )
                                    message = f'Authentication token generated, Token {jwt_token}.'
                                    self.logger.debug(message)
                                    status = True
                                else:
                                    message = f'Incorrect password {password} for user {username}.'
                                    self.logger.warning(message)
                            else:
                                message = f'User {username} is not exists.'
                                self.logger.error(message)
                        else:
                            if CONSTANT['API']['PASSWORD'] != password:
                                message = f'Incorrect password {password}, check luna.ini.'
                                self.logger.warning(message)
                            else:
                                # Creating Token via JWT with default id =1, expiry time
                                # and Secret Key from conf file, and algo Sha 256
                                jwt_token = encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
                                message = f'Authentication token generated, Token {jwt_token}'
                                self.logger.debug(message)
                                status = True
                    else:
                        message = 'Kindly provide the username and password'
                        self.logger.error(message)
                else:
                    message = 'Password Is Required'
                    self.logger.error(message)
            else:
                message = 'Username Is Required'
                self.logger.error(message)
        else:
            message = 'Login Required'
            self.logger.error(message)
        response = {'token' : jwt_token} if jwt_token else {'message' : message}
        return status, response


    def node_token(self, http_request=None, nodename=None):
        """
        This method will provide a PyJWT encoded token for a node.
        """
        http_request = http_request.data
        if not http_request:
            self.logger.error('Login Required')
            response = {'message' : 'Login Required'}
            access_code = 401

        self.logger.debug(f"TPM auth: {http_request}")

        api_expiry = timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
        expiry_time = datetime.utcnow() + api_expiry
        api_key = CONSTANT['API']['SECRET_KEY']

        access_code = 401
        response = {'message' : 'no result'}
        create_token = False

        cluster = Database().get_record(None, 'cluster', None)
        if cluster and 'security' in cluster[0] and cluster[0]['security']:
            self.logger.info(f"cluster security = {cluster[0]['security']}")
            if 'tpm_sha256' in http_request:
                node = Database().get_record(None, 'node', f' WHERE name = "{nodename}"')
                if node:
                    if 'tpm_sha256' in node[0]:
                        if http_request['tpm_sha256'] == node[0]['tpm_sha256']:
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
            if nodename and 'tpm_sha256' in http_request:
                where = [{"column": "name", "value": nodename}]
                row = [{"column": "tpm_sha256", "value": http_request['tpm_sha256']}]
                Database().update('node', row, where)
            create_token=True

        if create_token:
            jwt_token = encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
            self.logger.debug(f'Node token generated successfully, Token {jwt_token}')
            access_code = 200
            response = {"token" : jwt_token}

        self.logger.debug(f"my response: {response}")
        return dumps(response), access_code


    def validate_token(self, http_request=None):
        """
        This method will provide a PyJWT encoded token for a node.
        """
        # since some files are requested during early boot stage where no token is available
        # (think: PXE+kernel+ramdisk)
        # we do enforce authentication for specific files. .bz2 + .torrent
        # are most likely the images.
        auth_ext = [".gz", ".tar", ".bz", ".bz2", ".torrent"]

        access_code = 401
        http_token, uri, ext = None, None, None
        needs_auth = False
        if 'X-Original-URI' in http_request.headers:
            uri = http_request.headers['X-Original-URI']
        self.logger.debug(f"Auth request made for {uri}")
        if uri:
            result = search(r"^.+(\..[^.]+)(\?|\&|;|#)?", uri)
            ext = result.group(1)
            if ext in auth_ext:
                self.logger.debug(f"We enforce authentication for file extension = [{ext}]")
                needs_auth=True
        else:
            access_code = 401
            return "Missing request uri", access_code

        if not needs_auth:
            access_code = 200
            return "Go", access_code

        if 'x-access-tokens' in http_request.headers:
            http_token = http_request.headers['x-access-tokens']
        if not http_token:
            self.logger.error(f'A valid token is missing for request {uri}.')
            access_code = 401
            return "A valid token is missing", access_code
        try:
            decode(http_token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) # Decode
        except exceptions.DecodeError:
            self.logger.error(f'Token is invalid for request {uri}.')
            access_code = 401
            return "Token is invalid", access_code
        except exceptions.ExpiredSignatureError:
            self.logger.error(f'Expired Signature Error for request {uri}.')
            access_code = 401
            return "Token is invalid", access_code
        self.logger.info(f"Valid authentication for extension [{ext}] - Go!")
        access_code = 200
        return "Go", access_code
