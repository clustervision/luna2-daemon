#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BMC Setup Class will handle all bmc setup operations.
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
from utils.model import Model


class BMCSetup():
    """
    This class is responsible for all operations for bmc setup.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'bmcsetup'
        self.table_cap = 'BMC Setup'


    def get_all_bmcsetup(self):
        """
        This method will return all the bmcsetup in detailed format.
        """
        response, access_code = Model().get_record(
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def get_bmcsetup(self, name=None):
        """
        This method will return requested bmcsetup in detailed format.
        """
        response, access_code = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def get_bmcsetup_member(self, name=None):
        """
        This method will return all the list of all the member node names for a bmcsetup.
        """
        response, access_code = Model().get_member(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code


    def update_bmcsetup(self, name=None, http_request=None):
        """
        This method will create or update a bmcsetup.
        """
        new_name = 'newbmcname'
        response, access_code = Model().change_record(
            name = name,
            new_name = new_name,
            table = self.table,
            table_cap = self.table_cap,
            request_data = http_request.data
        )
        return response, access_code



    def clone_bmcsetup(self, name=None, http_request=None):
        """
        This method will clone a bmcsetup.
        """
        data, response = {}, {}
        create = False
        request_data = http_request.data
        if request_data:
            data = request_data['config'][self.table][name]
            if 'newbmcname' in data:
                data['name'] = data['newbmcname']
                newbmcname = data['newbmcname']
                del data['newbmcname']
            else:
                response = {'message': 'New bmc name nor provided'}
                access_code = 400
                return dumps(response), access_code
            where = f' WHERE `name` = "{name}"'
            check_bmcsetup = Database().get_record(table=self.table, where=where)
            if check_bmcsetup:
                where = f' WHERE `name` = "{newbmcname}"'
                check_new_bmcsetup = Database().get_record(table=self.table, where=where)
                if check_new_bmcsetup:
                    response = {'message': f'{newbmcname} Already present in database'}
                    access_code = 404
                    return dumps(response), access_code
                else:
                    create = True
                del check_bmcsetup[0]['id']
                for item in check_bmcsetup[0]:
                    if not item in data:
                        data[item] = check_bmcsetup[0][item]
            else:
                response = {'message': f'{name} not present in database'}
                access_code = 404
                return dumps(response), access_code
            bmcsetup_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, bmcsetup_columns)
            row = Helper().make_rows(data)
            if column_check:
                if create:
                    Database().insert(self.table, row)
                    response = {'message': 'BMC Setup created successfully'}
                    access_code = 201
            else:
                response = {'message': 'Columns are incorrect'}
                access_code = 400
                return dumps(response), access_code
        else:
            response = {'message': 'Did not received data'}
            access_code = 400
            return dumps(response), access_code
        return dumps(response), access_code


    def delete_bmcsetup(self, name=None):
        """
        This method will delete a bmcsetup.
        """
        response, access_code = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap
        )
        return response, access_code
