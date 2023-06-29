#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Secret Class will handle all secrets related operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from json import dumps
from utils.database import Database
from utils.log import Log
from utils.helper import Helper


class Secret():
    """
    This class is responsible for all operations for secrets.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_secrets(self):
        """This method will return all secrets in detailed format."""
        nodesecrets = Database().get_record(None, 'nodesecrets', None)
        groupsecrets = Database().get_record(None, 'groupsecrets', None)
        if nodesecrets or groupsecrets:
            response = {'config': {'secrets': {} }}
            access_code = 200
        else:
            self.logger.error('Secrets are not available.')
            response = {'message': 'Secrets are not available'}
            access_code = 404
        if nodesecrets:
            response['config']['secrets']['node'] = {}
            for node in nodesecrets:
                nodename = Database().getname_byid('node', node['nodeid'])
                if nodename not in response['config']['secrets']['node']:
                    response['config']['secrets']['node'][nodename] = []
                del node['nodeid']
                del node['id']
                node['content'] = Helper().decrypt_string(node['content'])
                response['config']['secrets']['node'][nodename].append(node)
        if groupsecrets:
            response['config']['secrets']['group'] = {}
            for group in groupsecrets:
                groupname = Database().getname_byid('group', group['groupid'])
                if groupname not in response['config']['secrets']['group']:
                    response['config']['secrets']['group'][groupname] = []
                del group['groupid']
                del group['id']
                group['content'] = Helper().decrypt_string(group['content'])
                response['config']['secrets']['group'][groupname].append(group)
        return dumps(response), access_code


    def get_node_secrets(self, name=None):
        """This method will return all secrets of a requested node in detailed format."""
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            groupid  = node[0]['groupid']
            nodesecrets = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{nodeid}"')
            groupsecrets = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{groupid}"')
            if nodesecrets or groupsecrets:
                response = {'config': {'secrets': {} }}
                access_code = 200
            else:
                self.logger.error(f'Secrets are not available for node {name}.')
                response = {'message': f'Secrets are not available for node {name}'}
                access_code = 404
            if nodesecrets:
                response['config']['secrets']['node'] = {}
                for node in nodesecrets:
                    nodename = Database().getname_byid('node', node['nodeid'])
                    if nodename not in response['config']['secrets']['node']:
                        response['config']['secrets']['node'][nodename] = []
                    del node['nodeid']
                    del node['id']
                    node['content'] = Helper().decrypt_string(node['content'])
                    response['config']['secrets']['node'][nodename].append(node)
            if groupsecrets:
                response['config']['secrets']['group'] = {}
                for group in groupsecrets:
                    groupname = Database().getname_byid('group', group['groupid'])
                    if groupname not in response['config']['secrets']['group']:
                        response['config']['secrets']['group'][groupname] = []
                    del group['groupid']
                    del group['id']
                    group['content'] = Helper().decrypt_string(group['content'])
                    response['config']['secrets']['group'][groupname].append(group)
        else:
            self.logger.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_node_secrets(self, name=None, http_request=None):
        """This method will create or update all secrets for a node."""
        data = {}
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    for secret in data:
                        secret_name = secret['name']
                        where = f' WHERE nodeid = "{nodeid}" AND name = "{secret_name}"'
                        secret_data = Database().get_record(None, 'nodesecrets', where)
                        if secret_data:
                            node_secret_columns = Database().get_columns('nodesecrets')
                            column_check = Helper().checkin_list(secret_data[0], node_secret_columns)
                            if column_check:
                                secret_id = secret_data[0]['id']
                                secret['content'] = Helper().encrypt_string(secret['content'])
                                where = [
                                    {"column": "id", "value": secret_id},
                                    {"column": "nodeid", "value": nodeid},
                                    {"column": "name", "value": secret_name}
                                    ]
                                row = Helper().make_rows(secret)
                                Database().update('nodesecrets', row, where)
                                update = True
                        else:
                            secret['nodeid'] = nodeid
                            secret['content'] = Helper().encrypt_string(secret['content'])
                            row = Helper().make_rows(secret)
                            Database().insert('nodesecrets', row)
                            create = True
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Node {name} is not available.')
                response = {'message': f'Node {name} is not available'}
                access_code = 404

            if create is True and update is True:
                response = {'message': f'Node {name} Secrets created & updated'}
                access_code = 201
            elif create is True and update is False:
                response = {'message': f'Node {name} Secret created'}
                access_code = 201
            elif create is False and update is True:
                response = {'message': f'Node {name} Secret updated'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def get_node_secret(self, name=None, secret=None):
        """This method will return a requested secret of a node in detailed format."""
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            where = f' WHERE nodeid = "{nodeid}" AND name = "{secret}"'
            secret_data = Database().get_record(None, 'nodesecrets', where)
            if secret_data:
                response = {'config': {'secrets': {'node': {name: [] } } } }
                access_code = 200
                del secret_data[0]['nodeid']
                del secret_data[0]['id']
                secret_data[0]['content'] = Helper().decrypt_string(secret_data[0]['content'])
                response['config']['secrets']['node'][name] = secret_data
            else:
                self.logger.error(f'Secret {secret} is unavailable for node {name}.')
                response = {'message': f'Secret {secret} is unavailable for node {name}'}
                access_code = 404
        else:
            self.logger.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_node_secret(self, name=None, secret=None, http_request=None):
        """This method will create or update a node secret."""
        data = {}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    node_secret_columns = Database().get_columns('nodesecrets')
                    column_check = Helper().checkin_list(data[0], node_secret_columns)
                    secret_name = data[0]['name']
                    where = f' WHERE nodeid = "{nodeid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(None, 'nodesecrets', where)
                    if column_check:
                        if secret_data:
                            secret_id = secret_data[0]['id']
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            where = [
                                {"column": "id", "value": secret_id},
                                {"column": "nodeid", "value": nodeid},
                                {"column": "name", "value": secret_name}
                                ]
                            row = Helper().make_rows(data[0])
                            Database().update('nodesecrets', row, where)
                            response = {'message': f'Node {name} Secret {secret} updated'}
                            access_code = 204
                        else:
                            data[0]['nodeid'] = nodeid
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            row = Helper().make_rows(data[0])
                            result=Database().insert('nodesecrets', row)
                            if result:
                                response = {'message': f'Node {name} secret {secret} updated'}
                                access_code = 204
                            else:
                                response = {'message': f'Node {name} secret {secret} update failed: {result}'}
                                access_code = 500
                    else:
                        self.logger.error(f'Rows do not match columns for Group {name}, secret {secret}.')
                        response = {'message': 'Supplied columns do not match the requirements'}
                        access_code = 400
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Node {name} is not available.')
                response = {'message': f'Node {name} is not available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def clone_node_secret(self, name=None, secret=None, http_request=None):
        """This method will clone a requested node secret."""
        data = {}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    secret_name = data[0]['name']
                    where = f' WHERE nodeid = "{nodeid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(None, 'nodesecrets', where)
                    if secret_data:
                        if 'newsecretname' in data[0]:
                            newsecretname = data[0]['newsecretname']
                            del data[0]['newsecretname']
                            data[0]['nodeid'] = nodeid
                            data[0]['name'] = newsecretname
                            where = f' WHERE nodeid = "{nodeid}" AND name = "{newsecretname}"'
                            new_secret_data = Database().get_record(None, 'nodesecrets', where)
                            if new_secret_data:
                                self.logger.error(f'Secret {newsecretname} already present.')
                                response = {'message': f'Secret {newsecretname} already present'}
                                access_code = 404
                            else:
                                node_secret_columns = Database().get_columns('nodesecrets')
                                column_check = Helper().checkin_list(data[0], node_secret_columns)
                                if column_check:
                                    data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                    row = Helper().make_rows(data[0])
                                    Database().insert('nodesecrets', row)
                                    message = f'Node {name} Secret {secret} Cloned to {newsecretname}.'
                                    response = {'message': message}
                                    access_code = 204
                        else:
                            self.logger.error('new secret name not provided.')
                            response = {'message': 'New secret name not provided'}
                            access_code = 400
                    else:
                        self.logger.error(f'Node {name}, Secret {secret} is unavailable.')
                        response = {'message': f'Node {name}, Secret {secret} is unavailable'}
                        access_code = 404
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Node {name} is not available.')
                response = {'message': f'Node {name} is not available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def delete_node_secret(self, name=None, secret=None):
        """This method will delete a requested secret of a node."""
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            where = f' WHERE nodeid = "{nodeid}" AND name = "{secret}"'
            secret_data = Database().get_record(None, 'nodesecrets', where)
            if secret_data:
                where = [{"column": "nodeid", "value": nodeid}, {"column": "name", "value": secret}]
                Database().delete_row('nodesecrets', where)
                response = {'message': f'Secret {secret} deleted from node {name}'}
                access_code = 204
            else:
                self.logger.error(f'Secret {secret} is unavailable for node {name}.')
                response = {'message': f'Secret {secret} is unavailable for node {name}'}
                access_code = 404
        else:
            self.logger.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def get_group_secrets(self, name=None):
        """This method will return all secrets of a requested group in detailed format."""
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid  = group[0]['id']
            groupsecrets = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{groupid}"')
            if groupsecrets:
                response = {'config': {'secrets': {'group': {name: [] } } } }
                for grp in groupsecrets:
                    del grp['groupid']
                    del grp['id']
                    grp['content'] = Helper().decrypt_string(grp['content'])
                    response['config']['secrets']['group'][name].append(grp)
                    access_code = 200
            else:
                self.logger.error(f'Secrets are not available for group {name}.')
                response = {'message': f'Secrets are not available for group {name}'}
                access_code = 404
        else:
            self.logger.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_group_secrets(self, name=None, http_request=None):
        """This method will create or update all secrets for a group."""
        data = {}
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    for secret in data:
                        secret_name = secret['name']
                        where = f' WHERE groupid = "{groupid}" AND name = "{secret_name}"'
                        secret_data = Database().get_record(None, 'groupsecrets', where)
                        if secret_data:
                            group_secret_columns = Database().get_columns('groupsecrets')
                            column_check = Helper().checkin_list(secret_data[0], group_secret_columns)
                            if column_check:
                                secret_id = secret_data[0]['id']
                                secret['content'] = Helper().encrypt_string(secret['content'])
                                where = [
                                    {"column": "id", "value": secret_id},
                                    {"column": "groupid", "value": groupid},
                                    {"column": "name", "value": secret_name}
                                    ]
                                row = Helper().make_rows(secret)
                                Database().update('groupsecrets', row, where)
                                update = True
                        else:
                            secret['groupid'] = groupid
                            secret['content'] = Helper().encrypt_string(secret['content'])
                            row = Helper().make_rows(secret)
                            Database().insert('groupsecrets', row)
                            create = True
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Group {name} is not available.')
                response = {'message': f'Group {name} is not available'}
                access_code = 404

            if create is True and update is True:
                response = {'message': f'Group {name} secrets created & updated'}
                access_code = 201
            elif create is True and update is False:
                response = {'message': f'Group {name} secret created'}
                access_code = 201
            elif create is False and update is True:
                response = {'message': f'Group {name} secret updated'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def get_group_secret(self, name=None, secret=None):
        """This method will return a requested secret of a group in detailed format."""
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid  = group[0]['id']
            where = f' WHERE groupid = "{groupid}" AND name = "{secret}"'
            secret_data = Database().get_record(None, 'groupsecrets', where)
            if secret_data:
                response = {'config': {'secrets': {'group': {name: [] } } } }
                access_code = 200
                del secret_data[0]['groupid']
                del secret_data[0]['id']
                secret_data[0]['content'] = Helper().decrypt_string(secret_data[0]['content'])
                response['config']['secrets']['group'][name] = secret_data
            else:
                self.logger.error(f'Secret {secret} is unavailable for group {name}.')
                response = {'message': f'Secret {secret} is unavailable for group {name}'}
                access_code = 404
        else:
            self.logger.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_group_secret(self, name=None, secret=None, http_request=None):
        """This method will create or update a group secret."""
        data = {}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    group_secret_columns = Database().get_columns('groupsecrets')
                    column_check = Helper().checkin_list(data[0], group_secret_columns)
                    secret_name = data[0]['name']
                    where = f' WHERE groupid = "{groupid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(None, 'groupsecrets', where)
                    if column_check:
                        if secret_data:
                            secret_id = secret_data[0]['id']
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            where = [
                                {"column": "id", "value": secret_id},
                                {"column": "groupid", "value": groupid},
                                {"column": "name", "value": secret_name}
                                ]
                            row = Helper().make_rows(data[0])
                            Database().update('groupsecrets', row, where)
                            response = {'message': f'Group {name} secret {secret} updated'}
                            access_code = 204
                        else:
                            data[0]['groupid'] = groupid
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            row = Helper().make_rows(data[0])
                            result=Database().insert('groupsecrets', row)
                            if result:
                                response = {'message': f'Group {name} secret {secret} updated'}
                                access_code = 204
                            else:
                                response = {'message': f'Group {name} secret {secret} update failed: {result}'}
                                access_code = 500
                    else:
                        self.logger.error(f'Rows do not match columns for Group {name}, secret {secret}.')
                        response = {'message': f'Supplied columns do not match the requirements'}
                        access_code = 400
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Group {name} is not available.')
                response = {'message': f'Group {name} is not available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def clone_group_secret(self, name=None, secret=None, http_request=None):
        """This method will clone a requested group secret."""
        data = {}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    secret_name = data[0]['name']
                    where = f' WHERE groupid = "{groupid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(None, 'groupsecrets', where)
                    if secret_data:
                        if 'newsecretname' in data[0]:
                            newsecretname = data[0]['newsecretname']
                            del data[0]['newsecretname']
                            data[0]['groupid'] = groupid
                            data[0]['name'] = newsecretname
                            where = f' WHERE groupid = "{groupid}" AND name = "{newsecretname}"'
                            new_secret_data = Database().get_record(None, 'groupsecrets', where)
                            if new_secret_data:
                                self.logger.error(f'Secret {newsecretname} already present.')
                                response = {'message': f'Secret {newsecretname} already present'}
                                access_code = 404
                            else:
                                group_secret_columns = Database().get_columns('groupsecrets')
                                column_check = Helper().checkin_list(data[0], group_secret_columns)
                                if column_check:
                                    data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                    row = Helper().make_rows(data[0])
                                    Database().insert('groupsecrets', row)
                                    message = f'Group {name} Secret {secret} cloned to {newsecretname}.'
                                    response = {'message': message}
                                    access_code = 204
                        else:
                            self.logger.error('the new secret name not provided.')
                            response = {'message': 'The new secret name not provided'}
                            access_code = 400
                    else:
                        self.logger.error(f'Group {name}, Secret {secret} is unavailable.')
                        response = {'message': f'Group {name}, Secret {secret} is unavailable'}
                        access_code = 404
                else:
                    self.logger.error('not provided at least one secret.')
                    response = {'message': 'At least one secret not provided'}
                    access_code = 400
            else:
                self.logger.error(f'Group {name} is not available.')
                response = {'message': f'Group {name} is not available'}
                access_code = 404
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def delete_group_secret(self, name=None, secret=None):
        """This method will delete a requested secret of a group."""
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid  = group[0]['id']
            where = f' WHERE groupid = "{groupid}" AND name = "{secret}"'
            db_secret = Database().get_record(None, 'groupsecrets', where)
            if db_secret:
                where = [{"column": "groupid", "value": groupid}, {"column": "name", "value": secret}]
                Database().delete_row('groupsecrets', where)
                response = {'message': f'Secret {secret} deleted from group {name}'}
                access_code = 204
            else:
                self.logger.error(f'Secret {secret} is unavailable for group {name}.')
                response = {'message': f'Secret {secret} is unavailable for group {name}'}
                access_code = 404
        else:
            self.logger.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available'}
            access_code = 404
        return dumps(response), access_code
