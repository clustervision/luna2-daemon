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
This File is use for authentication purpose.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import logging
from datetime import datetime, timedelta
from re import search
from jwt import encode, decode, exceptions
from utils.log import Log
from utils.database import Database
from base.user import User
from utils.helper import Helper
from utils.audit import Audit
from common.constant import CONSTANT

# Files with these extensions are handed out by the file server only with a token;
# anything else is served to whoever can reach the port. OS images wear these and
# are fetched by an installer that has a token, which is why the line sits where
# it does. Kept here, where it is enforced, and read by whatever else must agree.
TOKEN_GATED_EXTENSIONS = ('.gz', '.tar', '.bz', '.bz2', '.torrent')


class Authentication():
    """
    This class is responsible to authenticate tokens.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_token(self, request_data=None):
        """
        This method will provide a PyJWT encoded token.
        """
        status = False
        message, jwt_token = "", ""

        if request_data:
            if 'username' in request_data:
                username = request_data['username']
                if 'password' in request_data:
                    password = request_data['password']
                    api_expiry = timedelta(seconds=int(CONSTANT['API']['EXPIRY']))
                    expiry_time = datetime.utcnow() + api_expiry
                    api_key = CONSTANT['API']['SECRET_KEY']
                    if username and password:
                        if CONSTANT['API']['USERNAME'] != username:
                            self.logger.info(f'Username {username} does not belong to INI.')
                            user_id, message = self.login(username, password)
                            if user_id is not None:
                                jwt_token = encode({'id': user_id, 'exp': expiry_time}, api_key, 'HS256')
                                message = f'Authentication token generated, Token {jwt_token}'
                                self.logger.debug(message)
                                status = True
                                Audit().record(userid=user_id, username=username, method='POST', path='/token',
                                               outcome='login', code=201)
                            else:
                                self.logger.warning(message)
                                Audit().record(username=username, method='POST', path='/token',
                                               outcome='refused', code=401, detail=message)
                        else:
                            if CONSTANT['API']['PASSWORD'] != password:
                                shown = password if self.logger.isEnabledFor(logging.DEBUG) else '******'
                                message = f'Incorrect password {shown}, check luna.ini'
                                self.logger.warning(message)
                            else:
                                # Creating Token via JWT with default id =1, expiry time
                                # and Secret Key from conf file, and algo Sha 256
                                jwt_token = encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
                                message = f'Authentication token generated, Token {jwt_token}'
                                self.logger.debug(message)
                                status = True
                    else:
                        message = 'Please provide the username and password'
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


    def chain(self):
        """
        Output - the authentication sources in the order they are asked, from [AUTH] CHAIN;
        local then pam when the ini says nothing.
        """
        named = CONSTANT.get('AUTH', {}).get('CHAIN') or 'local, pam'
        return [source.strip().lower() for source in named.split(',') if source.strip()]


    def login(self, username=None, password=None):
        """
        This method walks the chain. The first source that knows the name decides: verified
        becomes a Luna user through login_identity, refused stops the chain. A source that
        cannot work is logged and skipped, so a local user still gets in.
        Output - the user's id and a message, or None and the reason.
        """
        # the journal imports every base class, and one of them imports this module
        from utils.journal import Journal
        plugins_path = CONSTANT['PLUGINS']['PLUGINS_DIRECTORY']
        auth_plugins = Helper().plugin_finder(f'{plugins_path}/auth')
        for source in self.chain():
            try:
                plugin_class = Helper().plugin_load(auth_plugins, 'auth', [source])
                if not plugin_class:
                    self.logger.error(f"authentication source {source} has no plugin; skipped")
                    continue
                status, result = plugin_class().authenticate(username, password)
            except Exception as exp:
                self.logger.error(f"authentication source {source} is unavailable: {exp}")
                continue
            if status is None:
                self.logger.debug(f"authentication source {source} does not know {username}: {result}")
                continue
            if status is False:
                return None, result
            journaled, message = Journal().add_request(function="User.login_identity", object=source, payload=result)
            if not journaled:
                self.logger.warning(f"login of {username} not journaled: {message}; the table sync repairs the peer")
            return User().login_identity(source, result)
        return None, f'User {username} is not known to any authentication source'


    def node_token(self, request_data=None, nodename=None):
        """
        This method will provide a PyJWT encoded token for a node.
        """
        status=False
        if not request_data:
            self.logger.error('Login Required')
            response = 'Login Required'
            status=False

        self.logger.debug(f"TPM auth: {request_data}")

        api_expiry = timedelta(seconds=int(CONSTANT['API']['EXPIRY']))
        expiry_time = datetime.utcnow() + api_expiry
        api_key = CONSTANT['API']['SECRET_KEY']

        status=False
        response = 'no result'
        create_token = False

        cluster = Database().get_record(table='cluster')
        if cluster and 'security' in cluster[0] and cluster[0]['security']:
            self.logger.info(f"cluster security = {cluster[0]['security']}")
            if 'tpm_sha256' in request_data:
                node = Database().get_record(table='node', where=f"name = '{nodename}'")
                if node:
                    if 'tpm_sha256' in node[0]:
                        if request_data['tpm_sha256'] == node[0]['tpm_sha256']:
                            create_token=True
                        else:
                            response = {'message' : 'invalid TPM information'}
                    else:
                        response = {'message' : 'node does not have TPM information'}
                else:
                    response = {'message' : 'invalid node'}
        else:
            forward_data={}
            if 'username' in request_data:
                forward_data['username']=request_data['username']
            if 'password' in request_data:
                forward_data['password']=request_data['password']
            fstatus,fresponse = self.get_token(forward_data)
            if fstatus is False:
                return fstatus, fresponse
            # we do not enforce security. just return the token
            # we store the string though - only a real one, and only when it changed.
            # the write is local to the controller that answered, so one per boot
            # keeps the node table differing between the controllers
            tpm_sha256 = request_data.get('tpm_sha256')
            if nodename and tpm_sha256:
                node = Database().get_record(table='node', where=f"name = '{nodename}'")
                if node and node[0]['tpm_sha256'] != tpm_sha256:
                    where = [{"column": "name", "value": nodename}]
                    row = [{"column": "tpm_sha256", "value": tpm_sha256}]
                    Database().update('node', row, where)
            create_token=True

        if create_token:
            # A node authenticates here for provisioning only, so issue a token scoped to
            # this node - the same shape the boot script embeds - rather than the admin
            # token. provision_token_required then confines it to this node's own endpoints.
            jwt_token = encode({'node': nodename, 'scope': 'provision', 'exp': expiry_time}, api_key, 'HS256')
            self.logger.debug(f'Node token generated successfully, Token {jwt_token}')
            status=True
            response = {"token" : jwt_token}

        self.logger.debug(f"my response: {response}")
        return status, response


    def validate_token(self, request_data=None, request_headers=None):
        """
        This method will provide a PyJWT encoded token for a node.
        """
        # since some files are requested during early boot stage where no token is available
        # (think: PXE+kernel+ramdisk)
        # we do enforce authentication for specific files. .bz2 + .torrent
        # are most likely the images.
        auth_ext = TOKEN_GATED_EXTENSIONS

        status=False
        http_token, uri, ext = None, None, None
        needs_auth = False
        if 'X-Original-URI' in request_headers:
            uri = request_headers['X-Original-URI']
        self.logger.debug(f"Auth request made for {uri}")
        if uri:
            result = search(r"^.+(\..[^.]+)(\?|\&|;|#)?", uri)
            if result:
                ext = result.group(1)
                if ext in auth_ext:
                    self.logger.debug(f"We enforce authentication for file extension = [{ext}]")
                    needs_auth=True
        else:
            status=False
            return status, "Missing request uri"

        if not needs_auth:
            status=True
            return status, "Go"

        if 'x-access-tokens' in request_headers:
            http_token = request_headers['x-access-tokens']
        if not http_token:
            self.logger.error(f'A valid token is missing for request {uri}.')
            status=False
            return status, "A valid token is missing"
        try:
            decode(http_token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) # Decode
        except exceptions.DecodeError:
            self.logger.error(f'Token is invalid for request {uri}.')
            status=False
            return status, "Token is invalid"
        except exceptions.ExpiredSignatureError:
            self.logger.error(f'Expired Signature Error for request {uri}.')
            status=False
            return status, "Token is invalid"
        self.logger.info(f"Valid authentication for extension [{ext}] - Go!")
        status=True
        return status, "Go"
