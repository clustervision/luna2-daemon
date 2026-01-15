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
Secret Class will handle all secrets related operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

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
        """
        This method will return all secrets in detailed format.
        """
        status=False
        nodesecrets = Database().get_record(table='nodesecrets')
        groupsecrets = Database().get_record(table='groupsecrets')
        if nodesecrets or groupsecrets:
            response = {'config': {'secrets': {} }}
            status=True
        else:
            response = 'No Secrets available'
            status=False
        if nodesecrets:
            response['config']['secrets']['node'] = {}
            for node in nodesecrets:
                nodename = Database().name_by_id('node', node['nodeid'])
                if nodename not in response['config']['secrets']['node']:
                    response['config']['secrets']['node'][nodename] = []
                del node['nodeid']
                del node['id']
                node['content'] = Helper().decrypt_string(node['content'])
                response['config']['secrets']['node'][nodename].append(node)
        if groupsecrets:
            response['config']['secrets']['group'] = {}
            for group in groupsecrets:
                groupname = Database().name_by_id('group', group['groupid'])
                if groupname not in response['config']['secrets']['group']:
                    response['config']['secrets']['group'][groupname] = []
                del group['groupid']
                del group['id']
                group['content'] = Helper().decrypt_string(group['content'])
                response['config']['secrets']['group'][groupname].append(group)
        return status, response


    def get_node_secrets(self, name=None):
        """
        This method will return all secrets of a requested node in detailed format.
        """
        status=False
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            groupid  = node[0]['groupid']
            where =  f'nodeid = "{nodeid}"'
            nodesecrets = Database().get_record(table='nodesecrets', where=where)
            where =  f'groupid = "{groupid}"'
            groupsecrets = Database().get_record(table='groupsecrets', where=where)
            if nodesecrets or groupsecrets:
                response = {'config': {'secrets': {} }}
                status=True
            else:
                self.logger.warning(f'no secrets available for node {name}')
                response = f'No secrets available for node {name}'
                status=False
            if nodesecrets:
                response['config']['secrets']['node'] = {}
                for node in nodesecrets:
                    nodename = Database().name_by_id('node', node['nodeid'])
                    if nodename not in response['config']['secrets']['node']:
                        response['config']['secrets']['node'][nodename] = []
                    del node['nodeid']
                    del node['id']
                    node['content'] = Helper().decrypt_string(node['content'])
                    response['config']['secrets']['node'][nodename].append(node)
            if groupsecrets:
                response['config']['secrets']['group'] = {}
                for group in groupsecrets:
                    groupname = Database().name_by_id('group', group['groupid'])
                    if groupname not in response['config']['secrets']['group']:
                        response['config']['secrets']['group'][groupname] = []
                    del group['groupid']
                    del group['id']
                    group['content'] = Helper().decrypt_string(group['content'])
                    response['config']['secrets']['group'][groupname].append(group)
        else:
            self.logger.error(f'Node {name} is not available.')
            response = f'Node {name} is not available'
            status=False
        return status, response


    def update_node_secrets(self, name=None, request_data=None):
        """
        This method will create or update all secrets for a node.
        """
        status=False
        response="Internal error"
        data = {}
        create, update = False, False
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(table='node', where=f'name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    for secret in data:
                        if ('name' not in secret.keys()) or ('content' not in secret.keys()):
                            status=False
                            return status, 'Invalid request: secret information not complete'
                        secret_name = secret['name']
                        where = f'nodeid = "{nodeid}" AND name = "{secret_name}"'
                        secret_data = Database().get_record(table='nodesecrets', where=where)
                        if secret_data:
                            node_secret_columns = Database().get_columns('nodesecrets')
                            column_check = Helper().compare_list(
                                secret_data[0],
                                node_secret_columns
                            )
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
                    response = 'Invalid request: secret information not complete'
                    status=False
            else:
                response = f'Node {name} is not available'
                status=False
            if create is True and update is True:
                response = f'Node {name} Secrets created & updated'
                status=True
            elif create is True and update is False:
                response = f'Node {name} Secret created'
                status=True
            elif create is False and update is True:
                response = f'Node {name} Secret updated'
                status=True
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def get_node_secret(self, name=None, secret=None):
        """
        This method will return a requested secret of a node in detailed format.
        """
        status=False
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            where = f'nodeid = "{nodeid}" AND name = "{secret}"'
            secret_data = Database().get_record(table='nodesecrets', where=where)
            if secret_data:
                response = {'config': {'secrets': {'node': {name: [] } } } }
                status=True
                del secret_data[0]['nodeid']
                del secret_data[0]['id']
                secret_data[0]['content'] = Helper().decrypt_string(secret_data[0]['content'])
                response['config']['secrets']['node'][name] = secret_data
            else:
                response = f'Secret {secret} is unavailable for node {name}'
                status=False
        else:
            response = f'Node {name} is not available'
            status=False
        return status, response


    def update_node_secret(self, name=None, secret=None, request_data=None):
        """
        This method will create or update a node secret.
        """
        status=False
        response="Internal error"
        data = {}
        result=False
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(table='node', where=f'name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    node_secret_columns = Database().get_columns('nodesecrets')
                    column_check = Helper().compare_list(data[0], node_secret_columns)
                    secret_name = data[0]['name']
                    where = f'nodeid = "{nodeid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(table='nodesecrets', where=where)
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
                            result=Database().update('nodesecrets', row, where)
                            response = f'Node {name} Secret {secret} updated'
                            status=True
                        else:
                            data[0]['nodeid'] = nodeid
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            row = Helper().make_rows(data[0])
                            result=Database().insert('nodesecrets', row)
                            response = f'Node {name} secret {secret} updated'
                            status=True
                        if not result:
                            response = f'Internal error: Node {name} secret {secret} create/update failed: {result}'
                            self.logger.error(response)
                            status=False
                    else:
                        response = 'Invalid request: Supplied columns do not match the requirements'
                        status=False
                else:
                    response = 'Invalid request: At least one secret needs to be provided'
                    status=False
            else:
                response = f'Node {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def clone_node_secret(self, name=None, secret=None, request_data=None):
        """
        This method will clone a requested node secret.
        """
        status=False
        response="Internal error"
        data = {}
        if request_data:
            data = request_data['config']['secrets']['node'][name]
            node = Database().get_record(table='node', where=f'name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if data:
                    secret_name = data[0]['name']
                    where = f'nodeid = "{nodeid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(table='nodesecrets', where=where)
                    if secret_data:
                        if 'newsecretname' in data[0]:
                            newsecretname = data[0]['newsecretname']
                            del data[0]['newsecretname']
                            data[0]['nodeid'] = nodeid
                            data[0]['name'] = newsecretname
                            where = f'nodeid = "{nodeid}" AND name = "{newsecretname}"'
                            new_secret_data = Database().get_record(table='nodesecrets', where=where)
                            if new_secret_data:
                                response = f'Secret {newsecretname} already present'
                                status=False
                            else:
                                node_secret_columns = Database().get_columns('nodesecrets')
                                column_check = Helper().compare_list(data[0], node_secret_columns)
                                if column_check:
                                    data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                    row = Helper().make_rows(data[0])
                                    Database().insert('nodesecrets', row)
                                    response = f'Node {name} Secret {secret} '
                                    response += f'Cloned to {newsecretname}.'
                                    status=True
                        else:
                            response = 'Invalid request: New secret name not provided'
                            status=False
                    else:
                        response = f'Node {name}, Secret {secret} is unavailable'
                        status=False
                else:
                    response = 'Invalid request: At least one secret needs to be provided'
                    status=False
            else:
                response = f'Node {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def delete_node_secret(self, name=None, secret=None):
        """
        This method will delete a requested secret of a node.
        """
        status=False
        response="Internal error"
        node = Database().get_record(table='node', where=f'name = "{name}"')
        if node:
            nodeid  = node[0]['id']
            where = f'nodeid = "{nodeid}" AND name = "{secret}"'
            secret_data = Database().get_record(table='nodesecrets', where=where)
            if secret_data:
                where = [{"column": "nodeid", "value": nodeid}, {"column": "name", "value": secret}]
                Database().delete_row('nodesecrets', where)
                response = f'Secret {secret} deleted from node {name}'
                status=True
            else:
                response = f'Secret {secret} is unavailable for node {name}'
                status=False
        else:
            response = f'Node {name} is not available'
            status=False
        return status, response


    def get_group_secrets(self, name=None):
        """
        This method will return all secrets of a requested group in detailed format.
        """
        status=False
        group = Database().get_record(table='group', where=f'name = "{name}"')
        if group:
            groupid  = group[0]['id']
            where = f'groupid = "{groupid}"'
            groupsecrets = Database().get_record(table='groupsecrets', where=where)
            if groupsecrets:
                response = {'config': {'secrets': {'group': {name: [] } } } }
                for grp in groupsecrets:
                    del grp['groupid']
                    del grp['id']
                    grp['content'] = Helper().decrypt_string(grp['content'])
                    response['config']['secrets']['group'][name].append(grp)
                    status=True
            else:
                self.logger.warning(f'no secrets available for group {name}')
                response = f'No secrets available for group {name}'
                status=False
        else:
            response = f'Group {name} is not available'
            status=False
        return status, response


    def update_group_secrets(self, name=None, request_data=None):
        """
        This method will create or update all secrets for a group.
        """
        status=False
        response="Internal error"
        data = {}
        result=False
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    for secret in data:
                        if ('name' not in secret.keys()) or ('content' not in secret.keys()):
                            status=False
                            return status, 'Invalid request: secret information not complete'
                        secret_name = secret['name']
                        where = f'groupid = "{groupid}" AND name = "{secret_name}"'
                        secret_data = Database().get_record(table='groupsecrets', where=where)
                        if secret_data:
                            group_secret_columns = Database().get_columns('groupsecrets')
                            column_check = Helper().compare_list(
                                secret_data[0],
                                group_secret_columns
                            )
                            if column_check:
                                secret_id = secret_data[0]['id']
                                secret['content'] = Helper().encrypt_string(secret['content'])
                                where = [
                                    {"column": "id", "value": secret_id},
                                    {"column": "groupid", "value": groupid},
                                    {"column": "name", "value": secret_name}
                                    ]
                                row = Helper().make_rows(secret)
                                result=Database().update('groupsecrets', row, where)
                                status=True
                                response = f'Group {name} secret updated'
                        else:
                            secret['groupid'] = groupid
                            secret['content'] = Helper().encrypt_string(secret['content'])
                            row = Helper().make_rows(secret)
                            result=Database().insert('groupsecrets', row)
                            status=True
                            response = f'Group {name} secret created'
                        if not result:
                            status=False
                            response = f'Internal error: Group {name} secret {secret_name} create/update failed: {result}'
                            self.logger.error(response)
                else:
                    response = 'Invalid request: secret information not complete'
                    status=False
            else:
                response = f'Group {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def get_group_secret(self, name=None, secret=None):
        """
        This method will return a requested secret of a group in detailed format.
        """
        status=False
        group = Database().get_record(table='group', where=f'name = "{name}"')
        if group:
            groupid  = group[0]['id']
            where = f'groupid = "{groupid}" AND name = "{secret}"'
            secret_data = Database().get_record(table='groupsecrets', where=where)
            if secret_data:
                response = {'config': {'secrets': {'group': {name: [] } } } }
                status=True
                del secret_data[0]['groupid']
                del secret_data[0]['id']
                secret_data[0]['content'] = Helper().decrypt_string(secret_data[0]['content'])
                response['config']['secrets']['group'][name] = secret_data
            else:
                response = f'Secret {secret} is unavailable for group {name}'
                status=False
        else:
            response = f'Group {name} is not available'
            status=False
        return status, response


    def update_group_secret(self, name=None, secret=None, request_data=None):
        """
        This method will create or update a group secret.
        """
        status=False
        response="Internal error"
        data = {}
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    group_secret_columns = Database().get_columns('groupsecrets')
                    column_check = Helper().compare_list(data[0], group_secret_columns)
                    secret_name = data[0]['name']
                    where = f'groupid = "{groupid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(table='groupsecrets', where=where)
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
                            response = f'Group {name} secret {secret} updated'
                            status=True
                        else:
                            data[0]['groupid'] = groupid
                            data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                            row = Helper().make_rows(data[0])
                            result=Database().insert('groupsecrets', row)
                            if result:
                                response = f'Group {name} secret {secret} updated'
                                status=True
                            else:
                                response = f'Internal error: Group {name} secret {secret} update failed: {result}'
                                status=False
                                self.logger.error(response)
                    else:
                        response = 'Invalid request: Supplied columns do not match the requirements'
                        status=False
                        self.logger.error(response)
                else:
                    response = 'Invalid request: At least one secret needs to be provided'
                    status=False
            else:
                response = f'Group {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not received data'
            status=False
        return status, response


    def clone_group_secret(self, name=None, secret=None, request_data=None):
        """
        This method will clone a requested group secret.
        """
        status=False
        response="Internal error"
        data = {}
        if request_data:
            data = request_data['config']['secrets']['group'][name]
            group = Database().get_record(table='group', where=f'name = "{name}"')
            if group:
                groupid = group[0]['id']
                if data:
                    secret_name = data[0]['name']
                    where = f'groupid = "{groupid}" AND name = "{secret_name}"'
                    secret_data = Database().get_record(table='groupsecrets', where=where)
                    if secret_data:
                        if 'newsecretname' in data[0]:
                            newsecretname = data[0]['newsecretname']
                            del data[0]['newsecretname']
                            data[0]['groupid'] = groupid
                            data[0]['name'] = newsecretname
                            where = f'groupid = "{groupid}" AND name = "{newsecretname}"'
                            new_secret_data = Database().get_record(table='groupsecrets', where=where)
                            if new_secret_data:
                                self.logger.error(f'Secret {newsecretname} already present.')
                                response = f'Secret {newsecretname} already present'
                                status=False
                            else:
                                group_secret_columns = Database().get_columns('groupsecrets')
                                column_check = Helper().compare_list(data[0], group_secret_columns)
                                if column_check:
                                    data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                    row = Helper().make_rows(data[0])
                                    Database().insert('groupsecrets', row)
                                    response = f'Group {name} Secret {secret} '
                                    response += f'Cloned to {newsecretname}.'
                                    status=True
                        else:
                            response = 'Invalid request: The new secret name not provided'
                            status=False
                    else:
                        response = f'Group {name}, Secret {secret} is unavailable'
                        status=False
                else:
                    response = 'Invalid request: At least one secret not provided'
                    status=False
            else:
                response = f'Group {name} is not available'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response


    def delete_group_secret(self, name=None, secret=None):
        """
        This method will delete a requested secret of a group.
        """
        status=False
        response="Internal error"
        group = Database().get_record(table='group', where=f'name = "{name}"')
        if group:
            groupid  = group[0]['id']
            where = f'groupid = "{groupid}" AND name = "{secret}"'
            db_secret = Database().get_record(table='groupsecrets', where=where)
            if db_secret:
                where = [
                    {"column": "groupid", "value": groupid},
                    {"column": "name", "value": secret}
                ]
                Database().delete_row('groupsecrets', where)
                response = f'Secret {secret} deleted from group {name}'
                status=True
            else:
                response = f'Secret {secret} is unavailable for group {name}'
                status=False
        else:
            response = f'Group {name} is not available'
            status=False
        return status, response
