#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Switch Class will handle all switch operations.
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
from utils.config import Config
from utils.service import Service
from utils.model import Model

class Switch():
    """
    This class is responsible for all operations for switch.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()
        self.table = 'switch'
        self.table_cap = self.table.capitalize()


    def get_all_switches(self):
        """
        This method will return all the switches in detailed format.
        """
        response, access_code = Model().get_record(
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return response, access_code


    def get_switch(self, name=None):
        """
        This method will return requested switch in detailed format.
        """
        response, access_code = Model().get_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return response, access_code


    def update_switch(self, name=None, http_request=None):
        """This method will create or update a switch."""
        network = False
        data, response = {}, {}
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config'][self.table][name]
            data['name'] = name
            check_switch = Database().get_record(table=self.table, where=f' WHERE `name` = "{name}"')
            if check_switch:
                switchid = check_switch[0]['id']
                if 'newswitchname' in request_data['config'][self.table][name]:
                    data['name'] = data['newswitchname']
                    del data['newswitchname']
                update = True
            else:
                create = True
            switch_columns = Database().get_columns(self.table)
            ipaddress, network = None, None
            if 'ipaddress' in data.keys():
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data.keys():
                network = data['network']
                del data['network']
            column_check = Helper().compare_list(data, switch_columns)
            data = Helper().check_ip_exist(data)
            if data:
                row = Helper().make_rows(data)
                if column_check:
                    if create:
                        switchid = Database().insert(self.table, row)
                        response = {'message': f'Switch {name} created successfully'}
                        access_code = 201
                    if update:
                        where = [{"column": "id", "value": switchid}]
                        Database().update(self.table, row, where)
                        response = {'message': f'Switch {name} updated successfully'}
                        access_code = 204
                else:
                    response = {'message': 'Bad Request; Columns are incorrect'}
                    access_code = 400
            # Antoine --->>> ----------- interface(s) update/create -------------
            if ipaddress or network:
                result, message = Config().device_ipaddress_config(switchid, self.table, ipaddress, network)
                if result is False:
                    response = {'message': f'{message}'}
                    access_code=404
                else:
                    Service().queue('dhcp','restart')
                    Service().queue('dns','restart')
            return dumps(response), access_code
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
            return dumps(response), access_code
        return dumps(response), access_code


    def clone_switch(self, name=None, http_request=None):
        """This method will clone a switch."""
        data, response = {}, {}
        create = False
        ipaddress, networkname = None, None
        request_data = http_request.data
        if request_data:
            data = request_data['config'][self.table][name]
            if 'newswitchname' in data:
                data['name'] = data['newswitchname']
                newswitchname = data['newswitchname']
                del data['newswitchname']
            else:
                response = {'message': 'New switch name not provided'}
                access_code = 400
                return dumps(response), access_code
            check_switch = Database().get_record(table=self.table, where=f' WHERE `name` = "{newswitchname}"')
            if check_switch:
                response = {'message': f'{newswitchname} already present in database'}
                access_code = 404
                return dumps(response), access_code
            else:
                create = True
            ipaddress, network = None, None
            if 'ipaddress' in data:
                ipaddress = data['ipaddress']
                del data['ipaddress']
            if 'network' in data:
                networkname = data['network']
                del data['network']
            switch_columns = Database().get_columns(self.table)
            column_check = Helper().compare_list(data, switch_columns)
            if data:
                if column_check:
                    if create:
                        switch = Database().get_record(table=self.table, where=f' WHERE `name` = "{name}"')
                        del switch[0]['id']
                        for key in switch[0]:
                            if key not in data:
                                data[key] = switch[0][key]
                        row = Helper().make_rows(data)
                        new_switchid = Database().insert(self.table, row)
                        if not new_switchid:
                            response = {'message': 'Switch not cloned due to clashing config'}
                            access_code = 404
                            self.logger.info(f"my response: {response}")
                            return dumps(response), access_code
                        access_code = 201
                        network=None
                        if networkname:
                            network = Database().get_record_join(
                                ['ipaddress.ipaddress', 'ipaddress.networkid as networkid', 'network.network', 'network.subnet'],
                                ['network.id=ipaddress.networkid'],
                                [f"network.name='{networkname}'"]
                            )
                        else:
                            network = Database().get_record_join(
                                ['ipaddress.ipaddress', 'ipaddress.networkid as networkid', 'network.name as networkname', 'network.network', 'network.subnet'],
                                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=switch.id'],
                                [f'switch.name="{name}"', 'ipaddress.tableref="switch"']
                            )
                            if network:
                                data['network'] = network[0]['networkname']
                                networkname=data['network']
                        if not ipaddress:
                            if not network:
                                network = Database().get_record(table='network', where=f' WHERE `name` = "{networkname}"')
                                if network:
                                    networkname = network[0]['networkname']
                            if network:
                                ips = Config().get_all_occupied_ips_from_network(networkname)
                                ret, avail = 0, None
                                max_count = 10
                                # we try to ping for 10 ips, if none of these are free, something
                                # else is going on (read: rogue devices)....
                                while(max_count > 0 and ret != 1):
                                    avail = Helper().get_available_ip(network[0]['network'], network[0]['subnet'], ips)
                                    ips.append(avail)
                                    _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                    max_count -= 1
                                if avail:
                                    ipaddress = avail
                            else:
                                response = {'message': 'Network and ipaddress not provided'}
                                access_code = 400
                                self.logger.info(f"my response: {response}")
                                return dumps(response), access_code
                        result, message = Config().device_ipaddress_config(new_switchid, self.table, ipaddress, networkname)
                        if result is False:
                            Database().delete_row(self.table, [{"column": "id", "value": new_switchid}])
                            # roll back
                            access_code=404
                            response = {'message': f'{message}'}
                        else:
                            Service().queue('dhcp','restart')
                            Service().queue('dns','restart')
                            response = {'message': 'Switch created'}
                else:
                    response = {'message': 'Bad Request; Columns are incorrect'}
                    access_code = 400
            else:
                response = {'message': 'Bad Request; Not enough information provided'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        self.logger.info(f"my response: {response}")
        return dumps(response), access_code


    def delete_switch(self, name=None):
        """
        This method will delete a switch.
        """
        response, access_code = Model().delete_record(
            name = name,
            table = self.table,
            table_cap = self.table_cap,
            ip_check = True
        )
        return response, access_code
